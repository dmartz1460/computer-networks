package server;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** Membership and ordered messages for one public or private board. */
public final class Board {
    private final String id;
    private final String name;
    private final boolean publicBoard;
    private final Set<Session> members = new LinkedHashSet<>();
    private final List<Message> messages = new ArrayList<>();

    public Board(String id, String name, boolean publicBoard) {
        this.id = id;
        this.name = name;
        this.publicBoard = publicBoard;
    }

    public String id() {
        return id;
    }

    public String name() {
        return name;
    }

    public boolean isPublicBoard() {
        return publicBoard;
    }

    public Set<Session> members() {
        return members;
    }

    public List<Message> messages() {
        return messages;
    }

    public List<Session> memberSnapshot() {
        return new ArrayList<>(members);
    }

    public List<Message> recentMessages(int limit) {
        int start = Math.max(0, messages.size() - limit);
        return Collections.unmodifiableList(new ArrayList<>(messages.subList(start, messages.size())));
    }
}
