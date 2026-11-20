"""Console UI helpers for the bulletin board client.

Responsible only for formatting output to stdout.  All string assembly is
centralised here so the rest of the client does not contain any raw print
statements with presentation logic.
"""

from __future__ import annotations

import sys
from typing import Any


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _divider(char: str = "-", width: int = 60) -> str:
    return char * width


def _header(title: str) -> None:
    print(_divider())
    print(f"  {title}")
    print(_divider())


# ---------------------------------------------------------------------------
# Public output functions
# ---------------------------------------------------------------------------

def show_prompt() -> None:
    """Print the interactive prompt without a newline."""
    print("> ", end="", flush=True)


def show_info(message: str) -> None:
    print(f"[info] {message}")


def show_error(message: str) -> None:
    print(f"[error] {message}", file=sys.stderr)


def show_welcome() -> None:
    _header("Bulletin Board Client")
    print("  Type %connect <host> [port] to get started.")
    print("  Type %exit to quit.\n")


def show_connected(host: str, port: int, username: str) -> None:
    print(f"[info] Connected to {host}:{port} as '{username}'")
    print("[info] Type %help to see all available commands.")


def show_help() -> None:
    _header("Available Commands")
    rows = [
        # (command,                        description)
        ("%connect <host> [port]",         "Connect to the bulletin board server (default port 5000)"),
        ("%join",                          "Join the public message board"),
        ("%post <subject> <content>",      "Post a message to the public board"),
        ("%users",                         "List users on the public board"),
        ("%leave",                         "Leave the public board"),
        ("%message <id>",                  "Retrieve the full content of a public message"),
        ("",                               ""),
        ("%groups",                        "List all available private groups"),
        ("%groupjoin <group>",             "Join a private group by ID or name"),
        ("%grouppost <group> <subject> <content>", "Post a message to a private group"),
        ("%groupusers <group>",            "List users in a private group"),
        ("%groupleave <group>",            "Leave a private group"),
        ("%groupmessage <group> <id>",     "Retrieve the full content of a group message"),
        ("",                               ""),
        ("%help",                          "Show this help message"),
        ("%exit",                          "Disconnect from the server and quit"),
    ]
    cmd_width = max(len(cmd) for cmd, _ in rows) + 2
    for cmd, description in rows:
        if cmd == "":
            print()
            continue
        print(f"  {cmd:<{cmd_width}} {description}")
    print()


def show_disconnected() -> None:
    print("[info] Disconnected from server")


def show_server_error(payload: dict, hint: str | None = None) -> None:
    code = payload.get("code", "UNKNOWN")
    message = payload.get("message", "")
    print(f"[server error] {code}: {message}", file=sys.stderr)
    if hint:
        print(f"[hint] {hint}", file=sys.stderr)


def show_groups(groups: list[dict]) -> None:
    _header("Available Groups")
    for group in groups:
        print(f"  {group['id']:>2}. {group['name']}")
    print()


def show_users(board: str, users: list[str]) -> None:
    _header(f"Users on '{board}'")
    if users:
        for user in users:
            print(f"  - {user}")
    else:
        print("  (no users)")
    print()


def show_join(payload: dict) -> None:
    board = payload.get("board", "?")
    users = payload.get("users", [])
    messages = payload.get("messages", [])
    _header(f"Joined '{board}'")
    print(f"  Members: {', '.join(users) if users else '(none)'}")
    if messages:
        print(f"\n  Last {len(messages)} message(s) on this board:")
        show_message_summaries(messages)
    print()


def show_left(payload: dict) -> None:
    board = payload.get("board", "?")
    username = payload.get("username", "?")
    users = payload.get("users", [])
    remaining = ", ".join(users) if users else "(none)"
    print(f"[info] Left '{board}'. Remaining members: {remaining}")


def show_post_ack(payload: dict) -> None:
    board = payload.get("board", "?")
    mid = payload.get("messageId", "?")
    subject = payload.get("subject", "?")
    date = payload.get("postDate", "?")
    print(f"[posted] board='{board}' id={mid} subject='{subject}' at {date}")


def show_message_summaries(summaries: list[dict]) -> None:
    """Print message summaries in the required format: ID | Sender | Date | Subject."""
    if not summaries:
        print("  (no messages)")
        return
    print(f"  {'ID':<6} {'Sender':<16} {'Post Date':<26} Subject")
    print("  " + _divider("-", 70))
    for msg in summaries:
        mid = str(msg.get("id", "?"))
        sender = str(msg.get("sender", "?"))
        date = str(msg.get("postDate", "?"))
        subject = str(msg.get("subject", "?"))
        print(f"  {mid:<6} {sender:<16} {date:<26} {subject}")


def show_message_detail(payload: dict) -> None:
    _header(f"Message {payload.get('id', '?')}")
    print(f"  Sender  : {payload.get('sender', '?')}")
    print(f"  Date    : {payload.get('postDate', '?')}")
    print(f"  Subject : {payload.get('subject', '?')}")
    print()
    print(f"  {payload.get('content', '')}")
    print()


# ---------------------------------------------------------------------------
# Event display (called from the receiver thread via a queue)
# ---------------------------------------------------------------------------

def show_event(event: dict) -> None:
    """Format and print a push event from the server."""
    event_type = event.get("type", "UNKNOWN")
    board = event.get("board", "?")

    if event_type == "USER_JOINED":
        user = event.get("user", "?")
        users = event.get("users", [])
        print(f"\n[event] '{user}' joined '{board}'.  Members: {', '.join(users)}")
    elif event_type == "USER_LEFT":
        user = event.get("user", "?")
        users = event.get("users", [])
        print(f"\n[event] '{user}' left '{board}'.  Remaining: {', '.join(users) or '(none)'}")
    elif event_type == "GROUP_JOINED":
        user = event.get("user", "?")
        users = event.get("users", [])
        print(f"\n[event] '{user}' joined group '{board}'.  Members: {', '.join(users)}")
    elif event_type == "GROUP_LEFT":
        user = event.get("user", "?")
        users = event.get("users", [])
        print(f"\n[event] '{user}' left group '{board}'.  Remaining: {', '.join(users) or '(none)'}")
    elif event_type == "MESSAGE_POSTED":
        mid = event.get("messageId", "?")
        sender = event.get("sender", "?")
        subject = event.get("subject", "?")
        date = event.get("postDate", "?")
        print(f"\n[new message] board='{board}' id={mid} sender='{sender}' "
              f"subject='{subject}' at {date}")
    elif event_type == "_DISCONNECTED":
        # Synthetic internal event from the receiver thread.
        print("\n[info] Server connection closed unexpectedly")
    else:
        print(f"\n[event] {event_type} on '{board}': {event}")
