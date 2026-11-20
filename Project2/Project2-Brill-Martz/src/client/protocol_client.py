"""TCP transport layer for the bulletin board client.

Handles framing, Base64 encoding/decoding, request IDs, a background receiver
thread, and a pending-response registry keyed by request ID.  The main thread
only enqueues outbound frames; it never writes to the socket directly.
"""

import base64
import json
import socket
import struct
import threading
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Framing constants (must match server FrameCodec)
# ---------------------------------------------------------------------------
_HEADER_SIZE = 4          # four-byte big-endian signed int
_MAX_FRAME_BYTES = 16 * 1024 * 1024  # 16 MiB safety cap


# ---------------------------------------------------------------------------
# Low-level frame I/O helpers
# ---------------------------------------------------------------------------

def _read_exact(sock: socket.socket, size: int) -> bytes:
    """Read exactly *size* bytes from *sock*, raising EOFError on close."""
    buf = bytearray()
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise EOFError("Socket closed while reading")
        buf.extend(chunk)
    return bytes(buf)


def _read_frame(sock: socket.socket) -> str:
    """Read one length-prefixed UTF-8 frame and return it as a string."""
    raw_len = _read_exact(sock, _HEADER_SIZE)
    length = struct.unpack(">i", raw_len)[0]   # signed big-endian int
    if length < 0 or length > _MAX_FRAME_BYTES:
        raise ValueError(f"Invalid frame length: {length}")
    return _read_exact(sock, length).decode("utf-8")


def _build_frame(payload: str) -> bytes:
    """Encode a string as a length-prefixed UTF-8 frame."""
    encoded = payload.encode("utf-8")
    if len(encoded) > _MAX_FRAME_BYTES:
        raise ValueError("Payload too large to frame")
    return struct.pack(">i", len(encoded)) + encoded


# ---------------------------------------------------------------------------
# Base64 / JSON helpers
# ---------------------------------------------------------------------------

def b64_encode(text: str) -> str:
    """Base64-encode a UTF-8 string to an ASCII string."""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def b64_decode(text: str) -> str:
    """Decode a Base64 ASCII string to a UTF-8 string."""
    return base64.b64decode(text.encode("ascii")).decode("utf-8")


def parse_json_payload(b64_payload: str) -> dict:
    """Decode a Base64 field that wraps a JSON object."""
    return json.loads(b64_decode(b64_payload))


# ---------------------------------------------------------------------------
# ProtocolClient
# ---------------------------------------------------------------------------

