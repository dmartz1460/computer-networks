package server;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.Socket;
import java.util.ArrayList;
import java.util.List;

/** Reads, validates, and dispatches requests for one client connection. */
public final class ClientHandler extends Thread {
    private final Socket socket;
    private final ServerState state;
    private final Session session;

    public ClientHandler(Socket socket, ServerState state) throws IOException {
        super("bulletin-client-" + socket.getRemoteSocketAddress());
        this.socket = socket;
        this.state = state;
        this.session = new Session(socket, new DataOutputStream(socket.getOutputStream()));
        state.addSession(session);
    }

    @Override
    public void run() {
        try (Socket client = socket;
             DataInputStream input = new DataInputStream(client.getInputStream())) {
            String request;
            while ((request = FrameCodec.readFrame(input)) != null) {
                dispatch(request);
                if (session.isDisconnected()) {
                    break;
                }
            }
        } catch (IOException exception) {
            if (!session.isDisconnected()) {
                System.err.println("Client connection ended: " + exception.getMessage());
            }
        } finally {
            cleanup();
        }
    }

    private void dispatch(String request) throws IOException {
        String[] fields = request.split("\\|", -1);
        if (fields.length == 0 || fields[0].isEmpty()) {
            sendError("0", "INVALID_COMMAND", "Command is missing");
            return;
        }
        String requestId = fields.length > 1 && fields[1].matches("\\d+")
                ? fields[1] : "0";
        if (fields.length < 2 || !fields[1].matches("\\d+")) {
            sendError(requestId, "INVALID_COMMAND", "Request ID must be a decimal string");
            return;
        }

        try {
            switch (fields[0]) {
                case "REGISTER" -> register(fields, requestId);
                case "JOIN_PUBLIC" -> joinPublic(fields, requestId);
                case "LEAVE_PUBLIC" -> leavePublic(fields, requestId);
                case "POST_PUBLIC" -> postPublic(fields, requestId);
                case "USERS_PUBLIC" -> usersPublic(fields, requestId);
                case "MESSAGE_PUBLIC" -> messagePublic(fields, requestId);
                case "LIST_GROUPS" -> listGroups(fields, requestId);
                case "JOIN_GROUP" -> joinGroup(fields, requestId);
                case "LEAVE_GROUP" -> leaveGroup(fields, requestId);
                case "POST_GROUP" -> postGroup(fields, requestId);
                case "USERS_GROUP" -> usersGroup(fields, requestId);
                case "MESSAGE_GROUP" -> messageGroup(fields, requestId);
                case "DISCONNECT" -> disconnect(fields, requestId);
                default -> sendError(requestId, "INVALID_COMMAND", "Unknown command");
            }
        } catch (IllegalArgumentException exception) {
            sendError(requestId, "INVALID_COMMAND", exception.getMessage());
        } catch (IllegalStateException exception) {
            sendError(requestId, "NOT_REGISTERED", "Register before using this command");
        }
    }

    private void register(String[] fields, String requestId) throws IOException {
        requireFieldCount(fields, 3);
        if (session.isRegistered()) {
            sendError(requestId, "ALREADY_REGISTERED", "This connection is already registered");
            return;
        }
        String username = Protocol.decodeBase64(fields[2]);
        if (username.isEmpty() || username.indexOf('|') >= 0) {
            sendError(requestId, "INVALID_COMMAND", "Username must be non-empty and cannot contain '|'");
            return;
        }
        synchronized (state) {
            if (!state.register(session, username)) {
                sendError(requestId, "NAME_TAKEN", "Username is already connected");
                return;
            }
            sendResponse(requestId, true, Protocol.object("\"username\":" + Protocol.quote(username)));
        }
    }

