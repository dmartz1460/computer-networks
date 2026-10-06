# Project 1 — Multi-Threaded Web Server with FTP Integration

**Dylan Martz — Computer Networks**

## Purpose

This project implements a simple HTTP web server in Java that serves static files (HTML, images, GIFs) to a web browser. When a requested text file is not found locally, the server automatically retrieves it from a local FTP server before serving it to the client. The main web page (`index.HTML`) uses JavaScript to fetch and display all content — text, images, and GIFs — inline in the browser.

## How It Works

1. The web server listens on **port 6789** for incoming HTTP requests.
2. Each request is handled in a **separate thread**, allowing the server to process multiple clients concurrently.
3. When a file is requested:
   - If the file **exists locally**, the server reads it from disk and responds with `200 OK`.
   - If the file is a **text file (.txt) that doesn't exist locally**, the server connects to a local FTP server, downloads the file, saves it to disk, and then serves it with `200 OK`.
   - If the file is **any other type and doesn't exist**, the server responds with `404 Not Found`.
4. The `index.HTML` page uses `fetch()` to request `text.txt`, `image1.jpg`, and `click.gif` from the server, rendering all three inline in the browser.

## Project Structure

```
Project1/
├── index.HTML                  # Main web page served to the browser
├── text.txt                    # Text file (fetched from FTP on first request)
├── image1.jpg                  # JPEG image served by the web server
├── click.gif                   # GIF image served by the web server
├── README.md                   # This file
└── webserver/
    ├── WebServer.java          # Web server entry point and HTTP request handler
    └── FtpClient.java          # FTP client for retrieving remote files
```

## File Descriptions

### `webserver/WebServer.java`

Contains two classes:

- **`WebServer`** — The main class. Creates a `ServerSocket` on port 6789 and enters an infinite loop, accepting TCP connections and spawning a new thread for each incoming request.

- **`HttpRequest`** — Implements `Runnable` to handle a single HTTP request on its own thread. Parses the HTTP request line and headers, looks up the requested file on disk, constructs an HTTP response with proper status line (`HTTP/1.1 200 OK` or `HTTP/1.1 404 Not Found`), content type, and content length headers, and writes the response back to the client. If a `.txt` file is not found locally, it delegates to `FtpClient` to download the file from the FTP server before serving it. Also includes a helper method `contentType()` that maps file extensions (`.html`, `.jpg`, `.gif`, `.txt`) to MIME types.

### `webserver/FtpClient.java`

An FTP client that communicates with a local FTP server (on port 21) using raw FTP protocol commands over a TCP control connection. Key operations:

- **`connect(username, password)`** — Opens a control connection to the FTP server and authenticates with `USER` and `PASS` commands.
- **`getFile(file_name)`** — Switches to passive mode (`PASV`), opens a data connection, sends a `RETR` command to download the file, and saves it locally using `createLocalFile()`.
- **`disconnect()`** — Closes the control connection.

### `index.HTML`

The main web page served by the web server. Uses three JavaScript `fetch()` calls to request content from the server:

- Fetches `text.txt` and displays its contents in a `<pre>` element.
- Fetches `image1.jpg` and renders it as an `<img>` element.
- Fetches `click.gif` and renders it as an `<img>` element.

## FTP Server

The FTP Server that hosts the missing `text.txt` file is ran using a Docker Container through a WSL2 terminal instance. FileZilla is used as an FTP Client to upload the missing `text.txt` file to the server.

## How to Run

From the `Project1/` directory:

```bash
# Compile
javac webserver/WebServer.java webserver/FtpClient.java

# Run
java webserver.WebServer
```

Then open a browser and navigate to: **http://localhost:6789/index.HTML**
