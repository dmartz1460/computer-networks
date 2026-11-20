package server;

import java.io.DataOutputStream;
import java.io.IOException;
import java.net.Socket;
import java.util.HashSet;
import java.util.Set;

/** State associated with one connected socket. */
public final class Session {
    private final Socket socket;
    private final DataOutputStream output;
    private final Set<Board> privateBoards = new HashSet<>();
    private String username;
    private boolean registered;
    private boolean publicMember;
    private boolean disconnected;

    public Session(Socket socket, DataOutputStream output) {
        this.socket = socket;
        this.output = output;
    }

    public Socket socket() {
        return socket;
    }

    public String username() {
        return username;
    }

    public void register(String username) {
        this.username = username;
        this.registered = true;
    }

    public boolean isRegistered() {
        return registered;
    }

    public boolean isPublicMember() {
        return publicMember;
    }

    public void setPublicMember(boolean publicMember) {
        this.publicMember = publicMember;
    }

    public Set<Board> privateBoards() {
        return privateBoards;
    }

    public boolean isDisconnected() {
        return disconnected;
    }

    public void markDisconnected() {
        disconnected = true;
    }

    public synchronized void send(String payload) throws IOException {
        if (disconnected) {
            throw new IOException("Session is disconnected");
        }
        FrameCodec.writeFrame(output, payload);
    }
}
