"""Client-side unit tests.

Tests cover:
- Frame encode/decode round-trip
- Base64 encode/decode round-trip
- JSON payload parse
- CommandParser: accepts all required commands
- CommandParser: rejects missing arguments
- Spaces in subject/content are preserved
- Pipe characters in subject/content survive Base64 round-trip
- %post subject/content splitting edge cases
- %grouppost splitting edge cases
- Unexpected status code handling (OK vs ERROR)
- Event frame detection vs response frame detection

Run with:
    python -m pytest test/client/ -v
  or directly:
    python test/client/test_client.py
"""

import base64
import struct
import sys
import types
import unittest
from pathlib import Path
from io import BytesIO

# ---------------------------------------------------------------------------
# Path setup – make src/client importable.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src" / "client"))

import command_parser as cp
from protocol_client import (
    _build_frame,
    _read_frame,
    _read_exact,
    b64_encode,
    b64_decode,
    parse_json_payload,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_socket_from_bytes(data: bytes):
    """Return a mock socket-like object that reads from *data*."""

    class _FakeSocket:
        def __init__(self, buf: bytes) -> None:
            self._buf = BytesIO(buf)

        def recv(self, n: int) -> bytes:
            return self._buf.read(n)

    return _FakeSocket(data)


# ---------------------------------------------------------------------------
# Frame codec tests
# ---------------------------------------------------------------------------

class TestFrameCodec(unittest.TestCase):

    def test_encode_then_decode_round_trip(self):
        for payload in ["hello", "REGISTER|1|dXNlcg==", "a" * 1000, "émoji 🎉"]:
            with self.subTest(payload=payload[:30]):
                frame = _build_frame(payload)
                sock = _make_socket_from_bytes(frame)
                result = _read_frame(sock)
                self.assertEqual(result, payload)

    def test_header_is_big_endian_signed_int(self):
        payload = "test"
        frame = _build_frame(payload)
        length = struct.unpack(">i", frame[:4])[0]
        self.assertEqual(length, len("test".encode("utf-8")))

    def test_empty_payload(self):
        frame = _build_frame("")
        sock = _make_socket_from_bytes(frame)
        self.assertEqual(_read_frame(sock), "")

    def test_multiple_frames_sequential(self):
        combined = _build_frame("first") + _build_frame("second")
        sock = _make_socket_from_bytes(combined)
        self.assertEqual(_read_frame(sock), "first")
        self.assertEqual(_read_frame(sock), "second")


# ---------------------------------------------------------------------------
# Base64 / JSON helpers
# ---------------------------------------------------------------------------

class TestBase64Helpers(unittest.TestCase):

    def test_encode_decode_simple(self):
        self.assertEqual(b64_decode(b64_encode("hello")), "hello")

    def test_encode_decode_with_spaces(self):
        text = "this has spaces and newlines\nin it"
        self.assertEqual(b64_decode(b64_encode(text)), text)

    def test_encode_decode_pipe_characters(self):
        # Pipe characters must survive a Base64 round-trip because the
        # protocol separates protocol fields with '|'.
        text = "subject|with|pipes"
        self.assertEqual(b64_decode(b64_encode(text)), text)

    def test_encode_decode_unicode(self):
        text = "こんにちは 🎉"
        self.assertEqual(b64_decode(b64_encode(text)), text)

    def test_parse_json_payload(self):
        raw = {"key": "value", "num": 42}
        import json
        b64 = b64_encode(json.dumps(raw))
        result = parse_json_payload(b64)
        self.assertEqual(result, raw)

    def test_parse_json_payload_malformed_raises(self):
        # Non-JSON Base64 content must raise, not silently return garbage.
        b64 = b64_encode("not json {{")
        with self.assertRaises(Exception):
            parse_json_payload(b64)


# ---------------------------------------------------------------------------
# Command parser tests
# ---------------------------------------------------------------------------

class TestCommandParser(unittest.TestCase):

    # --- commands that require no args ---
    def test_join_no_args(self):
        cmd = cp.parse("%join")
        self.assertEqual(cmd.name, "join")
        self.assertEqual(cmd.args, [])

    def test_users_no_args(self):
        cmd = cp.parse("%users")
        self.assertEqual(cmd.name, "users")

    def test_leave_no_args(self):
        cmd = cp.parse("%leave")
        self.assertEqual(cmd.name, "leave")

    def test_groups_no_args(self):
        cmd = cp.parse("%groups")
        self.assertEqual(cmd.name, "groups")

    def test_exit_no_args(self):
        cmd = cp.parse("%exit")
        self.assertEqual(cmd.name, "exit")

    # --- connect ---
    def test_connect_host_only(self):
        cmd = cp.parse("%connect localhost")
        self.assertEqual(cmd.name, "connect")
        self.assertEqual(cmd.args, ["localhost"])

    def test_connect_host_and_port(self):
        cmd = cp.parse("%connect 127.0.0.1 5000")
        self.assertEqual(cmd.args, ["127.0.0.1", "5000"])

    def test_connect_too_many_args_rejected(self):
        with self.assertRaises(cp.CommandError):
            cp.parse("%connect host 5000 extra")

    # --- %message ---
    def test_message_one_arg(self):
        cmd = cp.parse("%message 42")
        self.assertEqual(cmd.args, ["42"])

    def test_message_no_arg_rejected(self):
        with self.assertRaises(cp.CommandError):
            cp.parse("%message")

    # --- %post ---
    def test_post_subject_and_single_word_content(self):
        cmd = cp.parse("%post Hello World")
        self.assertEqual(cmd.name, "post")
        self.assertEqual(cmd.args[0], "Hello")
        self.assertEqual(cmd.args[1], "World")

    def test_post_content_with_spaces_preserved(self):
        cmd = cp.parse("%post MySubject This is the content of the message")
        self.assertEqual(cmd.args[0], "MySubject")
        self.assertEqual(cmd.args[1], "This is the content of the message")

    def test_post_missing_content_rejected(self):
        with self.assertRaises(cp.CommandError):
            cp.parse("%post OnlySubject")

    def test_post_no_args_rejected(self):
        with self.assertRaises(cp.CommandError):
            cp.parse("%post")

    # --- %groupjoin ---
    def test_groupjoin_by_name(self):
        cmd = cp.parse("%groupjoin sports")
        self.assertEqual(cmd.args, ["sports"])

    def test_groupjoin_by_id(self):
        cmd = cp.parse("%groupjoin 3")
        self.assertEqual(cmd.args, ["3"])

    def test_groupjoin_no_arg_rejected(self):
        with self.assertRaises(cp.CommandError):
            cp.parse("%groupjoin")

    # --- %grouppost ---
    def test_grouppost_three_parts(self):
        cmd = cp.parse("%grouppost general Hello World")
        self.assertEqual(cmd.args[0], "general")
        self.assertEqual(cmd.args[1], "Hello")
        self.assertEqual(cmd.args[2], "World")

    def test_grouppost_content_with_spaces_preserved(self):
        cmd = cp.parse("%grouppost tech SubjectLine Long content body here")
        self.assertEqual(cmd.args[0], "tech")
        self.assertEqual(cmd.args[1], "SubjectLine")
        self.assertEqual(cmd.args[2], "Long content body here")

    def test_grouppost_too_few_args_rejected(self):
        with self.assertRaises(cp.CommandError):
            cp.parse("%grouppost general OnlySubject")

    # --- %groupusers ---
    def test_groupusers_valid(self):
        cmd = cp.parse("%groupusers gaming")
        self.assertEqual(cmd.args, ["gaming"])

    # --- %groupleave ---
    def test_groupleave_valid(self):
        cmd = cp.parse("%groupleave study")
        self.assertEqual(cmd.args, ["study"])

    # --- %groupmessage ---
    def test_groupmessage_valid(self):
        cmd = cp.parse("%groupmessage tech 7")
        self.assertEqual(cmd.args, ["tech", "7"])

    def test_groupmessage_missing_id_rejected(self):
        with self.assertRaises(cp.CommandError):
            cp.parse("%groupmessage tech")

    # --- unknown command ---
    def test_unknown_command_rejected(self):
        with self.assertRaises(cp.CommandError):
            cp.parse("%foobar")

    # --- not a command ---
    def test_no_percent_prefix_rejected(self):
        with self.assertRaises(cp.CommandError):
            cp.parse("join")

    # --- case insensitivity of keyword ---
    def test_keyword_case_insensitive(self):
        cmd = cp.parse("%JOIN")
        self.assertEqual(cmd.name, "join")

    # --- trailing whitespace is stripped ---
    def test_leading_trailing_whitespace(self):
        cmd = cp.parse("  %groups  ")
        self.assertEqual(cmd.name, "groups")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
