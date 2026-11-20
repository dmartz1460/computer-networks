package server;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;

/** Entry point for the bulletin board server. */
public final class BulletinServer {
    public static final int DEFAULT_PORT = 5000;

    private BulletinServer() {
    }

    public static void main(String[] args) throws IOException {
        int port = parsePort(args);
        try (ServerSocket serverSocket = new ServerSocket(port)) {
            Runtime.getRuntime().addShutdownHook(new Thread(() -> closeQuietly(serverSocket)));
            System.out.println("Bulletin server listening on port " + serverSocket.getLocalPort());
            ServerState state = new ServerState();
            while (!serverSocket.isClosed()) {
                Socket socket = null;
                try {
                    socket = serverSocket.accept();
                    ClientHandler handler = new ClientHandler(socket, state);
                    handler.setDaemon(true);
                    handler.start();
                } catch (IOException exception) {
                    if (socket != null) {
                        closeQuietly(socket);
                    }
                    if (!serverSocket.isClosed()) {
                        System.err.println("Unable to accept client: " + exception.getMessage());
                    }
                }
            }
        }
    }

    private static int parsePort(String[] args) {
        if (args.length == 0) {
            return DEFAULT_PORT;
        }
        if (args.length == 2 && "--port".equals(args[0])) {
            try {
                int port = Integer.parseInt(args[1]);
                if (port > 0 && port <= 65535) {
                    return port;
                }
            } catch (NumberFormatException ignored) {
                // Report one consistent usage message below.
            }
        }
        throw new IllegalArgumentException(
                "Usage: java server.BulletinServer [--port <1-65535>]");
    }

    private static void closeQuietly(ServerSocket serverSocket) {
        try {
            serverSocket.close();
        } catch (IOException ignored) {
            // The process is already shutting down.
        }
    }

    private static void closeQuietly(Socket socket) {
        try {
            socket.close();
        } catch (IOException ignored) {
            // The connection could not be initialized.
        }
    }
}
