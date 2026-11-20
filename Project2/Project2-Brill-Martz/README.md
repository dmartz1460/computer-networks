# Project 2 Bulletin Board

Daniel Brill  
Dylan Martz

## Overview

This project is a console bulletin board with a Java TCP server and a Python
TCP client. The server supports a public board and five private group boards:
`general`, `sports`, `study`, `gaming`, and `tech`.

## Requirements

- JDK 17 or newer
- Python 3.10 or newer
- No third-party packages

## Run the server

Open a terminal in this directory, which contains `src/server/`.

### Windows (PowerShell)

```powershell
New-Item -ItemType Directory -Force build\server | Out-Null
javac -d build\server src\server\*.java
java -cp build\server server.BulletinServer --port 5000
```

### Windows (Command Prompt)

```bat
if not exist build\server mkdir build\server
javac -d build\server src\server\*.java
java -cp build\server server.BulletinServer --port 5000
```

### macOS and Linux

```bash
mkdir -p build/server
javac -d build/server src/server/*.java
java -cp build/server server.BulletinServer --port 5000
```

The server uses port `5000` by default. The port can be changed by replacing
`5000` with another non-system port in the Java command.

Stop the server with `Ctrl+C`.

## Client commands

```text
%connect <host> [port]
%join
%post <subject> <content>
%users
%leave
%message <message-id>
%groups
%groupjoin <group-id-or-name>
%grouppost <group-id-or-name> <subject> <content>
%groupusers <group-id-or-name>
%groupleave <group-id-or-name>
%groupmessage <group-id-or-name> <message-id>
%exit
```

## Run the client

With a server already running, open a second terminal in this directory.

### Windows (PowerShell / Command Prompt)

```powershell
python src\client\bulletin_client.py
```

### macOS and Linux

```bash
python3 src/client/bulletin_client.py
```

> **Note:** Use `py` instead of `python` on Windows if `python` is not on your PATH.

The client prompts for a username after connecting and handles all commands
listed above.

### Example session

```text
> %connect localhost 5000
Enter username: alice
[info] Connected to localhost:5000 as 'alice'

> %join
------------------------------------------------------------
  Joined 'public'
------------------------------------------------------------
  Members: alice

> %post Greetings Hello from alice!
[posted] board='public' id=1 subject='Greetings' at 2026-11-20T14:00:00Z

> %groups
------------------------------------------------------------
  Available Groups
------------------------------------------------------------
   1. general
   2. sports
   3. study
   4. gaming
   5. tech

> %groupjoin general
------------------------------------------------------------
  Joined 'general'
------------------------------------------------------------
  Members: alice

> %grouppost general News Big update today
[posted] board='general' id=2 subject='News' at 2026-11-20T14:01:00Z

> %exit
[info] Disconnected from server
```

## Run the tests

### Client tests

```powershell
python test\client\test_client.py
```

Or from the project root:

```bash
python test/client/test_client.py
```

## Language split and extra credit

The server is written in Java and the client is written in Python, satisfying
the different-language requirement for the 5% extra credit.

## Protocol summary

- Transport: TCP unicast sockets, port 5000 by default.
- Framing: four-byte big-endian signed integer length prefix followed by UTF-8 text.
- User-entered fields (usernames, subjects, content) are Base64-encoded.
- Responses: `RESPONSE|<requestId>|OK|<base64JSON>` or `RESPONSE|<requestId>|ERROR|<base64JSON>`.
- Push events: `EVENT|<base64JSON>`.

## Known issues and design notes

- The client event display is deferred to the main thread between commands to
  avoid interleaved output with the prompt.  Events that arrive while the user
  is typing will appear on the next Enter press.
- Private group IDs are accepted as either numeric IDs (1–5) or case-insensitive
  names (e.g. `general`, `GENERAL`).
- Pipe characters in subjects or content are safe because they are Base64-encoded
  before transmission.

## Server implementation

The server keeps board state in memory and supports registration, public and
private membership, message posting and lookup, user lists, join/leave events,
duplicate-name rejection, private-board isolation, and disconnect cleanup.
Message IDs are unique for the lifetime of the server process.