    private void joinPublic(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 2);
        joinBoard(state.publicBoard(), requestId, "USER_JOINED");
    }

    private void leavePublic(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 2);
        leaveBoard(state.publicBoard(), requestId, "USER_LEFT");
    }

    private void postPublic(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 4);
        post(state.publicBoard(), fields[2], fields[3], requestId);
    }

    private void usersPublic(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 2);
        users(state.publicBoard(), requestId);
    }

    private void messagePublic(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 3);
        message(state.publicBoard(), fields[2], requestId);
    }

    private void listGroups(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 2);
        StringBuilder groupsJson = new StringBuilder("[");
        List<Board> groups = state.groups();
        for (int index = 0; index < groups.size(); index++) {
            if (index > 0) {
                groupsJson.append(',');
            }
            Board group = groups.get(index);
            groupsJson.append(Protocol.object("\"id\":" + group.id()
                    + ",\"name\":" + Protocol.quote(group.name())));
        }
        groupsJson.append(']');
        sendResponse(requestId, true, Protocol.object("\"groups\":" + groupsJson));
    }

    private void joinGroup(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 3);
        Board group = findGroup(fields[2]);
        if (group == null) {
            sendError(requestId, "INVALID_GROUP", "Group does not exist");
            return;
        }
        joinBoard(group, requestId, "GROUP_JOINED");
    }

    private void leaveGroup(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 3);
        Board group = findGroup(fields[2]);
        if (group == null) {
            sendError(requestId, "INVALID_GROUP", "Group does not exist");
            return;
        }
        leaveBoard(group, requestId, "GROUP_LEFT");
    }

    private void postGroup(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 5);
        Board group = findGroup(fields[2]);
        if (group == null) {
            sendError(requestId, "INVALID_GROUP", "Group does not exist");
            return;
        }
        post(group, fields[3], fields[4], requestId);
    }

    private void usersGroup(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 3);
        Board group = findGroup(fields[2]);
        if (group == null) {
            sendError(requestId, "INVALID_GROUP", "Group does not exist");
            return;
        }
        users(group, requestId);
    }

    private void messageGroup(String[] fields, String requestId) throws IOException {
        requireRegistered();
        requireFieldCount(fields, 4);
        Board group = findGroup(fields[2]);
        if (group == null) {
            sendError(requestId, "INVALID_GROUP", "Group does not exist");
            return;
        }
        message(group, fields[3], requestId);
    }

    private void disconnect(String[] fields, String requestId) throws IOException {
        requireFieldCount(fields, 2);
        if (!session.isRegistered()) {
            sendError(requestId, "NOT_REGISTERED", "Register before disconnecting");
            return;
        }
        sendResponse(requestId, true, Protocol.object("\"username\":" + Protocol.quote(session.username())));
        cleanup();
    }

    private void joinBoard(Board board, String requestId, String eventType) throws IOException {
        synchronized (state) {
            if (board.members().contains(session)) {
                sendError(requestId, "ALREADY_MEMBER", "Already a member of this board");
                return;
            }
            List<Session> previousMembers = board.memberSnapshot();
            state.join(session, board);
            String snapshot = joinSnapshot(board);
            sendResponse(requestId, true, snapshot);
            notifyMembers(previousMembers, Protocol.event(joinEvent(eventType, board)));
        }
    }

    private void leaveBoard(Board board, String requestId, String eventType) throws IOException {
        synchronized (state) {
            if (!board.members().contains(session)) {
                sendError(requestId, "NOT_MEMBER", "You are not a member of that board");
                return;
            }
            state.leave(session, board);
            sendResponse(requestId, true, leaveResponse(board));
            notifyMembers(board.memberSnapshot(), Protocol.event(memberEvent(eventType, board)));
        }
    }

    private void post(Board board, String encodedSubject, String encodedContent, String requestId)
            throws IOException {
        synchronized (state) {
            if (!board.members().contains(session)) {
                sendError(requestId, "NOT_MEMBER", "You are not a member of that board");
                return;
            }
            String subject = Protocol.decodeBase64(encodedSubject);
            String content = Protocol.decodeBase64(encodedContent);
            if (subject.isEmpty() || content.isEmpty()) {
                sendError(requestId, "INVALID_MESSAGE", "Subject and content must be non-empty");
                return;
            }
            Message message = state.post(session, board, subject, content);
            String summary = Protocol.object("\"board\":" + Protocol.quote(Protocol.boardLabel(board))
                    + ",\"messageId\":" + Protocol.quote(message.id())
                    + ",\"subject\":" + Protocol.quote(message.subject())
                    + ",\"postDate\":" + Protocol.quote(message.postDate()));
            sendResponse(requestId, true, summary);
            String event = Protocol.event(Protocol.object("\"type\":\"MESSAGE_POSTED\","
                    + "\"board\":" + Protocol.quote(Protocol.boardLabel(board))
                    + ",\"messageId\":" + Protocol.quote(message.id())
                    + ",\"sender\":" + Protocol.quote(message.sender())
                    + ",\"subject\":" + Protocol.quote(message.subject())
                    + ",\"postDate\":" + Protocol.quote(message.postDate())));
            notifyMembers(board.memberSnapshot(), event);
        }
    }

    private void users(Board board, String requestId) throws IOException {
        synchronized (state) {
            if (!board.members().contains(session)) {
                sendError(requestId, "NOT_MEMBER", "You are not a member of that board");
                return;
            }
            sendResponse(requestId, true, Protocol.object("\"board\":"
                    + Protocol.quote(Protocol.boardLabel(board))
                    + ",\"users\":" + Protocol.userNames(board)));
        }
    }

    private void message(Board board, String messageId, String requestId) throws IOException {
        synchronized (state) {
            if (!board.members().contains(session)) {
                sendError(requestId, "NOT_MEMBER", "You are not a member of that board");
                return;
            }
            Message message = state.findMessage(board, messageId);
            if (message == null) {
                sendError(requestId, "INVALID_MESSAGE", "Message does not exist on this board");
                return;
            }
            sendResponse(requestId, true, Protocol.messageDetails(message));
        }
    }

    private String joinSnapshot(Board board) {
        StringBuilder messages = new StringBuilder("[");
        List<Message> recent = board.recentMessages(2);
        for (int index = 0; index < recent.size(); index++) {
            if (index > 0) {
                messages.append(',');
            }
            messages.append(Protocol.messageSummary(recent.get(index)));
        }
        messages.append(']');
        return Protocol.object("\"board\":" + Protocol.quote(Protocol.boardLabel(board))
                + ",\"users\":" + Protocol.userNames(board)
                + ",\"messages\":" + messages);
    }

    private String leaveResponse(Board board) {
        return Protocol.object("\"board\":" + Protocol.quote(Protocol.boardLabel(board))
                + ",\"username\":" + Protocol.quote(session.username())
                + ",\"users\":" + Protocol.userNames(board));
    }

    private String joinEvent(String eventType, Board board) {
        return memberEvent(eventType, board);
    }

    private String memberEvent(String eventType, Board board) {
        return Protocol.object("\"type\":" + Protocol.quote(eventType)
                + ",\"board\":" + Protocol.quote(Protocol.boardLabel(board))
                + ",\"user\":" + Protocol.quote(session.username())
                + ",\"users\":" + Protocol.userNames(board));
    }

    private void notifyMembers(List<Session> recipients, String event) {
        for (Session recipient : new ArrayList<>(recipients)) {
            try {
                recipient.send(event);
            } catch (IOException exception) {
                try {
                    recipient.socket().close();
                } catch (IOException closeException) {
                    System.err.println("Unable to close failed client connection: "
                            + closeException.getMessage());
                }
            }
        }
    }

    private Board findGroup(String value) {
        return state.findGroup(value);
    }

    private void cleanup() {
        synchronized (state) {
            if (session.isDisconnected()) {
                return;
            }
            List<Board> memberships = new ArrayList<>();
            if (session.isPublicMember()) {
                memberships.add(state.publicBoard());
            }
            memberships.addAll(session.privateBoards());
            for (Board board : memberships) {
                if (board.members().contains(session)) {
                    state.leave(session, board);
                    String eventType = board.isPublicBoard() ? "USER_LEFT" : "GROUP_LEFT";
                    notifyMembers(board.memberSnapshot(), Protocol.event(memberEvent(eventType, board)));
                }
            }
            state.disconnect(session);
        }
    }

    private void requireRegistered() {
        if (!session.isRegistered()) {
            throw new IllegalStateException("NOT_REGISTERED");
        }
    }

    private void requireFieldCount(String[] fields, int expected) {
        if (fields.length != expected) {
            throw new IllegalArgumentException("Expected " + expected + " fields");
        }
    }

    private void sendResponse(String requestId, boolean success, String json) throws IOException {
        session.send(Protocol.response(requestId, success, json));
    }

    private void sendError(String requestId, String code, String message) throws IOException {
        sendResponse(requestId, false, Protocol.error(code, message));
    }
}
