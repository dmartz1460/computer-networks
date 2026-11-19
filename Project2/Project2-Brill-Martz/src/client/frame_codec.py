"""TCP framing helpers shared by the Python client."""

import socket


HEADER_SIZE = 4
MAX_FRAME_SIZE = 16 * 1024 * 1024


def encode_frame(payload: str) -> bytes:
    """Encode UTF-8 text as a four-byte big-endian length-prefixed frame."""
    encoded = payload.encode("utf-8")
    if len(encoded) > MAX_FRAME_SIZE:
        raise ValueError("Frame payload is too large")
    return len(encoded).to_bytes(HEADER_SIZE, "big", signed=True) + encoded


def _read_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise EOFError("Socket closed while reading a frame")
        chunks.extend(chunk)
    return bytes(chunks)


def read_frame(sock: socket.socket) -> str:
    """Read one length-prefixed UTF-8 frame from a connected socket."""
    length = int.from_bytes(_read_exact(sock, HEADER_SIZE), "big", signed=True)
    if length < 0 or length > MAX_FRAME_SIZE:
        raise ValueError("Invalid frame length")
    return _read_exact(sock, length).decode("utf-8")
