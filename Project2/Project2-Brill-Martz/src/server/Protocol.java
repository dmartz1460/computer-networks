package server;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.List;

/** Protocol encoding helpers. JSON is serialized here because Java has no standard JSON API. */
public final class Protocol {
    private Protocol() {
    }

    public static String encodePayload(String json) {
        return Base64.getEncoder().encodeToString(json.getBytes(StandardCharsets.UTF_8));
    }

    public static String decodeBase64(String value) {
        return new String(Base64.getDecoder().decode(value), StandardCharsets.UTF_8);
    }

    public static String response(String requestId, boolean success, String json) {
        return "RESPONSE|" + requestId + "|" + (success ? "OK" : "ERROR") + "|" + encodePayload(json);
    }

    public static String event(String json) {
        return "EVENT|" + encodePayload(json);
    }

    public static String error(String code, String message) {
        return object("\"code\":\"" + escape(code) + "\",\"message\":\"" + escape(message) + "\"");
    }

    public static String object(String fields) {
        return "{" + fields + "}";
    }

    public static String quote(String value) {
        return "\"" + escape(value) + "\"";
    }

    public static String escape(String value) {
        StringBuilder escaped = new StringBuilder();
        for (int index = 0; index < value.length(); index++) {
            char character = value.charAt(index);
            switch (character) {
                case '"' -> escaped.append("\\\"");
                case '\\' -> escaped.append("\\\\");
                case '\b' -> escaped.append("\\b");
                case '\f' -> escaped.append("\\f");
                case '\n' -> escaped.append("\\n");
                case '\r' -> escaped.append("\\r");
                case '\t' -> escaped.append("\\t");
                default -> {
                    if (character < 0x20) {
                        escaped.append(String.format("\\u%04x", (int) character));
                    } else {
                        escaped.append(character);
                    }
                }
            }
        }
        return escaped.toString();
    }

    public static String stringArray(List<String> values) {
        StringBuilder result = new StringBuilder("[");
        for (int index = 0; index < values.size(); index++) {
            if (index > 0) {
                result.append(',');
            }
            result.append(quote(values.get(index)));
        }
        return result.append(']').toString();
    }

    public static String userNames(Board board) {
        return stringArray(board.memberSnapshot().stream().map(Session::username).toList());
    }

    public static String boardLabel(Board board) {
        return board.isPublicBoard() ? "public" : board.name();
    }

    public static String messageSummary(Message message) {
        return object("\"id\":" + quote(message.id())
                + ",\"sender\":" + quote(message.sender())
                + ",\"subject\":" + quote(message.subject())
                + ",\"postDate\":" + quote(message.postDate()));
    }

    public static String messageDetails(Message message) {
        return object("\"id\":" + quote(message.id())
                + ",\"sender\":" + quote(message.sender())
                + ",\"subject\":" + quote(message.subject())
                + ",\"postDate\":" + quote(message.postDate())
                + ",\"content\":" + quote(message.content()));
    }

    public static String nowUtc() {
        return Instant.now().toString();
    }
}
