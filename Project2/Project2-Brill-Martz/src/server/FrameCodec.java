package server;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * Shared TCP framing primitive for the server.
 *
 * A frame is a signed, four-byte big-endian length followed by UTF-8 text.
 */
public final class FrameCodec {
    private FrameCodec() {
    }

    public static String readFrame(DataInputStream input) throws IOException {
        final int length;
        try {
            length = input.readInt();
        } catch (EOFException exception) {
            return null;
        }
        if (length < 0) {
            throw new IOException("Frame length cannot be negative");
        }
        byte[] payload = input.readNBytes(length);
        if (payload.length != length) {
            throw new EOFException("Incomplete frame payload");
        }
        return new String(payload, StandardCharsets.UTF_8);
    }

    public static void writeFrame(DataOutputStream output, String payload) throws IOException {
        byte[] encoded = payload.getBytes(StandardCharsets.UTF_8);
        output.writeInt(encoded.length);
        output.write(encoded);
        output.flush();
    }
}
