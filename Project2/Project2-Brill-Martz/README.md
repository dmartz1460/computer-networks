# Project 2 Bulletin Board

Daniel Brill  
Dylan Martz

## Overview

This project is a console bulletin board with a Java TCP server and a Python
TCP client. The server supports a public board and five private group boards:
`general`, `sports`, `study`, `gaming`, and `tech`.

The server and client use only their language standard libraries. Communication
uses TCP sockets and the framing and request/response protocol specified in
[`../PLAN.md`](../PLAN.md), section 2.

## Requirements

- JDK 17 or newer
- Python 3.10 or newer
- No third-party packages

## Structure

```text
Project2-Brill-Martz/
|-- src/server/       Java server source
|-- src/client/       Python client source
|-- test/server/      Server tests
|-- test/client/      Client tests
|-- Makefile
|-- README.md
`-- run_server.sh
```

## Build and run

From this directory, the Makefile provides:

```text
make build
make run-server
make run-client
make test
make clean
```

On Windows PowerShell:

```powershell
Get-ChildItem src\server\*.java | ForEach-Object { $_.FullName } | Set-Content server_sources.txt
javac -d build\server @server_sources.txt
Remove-Item server_sources.txt
java -cp build\server server.BulletinServer --port 5000
py src\client\bulletin_client.py
py -m unittest discover -s test -p "test_*.py"
```

The default server port is `5000`. Use `--port <port>` to select another
non-system port.

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

## Testing

Run all tests with:

```powershell
py -m unittest discover -s test -p "test_*.py"
```

## Server implementation

The server keeps board state in memory and supports registration, public and
private membership, message posting and lookup, user lists, join/leave events,
duplicate-name rejection, private-board isolation, and disconnect cleanup.
Message IDs are unique for the lifetime of the server process.
