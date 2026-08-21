"""Resolve Herdr Unix socket path unit tests."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from helper.socket_path import resolve_socket_path


class TestSocketPathResolution(unittest.TestCase):
    def test_default_path_with_injected_home(self):
        path = resolve_socket_path({"HOME": "/fake/home"})
        self.assertEqual(path, "/fake/home/.config/herdr/herdr.sock")

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

    def test_empty_socket_and_session_use_injected_home(self):
        path = resolve_socket_path({
            "HERDR_SOCKET_PATH": "",
            "HERDR_SESSION": "",
            "XDG_CONFIG_HOME": "",
            "HOME": "/fake/home",
        })
        self.assertEqual(path, "/fake/home/.config/herdr/herdr.sock")

    def test_injected_empty_mapping_does_not_use_process_home(self):
        with mock.patch(
            "os.path.expanduser",
            side_effect=AssertionError("expanduser called"),
        ):
            with self.assertRaises(ValueError) as ctx:
                resolve_socket_path({})
        self.assertEqual(str(ctx.exception), "Herdr config home unavailable")

    def test_injected_mapping_ignores_os_environ(self):
        with mock.patch.dict(
            os.environ,
            {
                "HERDR_SOCKET_PATH": "/real/should-not-appear.sock",
                "HERDR_SESSION": "real-session",
                "XDG_CONFIG_HOME": "/real/xdg",
                "HOME": "/real/home",
            },
            clear=False,
        ):
            path = resolve_socket_path({
                "HOME": "/fake/home",
                "HERDR_SESSION": "fake-sess",
            })
        self.assertEqual(
            path,
            "/fake/home/.config/herdr/sessions/fake-sess/herdr.sock",
        )

    def test_production_none_uses_expanduser_fallback(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch(
                "os.path.expanduser",
                return_value="/expanded/config",
            ) as expand:
                path = resolve_socket_path(None)
        expand.assert_called_once_with("~/.config")
        self.assertEqual(path, "/expanded/config/herdr/herdr.sock")
