package server;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;

/**
 * Shared TCP framing primitive for the server.
 *
 * A frame is a signed, four-byte big-endian length followed by UTF-8 text.
 */
public final class FrameCodec {
    public static final int MAX_FRAME_SIZE = 16 * 1024 * 1024;

    private FrameCodec() {
    }

    public static String readFrame(DataInputStream input) throws IOException {
        final int length;
        try {
            length = input.readInt();
        } catch (EOFException exception) {
            return null;
        }
        if (length < 0 || length > MAX_FRAME_SIZE) {
            throw new IOException("Frame length must be between 0 and " + MAX_FRAME_SIZE);
        }
        byte[] payload = input.readNBytes(length);
        if (payload.length != length) {
            throw new EOFException("Incomplete frame payload");
        }
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(payload))
                    .toString();
        } catch (CharacterCodingException exception) {
            throw new IOException("Frame payload is not valid UTF-8", exception);
        }
    }

    public static void writeFrame(DataOutputStream output, String payload) throws IOException {
        byte[] encoded = payload.getBytes(StandardCharsets.UTF_8);
        if (encoded.length > MAX_FRAME_SIZE) {
            throw new IOException("Frame payload exceeds " + MAX_FRAME_SIZE + " bytes");
        }
        output.writeInt(encoded.length);
        output.write(encoded);
        output.flush();
    }
}
