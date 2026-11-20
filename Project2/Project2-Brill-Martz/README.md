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

## Server implementation

The server keeps board state in memory and supports registration, public and
private membership, message posting and lookup, user lists, join/leave events,
duplicate-name rejection, private-board isolation, and disconnect cleanup.
Message IDs are unique for the lifetime of the server process.
