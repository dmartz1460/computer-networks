package server;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.io.IOException;

/** Shared in-memory state. Callers hold this object's monitor for every mutation and notification. */
public final class ServerState {
    private final Board publicBoard = new Board("public", "public", true);
    private final Map<String, Board> groups = new LinkedHashMap<>();
    private final Map<Session, Boolean> sessions = new LinkedHashMap<>();
    private long nextMessageId = 1;

    public ServerState() {
        List<String> names = Arrays.asList("general", "sports", "study", "gaming", "tech");
        for (int index = 0; index < names.size(); index++) {
            String id = Integer.toString(index + 1);
            groups.put(id, new Board(id, names.get(index), false));
        }
    }

    public synchronized void addSession(Session session) {
        sessions.put(session, Boolean.TRUE);
    }

    public synchronized boolean register(Session session, String username) {
        if (session.isRegistered() || username.isEmpty()) {
            return false;
        }
        for (Session current : sessions.keySet()) {
            if (current.isRegistered() && current.username().equals(username)) {
                return false;
            }
        }
        session.register(username);
        return true;
    }

    public synchronized Board findGroup(String value) {
        Board byId = groups.get(value);
        if (byId != null) {
            return byId;
        }
        for (Board group : groups.values()) {
            if (group.name().equalsIgnoreCase(value)) {
                return group;
            }
        }
        return null;
    }

    public synchronized List<Board> groups() {
        return new ArrayList<>(groups.values());
    }

    public synchronized Board publicBoard() {
        return publicBoard;
    }

    public synchronized boolean join(Session session, Board board) {
        if (board.members().contains(session)) {
            return false;
        }
        board.members().add(session);
        if (board.isPublicBoard()) {
            session.setPublicMember(true);
        } else {
            session.privateBoards().add(board);
        }
        return true;
    }

    public synchronized boolean leave(Session session, Board board) {
        if (!board.members().remove(session)) {
            return false;
        }
        if (board.isPublicBoard()) {
            session.setPublicMember(false);
        } else {
            session.privateBoards().remove(board);
        }
        return true;
    }

    public synchronized Message post(Session session, Board board, String subject, String content) {
        Message message = new Message(Long.toString(nextMessageId++), session.username(),
                Protocol.nowUtc(), subject, content);
        board.messages().add(message);
        return message;
    }

    public synchronized Message findMessage(Board board, String id) {
        for (Message message : board.messages()) {
            if (message.id().equals(id)) {
                return message;
            }
        }
        return null;
    }

    public synchronized void disconnect(Session session) {
        if (session.isDisconnected()) {
            return;
        }
        publicBoard.members().remove(session);
        for (Board group : groups.values()) {
            group.members().remove(session);
        }
        session.setPublicMember(false);
        session.privateBoards().clear();
        session.markDisconnected();
        sessions.remove(session);
    }

    public synchronized void removeFromBoard(Session session, Board board) {
        leave(session, board);
    }

    public synchronized void closeSessions() {
        for (Session session : new ArrayList<>(sessions.keySet())) {
            try {
                session.socket().close();
            } catch (IOException exception) {
                System.err.println("Unable to close client connection: " + exception.getMessage());
            }
            disconnect(session);
        }
    }
}
