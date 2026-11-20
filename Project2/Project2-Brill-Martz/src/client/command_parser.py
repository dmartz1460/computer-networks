"""Command parser for the bulletin board client.

Parses raw user input into (command, args) tuples, validates argument counts,
and raises descriptive errors for missing or malformed inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


# ---------------------------------------------------------------------------
# Command definitions
# ---------------------------------------------------------------------------

# Maps the command keyword (lowercase, without %) to (min_args, max_args, usage)
# where args are the positional tokens after the keyword.  -1 means unlimited.
_COMMANDS: dict[str, tuple[int, int, str]] = {
    "connect":      (1, 2, "%connect <host> [port]"),
    "join":         (0, 0, "%join"),
    "post":         (2, -1, "%post <subject> <content>"),
    "users":        (0, 0, "%users"),
    "leave":        (0, 0, "%leave"),
    "message":      (1, 1, "%message <message-id>"),
    "help":         (0, 0, "%help"),
    "groups":       (0, 0, "%groups"),
    "groupjoin":    (1, 1, "%groupjoin <group-id-or-name>"),
    "grouppost":    (3, -1, "%grouppost <group-id-or-name> <subject> <content>"),
    "groupusers":   (1, 1, "%groupusers <group-id-or-name>"),
    "groupleave":   (1, 1, "%groupleave <group-id-or-name>"),
    "groupmessage": (2, 2, "%groupmessage <group-id-or-name> <message-id>"),
    "exit":         (0, 0, "%exit"),
}


@dataclass
class ParsedCommand:
    """A successfully parsed user command."""
    name: str           # e.g. "post"
    args: List[str]     # positional tokens after the command keyword


class CommandError(ValueError):
    """Raised when input does not match any known command or is missing arguments."""


def parse(raw: str) -> ParsedCommand:
    """Parse a raw input line into a ParsedCommand.

    Rules:
    - Input must start with '%'.
    - The first token (lowercased) is the command keyword.
    - For commands with a free-form tail (max_args == -1), the last argument
      absorbs all remaining tokens joined by spaces so that the split is:
        %post <subject_word> rest of line is content
        %grouppost <group> <subject_word> rest of line is content

    Raises:
        CommandError: for unknown commands or wrong argument counts.
    """
    stripped = raw.strip()
    if not stripped.startswith("%"):
        raise CommandError("Commands must start with '%'")

    tokens = stripped.split()
    keyword = tokens[0][1:].lower()  # strip '%', lowercase

    spec = _COMMANDS.get(keyword)
    if spec is None:
        raise CommandError(
            f"Unknown command '%{keyword}'.  "
            f"Available: {', '.join('%' + k for k in _COMMANDS)}"
        )

    min_args, max_args, usage = spec
    args = tokens[1:]  # everything after the keyword

    if max_args == -1:
        # Variable-length tail: the last free-form field absorbs remaining tokens.
        # Determine how many leading positional args are fixed.
        # e.g. %post has min_args=2: 1 fixed (subject) + tail (content)
        #      %grouppost has min_args=3: 2 fixed (group, subject) + tail (content)
        fixed_count = min_args - 1   # all but the last free-form field
        if len(args) < min_args:
            raise CommandError(f"Too few arguments.  Usage: {usage}")
        # Rejoin the tail into a single string for the last argument.
        leading = args[:fixed_count]
        tail = " ".join(args[fixed_count:])
        args = leading + [tail]
    else:
        if len(args) < min_args:
            raise CommandError(f"Too few arguments.  Usage: {usage}")
        if len(args) > max_args:
            raise CommandError(f"Too many arguments.  Usage: {usage}")

    return ParsedCommand(name=keyword, args=args)
