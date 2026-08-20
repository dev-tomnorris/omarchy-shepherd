import os
import socket
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fakes.fake_herdr import FakeHerdrServer
from helper.protocol import ProtocolError
from helper.rpc import RpcClient, RpcError


class TestOneShotRpc(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.socket_path = os.path.join(self.temp_dir, "herdr.sock")
        self.server = FakeHerdrServer(self.socket_path)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_one_request_per_rpc_connection_then_close(self):
        client = RpcClient(self.socket_path, recv_timeout=0.1, rpc_timeout=2.0)
        snapshot = client.snapshot()
        self.assertIn("agents", snapshot)
        client.snapshot()
        records = self.server.rpc_records()
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(record.methods, ["session.snapshot"])
            self.assertTrue(record.closed)

    def test_rpc_error_is_not_discarded(self):
        client = RpcClient(self.socket_path, recv_timeout=0.1, rpc_timeout=2.0)
        with self.assertRaises(RpcError) as raised:
            client.agent_focus("invalid")
        self.assertEqual(raised.exception.code, "invalid_param")

    def test_mismatched_id_is_not_discarded(self):
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        path = os.path.join(self.temp_dir, "mismatch.sock")
        listener.bind(path)
        listener.listen(1)
        listener.settimeout(2.0)

        def serve():
            conn, _ = listener.accept()
            conn.recv(4096)
            conn.sendall(b'{"id":"other","result":{"type":"ok"}}\n')
            conn.close()

        import threading
        thread = threading.Thread(target=serve)
        thread.start()
        client = RpcClient(path, recv_timeout=0.1, rpc_timeout=2.0)
        with self.assertRaises(ProtocolError):
            client.call("ping", {})
        thread.join(timeout=2.0)
        listener.close()
