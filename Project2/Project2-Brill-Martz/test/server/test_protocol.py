import base64
import json
import os
import socket
import subprocess
import time
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def frame(payload):
    encoded = payload.encode("utf-8")
    return len(encoded).to_bytes(4, "big", signed=True) + encoded


def read_exact(connection, size):
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise EOFError("server closed the connection")
        data.extend(chunk)
    return bytes(data)


def read_frame(connection):
    size = int.from_bytes(read_exact(connection, 4), "big", signed=True)
    return read_exact(connection, size).decode("utf-8")


def encoded(value):
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


class ServerProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        cls.port = probe.getsockname()[1]
        probe.close()
        cls.process = subprocess.Popen(
            ["java", "-cp", os.path.join("build", "server"),
             "server.BulletinServer", "--port", str(cls.port)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                cls.alice = socket.create_connection(("127.0.0.1", cls.port), timeout=1)
                cls.alice.settimeout(2)
                return
            except OSError:
                if cls.process.poll() is not None:
                    raise RuntimeError(cls.process.stderr.read())
                time.sleep(0.05)
        raise RuntimeError("server did not start")

    @classmethod
    def tearDownClass(cls):
        for connection_name in ("alice", "bob", "outsider"):
            connection = getattr(cls, connection_name, None)
            if connection is not None:
                connection.close()
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.process.stdout.close()
        cls.process.stderr.close()

    @staticmethod
    def request(connection, payload):
        connection.sendall(frame(payload))
        while True:
            response = read_frame(connection)
            if response.startswith("RESPONSE|"):
                fields = response.split("|", 3)
                body = json.loads(base64.b64decode(fields[3]).decode("utf-8"))
                return fields[1], fields[2], body

    @staticmethod
    def event(connection):
        payload = read_frame(connection)
        if not payload.startswith("EVENT|"):
            raise AssertionError("expected event, received " + payload)
        return json.loads(base64.b64decode(payload.split("|", 1)[1]).decode("utf-8"))

    def test_public_flow_and_private_isolation(self):
        self.assertEqual(
            self.request(self.alice, "REGISTER|1|" + encoded("alice"))[2],
            {"username": "alice"},
        )
        self.assertEqual(self.request(self.alice, "JOIN_PUBLIC|2")[2]["users"], ["alice"])

        self.bob = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        self.bob.settimeout(2)
        self.assertEqual(self.request(self.bob, "REGISTER|3|" + encoded("bob"))[2]["username"], "bob")
        self.assertEqual(self.request(self.bob, "JOIN_PUBLIC|4")[2]["users"], ["alice", "bob"])
        self.assertEqual(self.event(self.alice)["type"], "USER_JOINED")

        status = self.request(
            self.alice, "POST_PUBLIC|5|" + encoded("Hello") + "|" + encoded("Body")
        )
        self.assertEqual(status[1], "OK")
        message_id = status[2]["messageId"]
        self.assertEqual(self.event(self.alice)["type"], "MESSAGE_POSTED")
        self.assertEqual(self.event(self.bob)["messageId"], message_id)
        self.assertEqual(self.request(self.bob, "MESSAGE_PUBLIC|6|" + message_id)[2]["content"], "Body")

        self.assertEqual(self.request(self.alice, "JOIN_GROUP|7|GENERAL")[2]["board"], "general")
        status = self.request(self.alice, "POST_GROUP|8|1|" + encoded("Private") + "|" + encoded("Secret"))
        private_id = status[2]["messageId"]
        self.assertEqual(self.request(self.bob, "USERS_GROUP|9|1")[1], "ERROR")
        self.assertEqual(self.request(self.bob, "MESSAGE_GROUP|10|1|" + private_id)[2]["code"], "NOT_MEMBER")

    def test_duplicate_name_is_rejected(self):
        first = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        second = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        first.settimeout(2)
        second.settimeout(2)
        try:
            self.assertEqual(self.request(first, "REGISTER|11|" + encoded("duplicate"))[1], "OK")
            response = self.request(second, "REGISTER|12|" + encoded("duplicate"))
            self.assertEqual(response[1], "ERROR")
            self.assertEqual(response[2]["code"], "NAME_TAKEN")
        finally:
            first.close()
            second.close()
