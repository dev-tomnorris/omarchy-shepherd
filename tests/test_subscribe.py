import json
import os
import socket
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fakes.fake_herdr import FakeHerdrServer
from helper.events import build_subscriptions
from helper.subscribe import SubscribeSession


class TestSubscribeTransport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.socket_path = os.path.join(self.temp_dir, "herdr.sock")
        self.server = FakeHerdrServer(self.socket_path)
        self.server.start()
        self.session = SubscribeSession(self.socket_path, recv_timeout=0.05, ack_timeout=2.0)

    def tearDown(self):
        self.session.close()
        self.server.stop()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ack_then_exclusive_stream(self):
        req_id = self.session.open(build_subscriptions(("w1:p1", "w1:p2")))
        self.assertTrue(req_id)
        self.assertEqual(len(self.server.subscribe_records()), 1)
        types = [item["type"] for item in self.server.last_subscriptions]
        self.assertIn("pane.updated", types)
        self.assertIn("pane.created", types)
        scoped = [item for item in self.server.last_subscriptions if item["type"] == "pane.agent_status_changed"]
        self.assertEqual({item["pane_id"] for item in scoped}, {"w1:p1", "w1:p2"})
        self.assertNotIn("layout.updated", types)
        self.assertNotIn("pane.scroll_changed", types)
        self.assertNotIn("workspace.metadata_updated", types)

    def test_second_request_on_subscribe_socket_is_rejected(self):
        raw = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        raw.settimeout(2.0)
        raw.connect(self.socket_path)
        raw.sendall(json.dumps({
            "id": "sub_1",
            "method": "events.subscribe",
            "params": {"subscriptions": [{"type": "pane.created"}]},
        }).encode() + b"\n")
        ack = raw.recv(4096)
        self.assertIn(b"subscription_started", ack)
        raw.sendall(b'{"id":"x","method":"session.snapshot","params":{}}\n')
        time.sleep(0.2)
        records = self.server.subscribe_records()
        self.assertTrue(records[-1].second_request_rejected)
        raw.close()

    def test_idle_timeout_does_not_close_subscribe(self):
        self.session.open(build_subscriptions(("w1:p1",)))
        idle = 0
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            result = self.session.recv_classified()
            if result is None:
                idle += 1
            elif result == "EOF":
                self.fail("idle recv was treated as disconnect")
        self.assertGreater(idle, 0)
        self.assertEqual(len(self.server.subscribe_records()), 1)
        self.assertFalse(self.server.subscribe_records()[0].closed)

    def test_lifecycle_and_scoped_pushes(self):
        self.session.open(build_subscriptions(("w1:p1",)))
        self.server.push_lifecycle("workspace_created", {"type": "workspace_created", "workspace": {"workspace_id": "w2"}})
        self.server.push_scoped("pane.agent_status_changed", {
            "pane_id": "w1:p1",
            "workspace_id": "w1",
            "agent_status": "idle",
        })
        seen = []
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and len(seen) < 2:
            result = self.session.recv_classified()
            if result in (None, "EOF"):
                continue
            seen.extend(item["kind"] for item in result)
        self.assertIn("lifecycle_push", seen)
        self.assertIn("scoped_push", seen)
