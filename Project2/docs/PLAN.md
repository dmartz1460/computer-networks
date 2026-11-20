# Project 2 Implementation Plan

## 1. Goal and Assumptions

Build one console client-server bulletin board that supports both public and private group boards in the same server process.

- Server: Java
- Client: Python
- Networking: TCP unicast sockets only
- Java standard library for server
- Python standard library for client
- No GUI in this plan
- Target structure:

  ```text
  Project2/
  |-- ASSIGNMENT.md
  |-- NOTES.md
  |-- PLAN.md
  |-- Project2-<LastName>-<Partner1LastName>-<Partner2LastName>/
      |-- src/
      |   |-- server/
      |   |   `-- ... Java source
      |   `-- client/
      |       `-- ... Python source
      |-- README.md
  ```

The submission directory name and README name fields must use the two team members' surnames. Do not add package dependencies for networking or replace raw TCP sockets with frameworks.

## 2. Final Command and Protocol Contract

Both developers must treat this section as the interface specification. The server and client may be implemented concurrently only against this contract.

### 2.1 Transport framing

- Use TCP.
- Server listen port: `5000` by default.
- Client connects with `%connect <host> <port>`; if no port is provided, use `5000`.
- Every message, in either direction, is a four-byte, network byte-order, big-endian signed integer length followed by exactly that many bytes of UTF-8 text.
- Payload text is Base64 for user-entered text fields. Base64 encoding must be handled by language standard libraries.
- New command payload fields are separated by `|`; the protocol must reject extra or missing fields clearly.
- Request IDs are decimal strings. The server echoes a request ID in every direct response.

### 2.2 Fixed groups

The server owns these five private groups:

| ID | Name |
|---|---|
| 1 | general |
| 2 | sports |
| 3 | study |
| 4 | gaming |
| 5 | tech |

The public board has reserved ID `public`.

### 2.3 Requests

Use these request payload formats:

| Command | Payload format | Meaning |
|---|---|---|
| `REGISTER` | `REGISTER|<requestId>|<base64UserName>` | Register once after connecting |
| `JOIN_PUBLIC` | `JOIN_PUBLIC|<requestId>` | Join the public board |
| `LEAVE_PUBLIC` | `LEAVE_PUBLIC|<requestId>` | Leave the public board |
| `POST_PUBLIC` | `POST_PUBLIC|<requestId>|<base64Subject>|<base64Content>` | Post on public board |
| `USERS_PUBLIC` | `USERS_PUBLIC|<requestId>` | List public-board users |
| `MESSAGE_PUBLIC` | `MESSAGE_PUBLIC|<requestId>|<messageId>` | Get public message content |
| `LIST_GROUPS` | `LIST_GROUPS|<requestId>` | Return all five groups |
| `JOIN_GROUP` | `JOIN_GROUP|<requestId>|<groupIdOrName>` | Join a private group |
| `LEAVE_GROUP` | `LEAVE_GROUP|<requestId>|<groupIdOrName>` | Leave a private group |
| `POST_GROUP` | `POST_GROUP|<requestId>|<groupIdOrName>|<base64Subject>|<base64Content>` | Post to a private group |
| `USERS_GROUP` | `USERS_GROUP|<requestId>|<groupIdOrName>` | List users in a private group |
| `MESSAGE_GROUP` | `MESSAGE_GROUP|<requestId>|<groupIdOrName>|<messageId>` | Get private message content |
| `DISCONNECT` | `DISCONNECT|<requestId>` | Gracefully disconnect |

All request text fields are case-sensitive. Group ID/name matching is case-insensitive only for names.

### 2.4 Direct responses

Direct responses use:

```text
RESPONSE|<requestId>|<status>|<base64Payload>
```

- `status` is `OK` or `ERROR`.
- `base64Payload` is one field encoded as Base64. If a response contains structured data, Base64-encode JSON text. This uses only the standard JSON library in Java/Python and no third-party networking or JSON package.
- Error payload shape:

  ```json
  {"code":"NOT_MEMBER","message":"You are not a member of that group"}
  ```

The server should cover at least these error codes: `NOT_CONNECTED`, `NAME_TAKEN`, `NOT_REGISTERED`, `ALREADY_MEMBER`, `NOT_MEMBER`, `INVALID_GROUP`, `INVALID_MESSAGE`, `INVALID_COMMAND`, and `DISCONNECTED`.

### 2.5 Push notifications

The server sends:

```text
EVENT|<base64Payload>
```

with payload JSON:

```json
{"type":"USER_JOINED","board":"public","user":"alice","users":["alice","bob"]}
```

Use these event types:

| Event | Required fields |
|---|---|
| `USER_JOINED` | board, user, users |
| `USER_LEFT` | board, user, users |
| `MESSAGE_POSTED` | board, messageId, sender, subject, postDate |
| `GROUP_JOINED` | board, user, users |
| `GROUP_LEFT` | board, user, users |

Only public-board members receive public events. Only private-group members receive private events. The joiner's direct response, not a pushed join event, provides the new member with the joining snapshot.

### 2.6 JSON response shapes

The server must use stable JSON objects:

- Registration/listening:
  ```json
  {"username":"alice"}
  ```
- Public or group join:
  ```json
  {"board":"public","users":["alice","bob"],"messages":[{"id":"1","sender":"alice","subject":"Hello","postDate":"2026-11-18T14:18:49Z"}]}
  ```
- Public/group user list:
  ```json
  {"board":"public","users":["alice","bob"]}
  ```
- Groups:
  ```json
  {"groups":[{"id":1,"name":"general"},{"id":2,"name":"sports"},{"id":3,"name":"study"},{"id":4,"name":"gaming"},{"id":5,"name":"tech"}]}
  ```
- Post:
  ```json
  {"board":"public","messageId":"1","subject":"Hello","postDate":"2026-11-18T14:18:49Z"}
  ```
- Message lookup:
  ```json
  {"id":"1","sender":"alice","subject":"Hello","postDate":"2026-...Z","content":"Message body"}
  ```
- Leave or disconnect:
  ```json
  {"board":"public","username":"alice","users":["bob"]}
  ```

The public join and private group join snapshots include at most the two most recent message summaries. Other message summaries may be retrieved by post events; full content is still retrieved only by message ID.

### 2.7 Message identity and dates

- Message IDs are integers, unique across the entire server process, encoded as decimal strings.
- Use UTC ISO 8601 with a `Z` suffix.
- A message belongs to exactly one board and is only exposed to members of that board.
- Store in memory only; persistence is not required unless the team explicitly adds it as a later enhancement.

## 3. Shared Core Principles

### Server invariants

- Keep one `ClientSession` for each socket connection.
- Keep one public board plus exactly five private boards.
- A username is registered once and must be unique among currently connected users.
- Every membership change and message is synchronized under one shared server lock.
- Never expose private board membership or message data to a user not in that board.
- A client may hold public membership and any number of private memberships concurrently.
- A request handler only queues outbound frames; it must not assume another thread can unsafely mutate a socket.
- On disconnect, remove the user from every board and notify remaining public/private members.
- Every socket read/write has an appropriate timeout or shutdown path. Socket exceptions must not crash the server.

### Client invariants

- Maintain one reader thread and one writer thread must not write concurrently from both UI and reader paths.
- The simplest safe design: a single dedicated outbound queue and one receiver thread; only the main thread/command loop formats and queues requests.
- The receiver thread must handle `RESPONSE` frames and `EVENT` frames; it must resolve a pending response only by request ID.
- Never print or write server payloads without decoding Base64 and JSON.
- On `%exit`, send `DISCONNECT`, wait briefly for acknowledgement, close socket, and stop receiver thread.
- If the socket disconnects unexpectedly, print a clear error and return to `%connect`-ready state.

## 4. Work Division

### Person A - Server Engineer (Java)

Own all files under `src/server/` and server tests.

1. Create a Java project-free layout using `.java` files and `javac`.
2. Implement `BulletinServer.java`:
   - Parse `--port` and optional default host behavior.
   - Create `ServerSocket` on the configured non-system port.
   - Accept connections forever.
   - Start `ClientHandler` per connection.
   - Catch accept/socket failures at a level that lets the server shut down cleanly.
3. Implement `ClientHandler.java`:
   - Read exact frame length and UTF-8 payload.
   - Parse request fields.
   - Dispatch every command from section 2.
   - Send direct responses and queue push events safely.
   - Remove session state and notify boards on disconnect or socket failure.
4. Implement state classes:
   - `Session.java`: socket, username, public member flag, private memberships, output stream, registration state.
   - `Group.java` or `Board.java`: board ID, name, connected users, and ordered messages.
   - `Message.java`: ID, sender, UTC date, subject, content.
   - `ServerState.java`: shared lock, connected sessions, public board, five private boards, next message ID.
   - Atomic operation methods for register, join, leave, post, and lookup.
5. Synchronize all state operations and outbound notification fanout while holding the shared lock.
6. Implement join snapshots with at most two recent message summaries.
7. Implement user leave notifications for public and private boards.
8. Implement Base64 payload encoding and JSON serialization/deserialization manually or with standard-library-compatible small helpers.
9. Development may use server-only smoke tests or automated protocol tests under `test/`; test files are not final submission artifacts.
10. Add server comments at synchronization boundaries and protocol parsing decisions, but keep method names and variables descriptive.

Avoid editing `src/client/` except to fix a mutually agreed protocol mismatch.

### Person B - Client Engineer (Python)

Own all files under `src/client/` and client tests.

1. Create `bulletin_client.py` as the executable entry point.
2. Implement `ConsoleApp.py` or a single module with clear classes:
   - `ProtocolClient`: socket, frame reads/writes, request IDs, pending responses, receiver thread.
   - `CommandParser`: validates and splits `%` commands.
   - `ConsoleUi`: prompts and formatted output.
3. Implement the complete command set:
   - `%connect`
   - `%join`
   - `%post`
   - `%users`
   - `%leave`
   - `%message`
   - `%groups`
   - `%groupjoin`
   - `%grouppost`
   - `%groupusers`
   - `%groupleave`
   - `%groupmessage`
   - `%exit`
4. Register a username immediately after a successful connection:
   - The client may prompt `Enter username:`.
   - If `NAME_TAKEN`, show the error and prompt again.
   - Do not send board commands until registration succeeds.
5. Use newline-free console rendering that clearly separates direct responses and server events.
6. Implement Base64 and JSON parsing using Python standard libraries.
7. Implement one pending-response dictionary keyed by request ID.
8. Implement a bounded receive timeout or socket shutdown check so `%exit` never hangs.
9. Print message summaries and full content in a readable format:
   - Summary: `Message ID | Sender | Post Date | Subject`
   - Content: include ID, sender, date, subject, and body.
10. Format `NOT_MEMBER`, `NAME_TAKEN`, and malformed server payload errors without crashing.

Avoid editing `src/server/` except to fix a mutually agreed protocol mismatch.

## 5. Shared Files and Merge Ownership

Assign these files exclusively:

- Person A: `src/server/**` and development server tests, server README section.
- Person B: `src/client/**` and development client tests, client README section.
- Both share a review of `README.md`, but only Person A performs initial server/build documentation and only Person B performs initial run/client documentation.
- Only Person A creates protocol type constants in Java? Avoid duplicate protocol source of truth. Person B should implement the contract from `PLAN.md`, not create its own protocol specification.
- Both inspect and update `PROJECT2/.../README.md` by separate small patches or at the checkpoint merge.

If a protocol mismatch is discovered, add a dated short change note to `PLAN.md`, update this contract first, and then change both sides in separate commits.

## 6. Implementation Sequence

### Phase 0 - Checkpoint 1 (team merge)

Both developers meet for 20-30 minutes.

- Confirm Java/Python toolchains are installed.
- Confirm Java server and Python client entry points.
- Agree on submission directory and port `5000`.
- Confirm protocol section 2 is copied exactly into implementations.
- Person A creates server skeleton.
- Person B creates client skeleton and frame codec.
- Merge skeleton to a shared branch.
- Add concise README build and run heading.

Do not proceed past this checkpoint with incompatible frame or field formats.

### Phase 1 - Parallel implementation

Person A:

- Implement server socket, session, boards, in-memory state, public join/leave/post/list/message.
- Implement private-group join/leave/post/list/message.
- Development may add server unit tests for state operations. Do not include test files in the final submission.

Person B:

- Implement socket frame transport.
- Implement command parser and console UI.
- Implement all public and private commands.
- Development may add client parser and payload rendering tests.
- Development mock server socket tests may validate direct-response and event handling.
- Do not include test files in the final submission.
Development tests are not part of the final submission unless the team later explicitly decides otherwise.

There should be no shared-file edits during this phase.

### Phase 2 - Checkpoint 2 (integration)

Meet for 30-60 minutes.

- Start server.
- Run one public board and two private-board scenarios.
- Verify frames at packet level using server/client logs.
- Resolve protocol mismatches only.
- Merge server and client branches.
- Tag the commit `project2-part1-part2-integration`.

### Phase 3 - Hardening

Person A:

- Test disconnection cleanup.
- Test concurrent posts and joins.
- Test malformed payloads.
- Test username uniqueness and private isolation.

Person B:

- Test missing arguments and unknown commands.
- Test Base64 subjects and content with spaces and pipe characters.
- Test unexpected disconnect behavior.
- Test event rendering while waiting for a response.

### Phase 4 - Checkpoint 3 (acceptance)

Meet for 30-60 minutes.

- Execute the acceptance matrix below.
- Write README issues and fixes.
- Review no-binary and submission structure.
- Create final zip outside the repository.

## 7. AI-Agent Implementation Instructions

For every coding task:

1. Read `ASSIGNMENT.md`, `NOTES.md`, and this `PLAN.md`.
2. Implement only the ownership area assigned in section 4.
3. Search the worktree for an existing helper before creating another utility.
4. Use descriptive variable and method names.
5. Add comments only for non-obvious synchronization, framing, or protocol behavior.
6. Do not add third-party networking libraries or GUI code.
7. Do not modify the other developer's files.
8. Use standard library JSON/Base64/UTF-8 support.
9. Handle exceptions explicitly and print an actionable error.
10. Never log a password or sensitive socket data. This project has no authentication.
11. Run the smallest relevant test after each coherent change.
12. Update the relevant README section after adding commands or build/run steps.
13. Stop and report if an implementation decision is ambiguous; do not silently alter the protocol.
14. Before completion, show `git diff --stat`, `git diff --check`, and relevant test output.

## 8. Testing Plan

### Automated server tests

For development, Person A may add runnable tests under `test/server/` that cover:

- Frame encoding and decoding.
- Public join response and at-most-two-message snapshot.
- Public join/leave user notifications.
- Public post summary and full lookup.
- Public message lookup from a non-member is denied.
- Private group join and leave.
- Private board isolation: a member of one private group cannot read another.
- Private post summary and full lookup.
- Duplicate username.
- Duplicate public/private membership is rejected.
- Invalid group ID and invalid message ID.
- Disconnect cleanup from public and private boards.
- Concurrent public posts preserve unique IDs and do not lose messages.

Development tests may be Python scripts that compile or start Java child processes and use raw Python sockets. Tests are not part of the final submission unless the team later explicitly decides otherwise.

### Automated client tests

For development, Person B may add runnable tests under `test/client/` that cover:

- Frame length/header encoding.
- Base64 and JSON payload round trips.
- Parser accepts all required commands.
- Parser rejects missing arguments.
- Spaces in subject/content are preserved.
- Pipe characters in subject/content are preserved through Base64.
- Unexpected response code.
- Duplicate/unknown request ID handling.
- Receiver thread resolves direct responses.
- Event-only response is not mistaken for a direct response.
- `%exit` closes cleanly.

### Manual acceptance matrix

Run one server and at least two clients.

| Scenario | Required result |
|---|---|
| Server start | Server listens on port 5000 and accepts clients |
| Duplicate client names | Second same name is rejected with `NAME_TAKEN` |
| Public join | Both users receive join event; joiner receives user list and last two public summaries |
| Public post | Both public members receive summary event |
| Public message lookup | Requesting member receives full content |
| Public lookup denial | Non-member receives `NOT_MEMBER` |
| Public leave | Remaining members receive leave event |
| List groups | Client receives exactly five groups |
| Private join | Existing/private members receive group event |
| Private isolation | A user outside the group cannot read users or message content |
| Multiple memberships | One user can be public and private or join multiple private groups |
| Private post | Members receive private summary event; outside users receive no event |
| Private leave | Remaining group members receive leave event |
| Disconnect | Every board removes/disconnect-notifies user appropriately |
| Malformed command | Client shows clear usage or server sends `INVALID_COMMAND` |
| Pipe/special characters | Subject/content survives a round trip |

### Development verification commands

Document and verify the direct server commands:

```text
cd Project2-<Lastname>-<Partner...>
javac -d build/server src/server/*.java
java -cp build/server server.BulletinServer --port 5000
python src/client/bulletin_client.py
```

The README must include equivalent commands for Windows, macOS, and Linux and explain when `py` or `python` differs.

Development tests may be compiled and run only while implementing; remove or exclude them from the final submission directory and zip.

## 9. Error and Concurrency Checklist

Person A must test:

- Empty or oversized frame lengths.
- Disconnect while a handler is broadcasting.
- Double leave.
- Join to already joined board.
- Group ID outside `1-5`.
- Message ID not found.
- Message ID not in selected board.
- Socket read/write failure.
- Two clients post at exactly the same time.

Person B must test:

- No server running.
- Server closes after connected.
- `%connect` while already connected.
- `%post` with no subject.
- `%post` before joining public board.
- Unknown command.
- Extra arguments.
- Pipe characters in base64 fields.
- Non-UTF-8 or malformed server JSON.
- `%exit` before `%connect`.

## 10. README Requirements

The README must begin with:

```text
<Name of Partner 1>
<Name of Partner 2>
```

At the top, before Purpose or build instructions.

Then include:

- Purpose and supported features.
- Language split and extra-credit selection.
- Protocol summary.
- Prerequisites.
- Exact compile/run commands.
- Complete console command list.
- Examples for connecting, joining, posting, private groups, and exit.
- Known issues and how they were handled.
- Division or contribution notes if the team chooses to include them.

No binaries should be committed or included in the submission zip.

## 11. Submission Checklist

- Both student names at README top.
- Source under one submission directory.
- Server and client source included.
- Exact cross-platform compile/run steps included.
- README complete.
- No `.class`, `__pycache__`, virtual environment, executable binary, development test files, shell launcher, or ZIP in the final source or submission.
- Server run on non-system port.
- Public and private flows work in a single server process.
- Both languages are present and the client/server communicate over TCP.
- Final tree and zip contain no GUI code or GUI dependency unless a future explicit task adds it.
- Zip is created outside the repository, if Windows Explorer/PowerShell can name it.

## 12. Suggested Branch and Commit Strategy

- Branch `main` or `master` contains the skeleton only.
- Person A branch: `feature/server-core`
- Person B branch: `feature/python-client`
- Merge at Checkpoint 1.
- Person A branch: `feature/server-part1-part2`
- Person B branch: `feature/client-console`
- Merge at Checkpoint 2 only for integration.
- Final branch: `feature/project2-hardening` or a shared review branch.
- Commit in small coherent units.
- At merge, resolve protocol mismatches in contract or code; do not alter only one side.

## 13. Day-Level Target

This plan is designed for two developers to complete in a few days:

- Day 1 morning: Checkpoint 1 and skeleton.
- Day 1 afternoon through Day 2: parallel core implementation.
- Day 2 end: Checkpoint 2 integration.
- Day 3: hardening and edge cases.
- Day 3 end or Day 4: Checkpoint 3 acceptance and README/submission cleanup.

No day estimate is more important than verifying the acceptance matrix.
