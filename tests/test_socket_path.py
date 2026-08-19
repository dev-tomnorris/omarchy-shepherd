import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from helper.socket_path import resolve_socket_path


class TestSocketPathResolution(unittest.TestCase):
    def test_default_path(self):
        path = resolve_socket_path({})
        expected = os.path.expanduser("~/.config/herdr/herdr.sock")
        self.assertEqual(path, expected)

    def test_xdg_config_home(self):
        path = resolve_socket_path({"XDG_CONFIG_HOME": "/custom/config"})
        self.assertEqual(path, "/custom/config/herdr/herdr.sock")

    def test_herdr_socket_path(self):
        path = resolve_socket_path({
            "HERDR_SOCKET_PATH": "/custom/path.sock",
            "HERDR_SESSION": "ignored",
            "XDG_CONFIG_HOME": "/custom/config",
        })
        self.assertEqual(path, "/custom/path.sock")

    def test_herdr_session(self):
        path = resolve_socket_path({
            "XDG_CONFIG_HOME": "/custom/config",
            "HERDR_SESSION": "my-session",
        })
        self.assertEqual(path, "/custom/config/herdr/sessions/my-session/herdr.sock")

    def test_empty_env_vars(self):
        path = resolve_socket_path({
            "HERDR_SOCKET_PATH": "",
            "HERDR_SESSION": "",
            "XDG_CONFIG_HOME": "",
        })
        self.assertEqual(path, os.path.expanduser("~/.config/herdr/herdr.sock"))
