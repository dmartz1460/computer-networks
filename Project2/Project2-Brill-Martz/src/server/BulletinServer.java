package server;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;

/**
 * Phase 0 server entry point. Feature dispatch is added in Phase 1.
 */
public final class BulletinServer {
    private static final int DEFAULT_PORT = 5000;

    private BulletinServer() {
    }

    public static void main(String[] args) throws IOException {
        int port = parsePort(args);
        try (ServerSocket serverSocket = new ServerSocket(port)) {
            System.out.println("Bulletin server listening on port " + port);
            while (!serverSocket.isClosed()) {
                Socket client = serverSocket.accept();
                Thread handler = new Thread(() -> handleConnection(client), "bulletin-client");
                handler.start();
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
                // Fall through to the actionable usage error below.
            }
        }
        throw new IllegalArgumentException("Usage: java server.BulletinServer [--port <1-65535>]");
    }

    private static void handleConnection(Socket client) {
        try (Socket socket = client;
             DataInputStream input = new DataInputStream(socket.getInputStream());
             DataOutputStream output = new DataOutputStream(socket.getOutputStream())) {
            while (FrameCodec.readFrame(input) != null) {
                FrameCodec.writeFrame(output, "RESPONSE|0|ERROR|UGhhc2UgMCA6IGNvbW1hbmRzIG5vdCBpbXBsZW1lbnRlZA==");
            }
        } catch (IOException exception) {
            System.err.println("Client connection ended: " + exception.getMessage());
        }
    }
}
