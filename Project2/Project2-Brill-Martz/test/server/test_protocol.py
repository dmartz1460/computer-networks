import base64
import json
import os
import socket
import subprocess
import threading
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

    def new_user(self, username):
        connection = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        connection.settimeout(2)
        response = self.request(connection, "REGISTER|100|" + encoded(username))
        self.assertEqual(response[1], "OK")
        return connection

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
        self.assertEqual(self.event(self.bob)["messageId"], message_id)
        self.assertEqual(self.request(self.bob, "MESSAGE_PUBLIC|6|" + message_id)[2]["content"], "Body")

        self.assertEqual(self.request(self.alice, "JOIN_GROUP|7|GENERAL")[2]["board"], "general")
        status = self.request(self.alice, "POST_GROUP|8|1|" + encoded("Private") + "|" + encoded("Secret"))
        private_id = status[2]["messageId"]
        self.assertEqual(self.request(self.bob, "USERS_GROUP|9|1")[1], "ERROR")
        self.assertEqual(self.request(self.bob, "MESSAGE_GROUP|10|1|" + private_id)[2]["code"], "NOT_MEMBER")

    def test_disconnect_response_contains_public_board_shape(self):
        connection = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        connection.settimeout(2)
        try:
            self.assertEqual(self.request(connection, "REGISTER|20|" + encoded("disconnect-user"))[1], "OK")
            self.assertEqual(self.request(connection, "JOIN_PUBLIC|21")[1], "OK")
            response = self.request(connection, "DISCONNECT|22")
            self.assertEqual(response[1], "OK")
            self.assertEqual(response[2]["board"], "public")
            self.assertEqual(response[2]["username"], "disconnect-user")
            self.assertNotIn("disconnect-user", response[2]["users"])
        finally:
            connection.close()

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

    def test_join_snapshot_contains_only_two_latest_messages(self):
        poster = self.new_user("snapshot-poster")
        joiner = self.new_user("snapshot-joiner")
        try:
            self.assertEqual(self.request(poster, "JOIN_PUBLIC|30")[1], "OK")
            for index in range(3):
                response = self.request(
                    poster,
                    "POST_PUBLIC|31|" + encoded("subject-" + str(index))
                    + "|" + encoded("content-" + str(index)),
                )
                self.assertEqual(response[1], "OK")
            snapshot = self.request(joiner, "JOIN_PUBLIC|32")[2]
            self.assertEqual([message["subject"] for message in snapshot["messages"]],
                             ["subject-1", "subject-2"])
        finally:
            poster.close()
            joiner.close()

    def test_public_leave_notifies_remaining_member(self):
        first = self.new_user("leave-first")
        second = self.new_user("leave-second")
        try:
            self.request(first, "JOIN_PUBLIC|40")
            self.request(second, "JOIN_PUBLIC|41")
            self.assertEqual(self.event(first)["type"], "USER_JOINED")
            self.assertEqual(self.request(first, "LEAVE_PUBLIC|42")[1], "OK")
            event = self.event(second)
            self.assertEqual(event["type"], "USER_LEFT")
            self.assertEqual(event["user"], "leave-first")
        finally:
            first.close()
            second.close()

    def test_private_join_and_leave_notifications(self):
        first = self.new_user("private-first")
        second = self.new_user("private-second")
        try:
            self.request(first, "JOIN_GROUP|50|2")
            self.request(second, "JOIN_GROUP|51|sports")
            joined = self.event(first)
            self.assertEqual(joined["type"], "GROUP_JOINED")
            self.assertEqual(joined["board"], "sports")
            self.assertEqual(self.request(second, "LEAVE_GROUP|52|2")[1], "OK")
            left = self.event(first)
            self.assertEqual(left["type"], "GROUP_LEFT")
            self.assertEqual(left["user"], "private-second")
        finally:
            first.close()
            second.close()

    def test_all_groups_are_listed_and_joinable_by_id(self):
        connection = self.new_user("all-groups")
        try:
            groups = self.request(connection, "LIST_GROUPS|60")[2]["groups"]
            self.assertEqual(
                groups,
                [
                    {"id": 1, "name": "general"},
                    {"id": 2, "name": "sports"},
                    {"id": 3, "name": "study"},
                    {"id": 4, "name": "gaming"},
                    {"id": 5, "name": "tech"},
                ],
            )
            for group_id in range(1, 6):
                self.assertEqual(
                    self.request(connection, "JOIN_GROUP|61|" + str(group_id))[1], "OK"
                )
        finally:
            connection.close()

    def test_invalid_group_message_and_field_count_errors(self):
        connection = self.new_user("invalid-inputs")
        try:
            self.assertEqual(
                self.request(connection, "JOIN_GROUP|70|99")[2]["code"], "INVALID_GROUP"
            )
            self.assertEqual(
                self.request(connection, "JOIN_PUBLIC|71|extra")[2]["code"], "INVALID_COMMAND"
            )
            self.assertEqual(
                self.request(connection, "MESSAGE_PUBLIC|72|1")[2]["code"], "NOT_MEMBER"
            )
            self.assertEqual(self.request(connection, "JOIN_PUBLIC|73")[1], "OK")
            self.assertEqual(
                self.request(connection, "MESSAGE_PUBLIC|74|not-a-number")[2]["code"],
                "INVALID_MESSAGE",
            )
            self.assertEqual(
                self.request(connection, "POST_PUBLIC|75|%%%|%%%")[2]["code"],
                "INVALID_COMMAND",
            )
        finally:
            connection.close()

    def test_special_text_survives_post_and_lookup(self):
        connection = self.new_user("special-text")
        try:
            self.request(connection, "JOIN_PUBLIC|80")
            subject = 'quotes " and | pipes'
            content = "line one\nline two — café"
            response = self.request(
                connection, "POST_PUBLIC|81|" + encoded(subject) + "|" + encoded(content)
            )
            message_id = response[2]["messageId"]
            message = self.request(connection, "MESSAGE_PUBLIC|82|" + message_id)[2]
            self.assertEqual(message["subject"], subject)
            self.assertEqual(message["content"], content)
        finally:
            connection.close()

    def test_private_events_are_isolated(self):
        member = self.new_user("isolated-member")
        outsider = self.new_user("isolated-outsider")
        try:
            self.request(member, "JOIN_GROUP|90|general")
            self.request(outsider, "JOIN_GROUP|91|sports")
            self.request(
                outsider, "POST_GROUP|92|sports|" + encoded("private") + "|" + encoded("content")
            )
            member.settimeout(0.25)
            with self.assertRaises(socket.timeout):
                self.event(member)
        finally:
            member.close()
            outsider.close()

    def test_disconnect_notifies_public_members(self):
        observer = self.new_user("disconnect-observer")
        departing = self.new_user("disconnect-departing")
        try:
            self.request(observer, "JOIN_PUBLIC|100")
            self.request(departing, "JOIN_PUBLIC|101")
            self.event(observer)
            departing.close()
            event = self.event(observer)
            self.assertEqual(event["type"], "USER_LEFT")
            self.assertEqual(event["user"], "disconnect-departing")
        finally:
            observer.close()
            departing.close()

    def test_malformed_and_oversized_frames_are_rejected(self):
        malformed = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        malformed.settimeout(2)
        try:
            malformed.sendall((1).to_bytes(4, "big", signed=True) + b"\xff")
            try:
                self.assertEqual(malformed.recv(1), b"")
            except OSError:
                pass
        finally:
            malformed.close()

        oversized = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        oversized.settimeout(2)
        try:
            oversized.sendall((16 * 1024 * 1024 + 1).to_bytes(4, "big", signed=True))
            try:
                self.assertEqual(oversized.recv(1), b"")
            except OSError:
                pass
        finally:
            oversized.close()

    def test_concurrent_posts_have_unique_ids(self):
        connections = [self.new_user("concurrent-" + str(index)) for index in range(4)]
        try:
            for connection in connections:
                self.request(connection, "JOIN_PUBLIC|110")

            results = []
            failures = []

            def post(index):
                try:
                    response = self.request(
                        connections[index],
                        "POST_PUBLIC|120|" + encoded("subject-" + str(index))
                        + "|" + encoded("body"),
                    )
                    results.append(response[2]["messageId"])
                except Exception as exception:
                    failures.append(exception)

            threads = [threading.Thread(target=post, args=(index,)) for index in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertFalse(failures)
            self.assertEqual(len(results), 4)
            self.assertEqual(len(set(results)), 4)
        finally:
            for connection in connections:
                connection.close()
