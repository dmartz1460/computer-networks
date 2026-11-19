import socket
import unittest

from src.client.frame_codec import encode_frame, read_frame


class FrameCodecTests(unittest.TestCase):
    def test_round_trip_preserves_utf8(self):
        left, right = socket.socketpair()
        try:
            left.sendall(encode_frame("hello | café"))
            self.assertEqual(read_frame(right), "hello | café")
        finally:
            left.close()
            right.close()

    def test_rejects_negative_length(self):
        left, right = socket.socketpair()
        try:
            left.sendall((-1).to_bytes(4, "big", signed=True))
            with self.assertRaises(ValueError):
                read_frame(right)
        finally:
            left.close()
            right.close()