class ProtocolClient:
    """Manages the TCP connection, framing, and concurrent receive loop.

    Public interface (called from the main thread only):
        connect / disconnect / send_request

    The receiver thread calls the *event_handler* callback for every
    unsolicited EVENT frame and resolves pending futures for RESPONSE frames.
    """

    def __init__(self, event_handler: Callable[[dict], None]) -> None:
        """
        Args:
            event_handler: Called from the receiver thread whenever an EVENT
                           frame arrives.  The argument is the decoded JSON dict.
        """
        self._event_handler = event_handler
        self._sock: Optional[socket.socket] = None
        self._send_lock = threading.Lock()          # one writer at a time
        self._next_request_id = 1
        self._id_lock = threading.Lock()

        # Maps request_id (str) -> threading.Event, and
        #           request_id (str) -> response dict (filled by receiver).
        self._pending: dict[str, threading.Event] = {}
        self._results: dict[str, dict] = {}
        self._pending_lock = threading.Lock()

        self._receiver: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, host: str, port: int) -> None:
        """Open a TCP connection to *host*:*port* and start the receiver thread."""
        if self._sock is not None:
            raise RuntimeError("Already connected; call disconnect first")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        self._sock = sock
        self._running = True
        self._receiver = threading.Thread(
            target=self._receive_loop,
            name="bulletin-receiver",
            daemon=True,
        )
        self._receiver.start()

    def disconnect(self) -> None:
        """Signal the receiver thread to stop and close the socket."""
        self._running = False
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        # Wake up any pending waiters so they don't block forever.
        with self._pending_lock:
            for event in self._pending.values():
                event.set()

    @property
    def connected(self) -> bool:
        return self._sock is not None

    # ------------------------------------------------------------------
    # Request/response
    # ------------------------------------------------------------------

    def _next_id(self) -> str:
        with self._id_lock:
            rid = str(self._next_request_id)
            self._next_request_id += 1
        return rid

    def send_request(self, payload: str, timeout: float = 10.0) -> dict:
        """Send *payload* to the server and block until the matching response arrives.

        Returns the decoded JSON response dict, or raises RuntimeError on
        timeout or unexpected disconnect.
        """
        if self._sock is None:
            raise RuntimeError("Not connected")

        # Register the pending slot before sending so we cannot miss a fast reply.
        rid = self._next_id()
        event = threading.Event()
        with self._pending_lock:
            self._pending[rid] = event
            self._results.pop(rid, None)

        # Insert the request ID into the payload at field index 1.
        # Payload format: "COMMAND|<rid>|..." – but callers pass "COMMAND|..."
        # so we splice in the ID.
        parts = payload.split("|", 1)
        framed_payload = parts[0] + "|" + rid + ("|" + parts[1] if len(parts) > 1 else "")

        frame = _build_frame(framed_payload)
        with self._send_lock:
            if self._sock is None:
                raise RuntimeError("Not connected")
            self._sock.sendall(frame)

        # Wait for the receiver thread to populate the result.
        if not event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(rid, None)
                self._results.pop(rid, None)
            raise TimeoutError(f"No response received within {timeout}s")

        with self._pending_lock:
            result = self._results.pop(rid, None)
            self._pending.pop(rid, None)

        if result is None:
            raise RuntimeError("Disconnected while waiting for a response")
        return result

    # ------------------------------------------------------------------
    # Receiver loop (runs in background thread)
    # ------------------------------------------------------------------

    def _receive_loop(self) -> None:
        """Read frames from the server until the connection closes."""
        sock = self._sock
        while self._running and sock is not None:
            try:
                raw = _read_frame(sock)
            except (EOFError, OSError, ValueError):
                break
            self._dispatch_frame(raw)

        # Socket is gone; signal disconnect to anyone waiting.
        self._running = False
        self._sock = None
        with self._pending_lock:
            for event in self._pending.values():
                event.set()
        # Notify the UI layer via a synthetic event.
        self._event_handler({"type": "_DISCONNECTED"})

    def _dispatch_frame(self, raw: str) -> None:
        """Route one received frame to either the pending registry or event handler."""
        parts = raw.split("|", 3)
        if not parts:
            return
        prefix = parts[0]

        if prefix == "RESPONSE" and len(parts) == 4:
            self._handle_response(parts)
        elif prefix == "EVENT" and len(parts) == 2:
            self._handle_event(parts[1])
        else:
            # Malformed frame – log and continue.
            print(f"[WARN] Unrecognised frame prefix or field count: {raw[:80]!r}")

    def _handle_response(self, parts: list[str]) -> None:
        """Decode a RESPONSE frame and wake the waiting main-thread caller."""
        _, request_id, status, b64_payload = parts
        try:
            payload_json = parse_json_payload(b64_payload)
        except Exception as decode_error:
            payload_json = {"_raw": b64_payload, "_error": str(decode_error)}

        result = {"requestId": request_id, "status": status, "payload": payload_json}

        with self._pending_lock:
            event = self._pending.get(request_id)
            if event is not None:
                self._results[request_id] = result
                event.set()
            else:
                # Unsolicited or duplicate response — just print a warning.
                print(f"[WARN] Response for unknown request ID {request_id!r} ignored")

    def _handle_event(self, b64_payload: str) -> None:
        """Decode an EVENT frame and pass the JSON dict to the event handler."""
        try:
            payload_json = parse_json_payload(b64_payload)
        except Exception as decode_error:
            print(f"[WARN] Could not decode event payload: {decode_error}")
            return
        self._event_handler(payload_json)
