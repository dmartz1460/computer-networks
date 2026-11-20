package server;

/** Immutable message stored on exactly one board. */
public final class Message {
    private final String id;
    private final String sender;
    private final String postDate;
    private final String subject;
    private final String content;

    public Message(String id, String sender, String postDate, String subject, String content) {
        this.id = id;
        this.sender = sender;
        this.postDate = postDate;
        this.subject = subject;
        this.content = content;
    }

    public String id() {
        return id;
    }

    public String sender() {
        return sender;
    }

    public String postDate() {
        return postDate;
    }

    public String subject() {
        return subject;
    }

    public String content() {
        return content;
    }
}
