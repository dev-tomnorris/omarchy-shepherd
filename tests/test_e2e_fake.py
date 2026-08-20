import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fakes.fake_herdr import FakeHerdrServer
from helper.runtime import Helper
from support import JsonlSink, wait_until


class TestFakeEndToEnd(unittest.TestCase):
    def test_helper_event_refresh_focus_and_shutdown(self):
        temp_dir = tempfile.mkdtemp()
        socket_path = os.path.join(temp_dir, "herdr.sock")
        server = FakeHerdrServer(socket_path)
        server.start()
        sink = JsonlSink()
        stdin_r, stdin_w = os.pipe()
        stdin_read = os.fdopen(stdin_r)
        stdin_write = os.fdopen(stdin_w, "w")
        helper = Helper(
            socket_path=socket_path,
            debounce_s=0.08,
            recv_timeout=0.05,
            rpc_timeout=2.0,
            backoff_initial=0.05,
            backoff_max=0.2,
            infile=stdin_read,
            outfile=sink,
        )
        thread = threading.Thread(target=helper.run, name="shepherd-run")
        try:
            thread.start()
            self.assertTrue(wait_until(lambda: len(sink.of_type("state")) >= 1))
            initial = sink.of_type("state")[0]
            self.assertEqual(initial["connection"], "connected")
            self.assertFalse(initial["stale"])

            server.push_lifecycle("pane_focused", {
                "type": "pane_focused",
                "pane_id": "w1:p2",
                "workspace_id": "w1",
            })
            self.assertTrue(wait_until(lambda: len(sink.of_type("state")) >= 2))

            stdin_write.write('{"type":"focus","request_id":"req-e2e","pane_id":"w1:p1"}\n')
            stdin_write.flush()
            self.assertTrue(wait_until(lambda: any(
                m.get("request_id") == "req-e2e" and m.get("ok") is True
                for m in sink.of_type("action_result")
            )))
        finally:
            helper.stop()
            thread.join(timeout=3.0)
            stdin_write.close()
            stdin_read.close()
            server.stop()
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertFalse(thread.is_alive())
        live = [t.name for t in threading.enumerate() if t.name.startswith("shepherd-")]
        self.assertEqual(live, [])
        self.assertEqual(helper._thread_errors, [])
        self.assertEqual(server.thread_errors, [])
        snapshot_rpcs = [r for r in server.rpc_records() if r.methods == ["session.snapshot"]]
        self.assertGreaterEqual(len(snapshot_rpcs), 2)
        self.assertTrue(any(r.methods == ["agent.focus"] for r in server.rpc_records()))
