import os
import pathlib
import unittest


class TestProductionIsolation(unittest.TestCase):
    def test_helper_has_no_fake_server_or_wait_matched_invalidation(self):
        root = pathlib.Path(__file__).resolve().parents[1] / "helper"
        for path in root.glob("*.py"):
            text = path.read_text()
            self.assertNotIn("FakeHerdrServer", text, path.name)
            self.assertNotIn("start_server", text, path.name)
            self.assertNotIn("import unittest", text, path.name)
            if path.name != "protocol.py":
                self.assertNotIn("wait_matched", text, path.name)
        protocol = (root / "protocol.py").read_text()
        self.assertIn("wait_matched", protocol)
        self.assertIn("never treated as invalidation", protocol)
