"""Bulletin board client entry point.

Runs an interactive command loop that connects to the bulletin board server
and supports Part 1 (public board) and Part 2 (private groups) commands.

Usage:
    python bulletin_client.py

Then type commands such as:
    %connect localhost 5000
    %join
    %post Hello World
    %groups
    %groupjoin general
    %exit
"""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the client package directory is on the path so sibling modules load.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from command_parser import CommandError, ParsedCommand, parse
from console_ui import (
    show_connected,
    show_disconnected,
    show_error,
    show_event,
    show_groups,
    show_help,
    show_info,
    show_join,
    show_left,
    show_message_detail,
    show_message_summaries,
    show_post_ack,
    show_server_error,
    show_users,
    show_welcome,
)
from protocol_client import ProtocolClient, b64_encode

DEFAULT_PORT = 5000


# ---------------------------------------------------------------------------
# BulletinClient: main application loop
# ---------------------------------------------------------------------------

class BulletinClient:
    """Ties together the ProtocolClient, command parser, and console UI."""

    def __init__(self) -> None:
        # Event queue bridges the receiver (background) thread to the UI
        # so that events are printed without interleaving with user input.
        self._event_queue: queue.SimpleQueue[dict] = queue.SimpleQueue()
        self._client = ProtocolClient(event_handler=self._on_event)
        self._username: str | None = None

    # ------------------------------------------------------------------
    # Event callback (called from receiver thread)
    # ------------------------------------------------------------------

    def _on_event(self, event: dict) -> None:
        """Enqueue a push event so the main thread can render it safely."""
        self._event_queue.put(event)

    def _drain_events(self) -> None:
        """Print any pending events that arrived since the last drain."""
        while not self._event_queue.empty():
            try:
                event = self._event_queue.get_nowait()
                show_event(event)
                if event.get("type") == "_DISCONNECTED":
                    self._username = None
            except queue.Empty:
                break

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------

    def _request(self, payload: str, hint: str | None = None) -> dict | None:
        """Send a request and return the response payload dict on success.

        Prints server errors (with an optional *hint*) and returns None on
        failure so callers can be written as simple ``if payload is not None``
        guards.
        """
        try:
            response = self._client.send_request(payload)
        except (TimeoutError, RuntimeError, OSError) as exc:
            show_error(str(exc))
            return None

        self._drain_events()

        if response["status"] == "ERROR":
            show_server_error(response["payload"], hint=hint)
            return None

        return response["payload"]

    # ------------------------------------------------------------------
    # Connection / registration
    # ------------------------------------------------------------------

    def _cmd_connect(self, args: list[str]) -> None:
        if self._client.connected:
            show_error("Already connected. Use %exit or %leave first.")
            return

        host = args[0]
        port = int(args[1]) if len(args) > 1 else DEFAULT_PORT

        try:
            self._client.connect(host, port)
        except OSError as exc:
            show_error(f"Could not connect to {host}:{port} – {exc}")
            return

        # Registration loop: prompt until name is accepted.
        while True:
            try:
                username = input("Enter username: ").strip()
            except (EOFError, KeyboardInterrupt):
                self._client.disconnect()
                return

            if not username:
                show_error("Username cannot be empty.")
                continue
            if "|" in username:
                show_error("Username cannot contain '|'.")
                continue

            payload = self._request(f"REGISTER|{b64_encode(username)}")
            if payload is not None:
                self._username = payload.get("username", username)
                show_connected(host, port, self._username)
                return
            # On NAME_TAKEN the error was already printed; loop to re-prompt.

    def _cmd_exit(self) -> bool:
        """Send DISCONNECT if registered, close the socket, and return True to quit."""
        if self._client.connected:
            if self._username is not None:
                self._request("DISCONNECT")
            self._client.disconnect()
            show_disconnected()
        return True  # signal the main loop to stop

    # ------------------------------------------------------------------
    # Part 1 – public board
    # ------------------------------------------------------------------

    def _cmd_join(self) -> None:
        payload = self._request("JOIN_PUBLIC")
        if payload is not None:
            show_join(payload)

    def _cmd_post(self, args: list[str]) -> None:
        # args[0] = subject, args[1] = content (already joined by parser)
        subject, content = args[0], args[1]
        payload = self._request(
            f"POST_PUBLIC|{b64_encode(subject)}|{b64_encode(content)}",
            hint="Run %join first to join the public board before posting.",
        )
        if payload is not None:
            show_post_ack(payload)

    def _cmd_users(self) -> None:
        payload = self._request(
            "USERS_PUBLIC",
            hint="Run %join first to join the public board.",
        )
        if payload is not None:
            show_users(payload.get("board", "public"), payload.get("users", []))

    def _cmd_leave(self) -> None:
        payload = self._request(
            "LEAVE_PUBLIC",
            hint="Run %join first to join the public board.",
        )
        if payload is not None:
            show_left(payload)

    def _cmd_message(self, args: list[str]) -> None:
        message_id = args[0]
        payload = self._request(
            f"MESSAGE_PUBLIC|{message_id}",
            hint="Run %join first to join the public board.",
        )
        if payload is not None:
            show_message_detail(payload)

    # ------------------------------------------------------------------
    # Part 2 – private groups
    # ------------------------------------------------------------------

    def _cmd_groups(self) -> None:
        payload = self._request("LIST_GROUPS")
        if payload is not None:
            show_groups(payload.get("groups", []))

    def _cmd_groupjoin(self, args: list[str]) -> None:
        group = args[0]
        payload = self._request(f"JOIN_GROUP|{group}")
        if payload is not None:
            show_join(payload)

    def _cmd_grouppost(self, args: list[str]) -> None:
        group, subject, content = args[0], args[1], args[2]
        payload = self._request(
            f"POST_GROUP|{group}|{b64_encode(subject)}|{b64_encode(content)}"
        )
        if payload is not None:
            show_post_ack(payload)

    def _cmd_groupusers(self, args: list[str]) -> None:
        group = args[0]
        payload = self._request(f"USERS_GROUP|{group}")
        if payload is not None:
            show_users(payload.get("board", group), payload.get("users", []))

    def _cmd_groupleave(self, args: list[str]) -> None:
        group = args[0]
        payload = self._request(f"LEAVE_GROUP|{group}")
        if payload is not None:
            show_left(payload)

    def _cmd_groupmessage(self, args: list[str]) -> None:
        group, message_id = args[0], args[1]
        payload = self._request(f"MESSAGE_GROUP|{group}|{message_id}")
        if payload is not None:
            show_message_detail(payload)

    # ------------------------------------------------------------------
    # Dispatch table
    # ------------------------------------------------------------------

    def _dispatch(self, cmd: ParsedCommand) -> bool:
        """Execute a parsed command.  Returns True if the client should exit."""
        name, args = cmd.name, cmd.args

        # Guard: require connection for board commands.
        board_commands = {
            "join", "post", "users", "leave", "message",
            "groups", "groupjoin", "grouppost", "groupusers",
            "groupleave", "groupmessage",
        }
        if name in board_commands and not self._client.connected:
            show_error("Not connected. Use %connect <host> [port] first.")
            return False

        # Guard: require registration for board commands.
        if name in board_commands and self._username is None:
            show_error("Not registered. Reconnect with %connect.")
            return False

        match name:
            case "connect":
                self._cmd_connect(args)
            case "help":
                show_help()
            case "join":
                self._cmd_join()
            case "post":
                self._cmd_post(args)
            case "users":
                self._cmd_users()
            case "leave":
                self._cmd_leave()
            case "message":
                self._cmd_message(args)
            case "groups":
                self._cmd_groups()
            case "groupjoin":
                self._cmd_groupjoin(args)
            case "grouppost":
                self._cmd_grouppost(args)
            case "groupusers":
                self._cmd_groupusers(args)
            case "groupleave":
                self._cmd_groupleave(args)
            case "groupmessage":
                self._cmd_groupmessage(args)
            case "exit":
                return self._cmd_exit()

        return False

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        show_welcome()
        while True:
            # Print any events that arrived while we were waiting for input.
            self._drain_events()
            try:
                raw = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self._cmd_exit()
                break

            if not raw:
                continue

            try:
                cmd = parse(raw)
            except CommandError as exc:
                show_error(str(exc))
                continue

            try:
                should_exit = self._dispatch(cmd)
            except Exception as exc:  # noqa: BLE001 – catch-all safety net
                show_error(f"Unexpected error: {exc}")
                continue

            if should_exit:
                break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    BulletinClient().run()


if __name__ == "__main__":
    main()
