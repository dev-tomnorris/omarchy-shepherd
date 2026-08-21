"""Unit tests for helper.presentation descriptors."""

import copy
import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from helper.presentation import build_presentation_descriptor


_APP_ID_RE = re.compile(r"^org\.omarchy\.herdr\.session-[a-f0-9]{12}$")
_KEYS = ("kind", "supported", "app_id", "argv")


def _desc(env, config_dir=None):
    return build_presentation_descriptor(env, config_dir=config_dir)


def _assert_keys_only(test, descriptor):
    test.assertEqual(tuple(descriptor.keys()), _KEYS)
    test.assertEqual(set(descriptor.keys()), set(_KEYS))


def _patch_process_path_helpers():
    """Fail the test if process-home / CWD helpers are consulted."""
    return mock.patch.multiple(
        "os.path",
        expanduser=mock.Mock(side_effect=AssertionError("expanduser called")),
        abspath=mock.Mock(side_effect=AssertionError("abspath called")),
        realpath=mock.Mock(side_effect=AssertionError("realpath called")),
    )


class TestPresentationDescriptor(unittest.TestCase):
    def test_default_session(self):
        d = _desc({})
        self.assertEqual(d["kind"], "default")
        self.assertTrue(d["supported"])
        self.assertEqual(d["app_id"], "org.omarchy.herdr")
        self.assertEqual(d["argv"], ["herdr"])
        _assert_keys_only(self, d)

    def test_named_session(self):
        d = _desc({"HERDR_SESSION": "alpha-session"})
        self.assertEqual(d["kind"], "named")
        self.assertTrue(d["supported"])
        self.assertEqual(d["argv"], ["herdr", "--session", "alpha-session"])
        self.assertRegex(d["app_id"], _APP_ID_RE)
        _assert_keys_only(self, d)

    def test_named_app_id_stable(self):
        a = _desc({"HERDR_SESSION": "stable-name"})
        b = _desc({"HERDR_SESSION": "stable-name"})
        self.assertEqual(a["app_id"], b["app_id"])
        expected = "org.omarchy.herdr.session-" + hashlib.sha256(
            b"stable-name"
        ).hexdigest()[:12]
        self.assertEqual(a["app_id"], expected)

    def test_named_app_id_format(self):
        d = _desc({"HERDR_SESSION": "format-check"})
        self.assertRegex(d["app_id"], _APP_ID_RE)
        self.assertNotIn("format-check", d["app_id"])

    def test_similar_names_different_ids(self):
        # Character-replacement collisions must still differ under hashing.
        left = _desc({"HERDR_SESSION": "work_session"})
        right = _desc({"HERDR_SESSION": "work-session"})
        self.assertNotEqual(left["app_id"], right["app_id"])
        self.assertRegex(left["app_id"], _APP_ID_RE)
        self.assertRegex(right["app_id"], _APP_ID_RE)

    def test_empty_env_values_match_resolver(self):
        # Empty strings are falsy in resolve_socket_path → default.
        d = _desc({
            "HERDR_SOCKET_PATH": "",
            "HERDR_SESSION": "",
            "XDG_CONFIG_HOME": "",
        })
        self.assertEqual(d["kind"], "default")
        self.assertTrue(d["supported"])
        self.assertEqual(d["argv"], ["herdr"])

    def test_missing_keys_are_unset(self):
        d = _desc({"OTHER": "1"})
        self.assertEqual(d["kind"], "default")

    def test_custom_xdg_config_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"XDG_CONFIG_HOME": tmp}
            default_sock = os.path.join(tmp, "herdr", "herdr.sock")
            with _patch_process_path_helpers():
                d = _desc({
                    **env,
                    "HERDR_SOCKET_PATH": default_sock,
                })
            self.assertEqual(d["kind"], "default")
            self.assertTrue(d["supported"])
            self.assertEqual(d["argv"], ["herdr"])

    def test_config_dir_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock = os.path.join(tmp, "herdr", "herdr.sock")
            with _patch_process_path_helpers():
                d = _desc(
                    {"HERDR_SOCKET_PATH": sock},
                    config_dir=tmp,
                )
            self.assertEqual(d["kind"], "default")

    def test_conventional_default_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock = os.path.join(tmp, "herdr", "herdr.sock")
            with _patch_process_path_helpers():
                d = _desc(
                    {"HERDR_SOCKET_PATH": sock, "HERDR_SESSION": "should-not-win"},
                    config_dir=tmp,
                )
            self.assertEqual(d["kind"], "default")
            self.assertEqual(d["argv"], ["herdr"])

    def test_conventional_named_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock = os.path.join(tmp, "herdr", "sessions", "fleet-a", "herdr.sock")
            with _patch_process_path_helpers():
                d = _desc({"HERDR_SOCKET_PATH": sock}, config_dir=tmp)
            self.assertEqual(d["kind"], "named")
            self.assertTrue(d["supported"])
            self.assertEqual(d["argv"], ["herdr", "--session", "fleet-a"])
            self.assertRegex(d["app_id"], _APP_ID_RE)

    def test_socket_path_precedence_over_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock = os.path.join(tmp, "herdr", "sessions", "from-socket", "herdr.sock")
            with _patch_process_path_helpers():
                d = _desc(
                    {
                        "HERDR_SOCKET_PATH": sock,
                        "HERDR_SESSION": "from-env",
                    },
                    config_dir=tmp,
                )
            self.assertEqual(d["kind"], "named")
            self.assertEqual(d["argv"], ["herdr", "--session", "from-socket"])

    def test_conventional_named_uses_recovered_not_session_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock = os.path.join(tmp, "herdr", "sessions", "recovered", "herdr.sock")
            with _patch_process_path_helpers():
                d = _desc(
                    {
                        "HERDR_SOCKET_PATH": sock,
                        "HERDR_SESSION": "other-name",
                    },
                    config_dir=tmp,
                )
            self.assertEqual(d["argv"][2], "recovered")
            self.assertNotEqual(d["argv"][2], "other-name")

    def test_arbitrary_absolute_override_unsupported(self):
        fake = "/var/tmp/shepherd-pres-fake/not-herdr.sock"
        with _patch_process_path_helpers():
            d = _desc({"HERDR_SOCKET_PATH": fake, "HERDR_SESSION": "ignored"})
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])
        self.assertEqual(d["app_id"], "")
        self.assertEqual(d["argv"], [])
        _assert_keys_only(self, d)
        blob = json.dumps(d)
        self.assertNotIn(fake, blob)

    def test_arbitrary_relative_override_unsupported(self):
        rel = "relative-fake/herdr.sock"
        with _patch_process_path_helpers():
            d = _desc({"HERDR_SOCKET_PATH": rel})
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])
        self.assertNotIn(rel, json.dumps(d))

    def test_nested_session_socket_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock = os.path.join(
                tmp, "herdr", "sessions", "outer", "inner", "herdr.sock"
            )
            with _patch_process_path_helpers():
                d = _desc({"HERDR_SOCKET_PATH": sock}, config_dir=tmp)
            self.assertEqual(d["kind"], "socket_override")
            self.assertFalse(d["supported"])

    def test_traversal_shaped_input_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Contains ".." component — must not classify as named.
            sock = os.path.join(
                tmp, "herdr", "sessions", "safe", "..", "other", "herdr.sock"
            )
            with _patch_process_path_helpers():
                d = _desc({"HERDR_SOCKET_PATH": sock}, config_dir=tmp)
            self.assertEqual(d["kind"], "socket_override")
            self.assertFalse(d["supported"])
            self.assertNotIn("..", json.dumps(d))

    def test_dot_component_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock = os.path.join(
                tmp, "herdr", "sessions", ".", "weird", "herdr.sock"
            )
            with _patch_process_path_helpers():
                d = _desc({"HERDR_SOCKET_PATH": sock}, config_dir=tmp)
            self.assertEqual(d["kind"], "socket_override")
            self.assertFalse(d["supported"])

    def test_wrong_socket_filename_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            sock = os.path.join(
                tmp, "herdr", "sessions", "fleet-b", "herdr-client.sock"
            )
            with _patch_process_path_helpers():
                d = _desc({"HERDR_SOCKET_PATH": sock}, config_dir=tmp)
            self.assertEqual(d["kind"], "socket_override")
            self.assertFalse(d["supported"])

    def test_descriptor_exactly_four_keys(self):
        for env in (
            {},
            {"HERDR_SESSION": "k1"},
            {"HERDR_SOCKET_PATH": "/tmp/shepherd-pres-unsup.sock"},
        ):
            d = _desc(env)
            _assert_keys_only(self, d)

    def test_unsupported_excludes_raw_path(self):
        marker = "/tmp/shepherd-pres-marker-xyz/custom.sock"
        with _patch_process_path_helpers():
            d = _desc({"HERDR_SOCKET_PATH": marker})
        serialized = json.dumps(d, sort_keys=True)
        self.assertNotIn(marker, serialized)
        self.assertNotIn("shepherd-pres-marker", serialized)
        self.assertNotIn(marker, repr(d))

    def test_json_serializable(self):
        cases = (
            {},
            {"HERDR_SESSION": "json-sess"},
            {"HERDR_SOCKET_PATH": "/tmp/shepherd-pres-json.sock"},
        )
        for env in cases:
            d = _desc(env)
            raw = json.dumps(d)
            loaded = json.loads(raw)
            self.assertEqual(loaded, d)

    def test_env_mapping_unchanged(self):
        env = {
            "HERDR_SESSION": "immutable",
            "XDG_CONFIG_HOME": "/tmp/shepherd-pres-xdg",
            "HOME": "/tmp/shepherd-pres-home",
            "HERDR_SOCKET_PATH": "/tmp/shepherd-pres-sock.sock",
        }
        before = copy.deepcopy(env)
        with _patch_process_path_helpers():
            _desc(env)
        self.assertEqual(env, before)

    def test_named_matches_session_env_app_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            name = "parity-name"
            via_env = _desc({"HERDR_SESSION": name})
            sock = os.path.join(tmp, "herdr", "sessions", name, "herdr.sock")
            with _patch_process_path_helpers():
                via_sock = _desc({"HERDR_SOCKET_PATH": sock}, config_dir=tmp)
            self.assertEqual(via_env, via_sock)

    def test_no_filesystem_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = set(Path(tmp).rglob("*"))
            sock = os.path.join(tmp, "herdr", "sessions", "n1", "herdr.sock")
            # Path does not need to exist.
            with _patch_process_path_helpers():
                _desc({"HERDR_SOCKET_PATH": sock}, config_dir=tmp)
            after = set(Path(tmp).rglob("*"))
            self.assertEqual(before, after)

    def test_arbitrary_override_does_not_fallback_to_session(self):
        with _patch_process_path_helpers():
            d = _desc({
                "HERDR_SOCKET_PATH": "/tmp/shepherd-pres-arb.sock",
                "HERDR_SESSION": "would-be-named",
            })
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])
        self.assertEqual(d["argv"], [])

    # --- Amendment: injected HOME / XDG / tilde determinism ---

    def test_injected_home_recognizes_default_socket(self):
        home = "/tmp/shepherd-pres-home-default"
        sock = home + "/.config/herdr/herdr.sock"
        with _patch_process_path_helpers():
            d = _desc({"HOME": home, "HERDR_SOCKET_PATH": sock})
        self.assertEqual(d["kind"], "default")
        self.assertTrue(d["supported"])
        self.assertEqual(d["argv"], ["herdr"])

    def test_injected_home_recognizes_named_socket(self):
        home = "/tmp/shepherd-pres-home-named"
        sock = home + "/.config/herdr/sessions/fleet-home/herdr.sock"
        with _patch_process_path_helpers():
            d = _desc({"HOME": home, "HERDR_SOCKET_PATH": sock})
        self.assertEqual(d["kind"], "named")
        self.assertEqual(d["argv"], ["herdr", "--session", "fleet-home"])

    def test_fake_injected_home_used_instead_of_process_home(self):
        fake_home = "/tmp/shepherd-pres-fake-home-zzz"
        sock = fake_home + "/.config/herdr/herdr.sock"
        with _patch_process_path_helpers():
            with mock.patch(
                "pathlib.Path.home",
                side_effect=AssertionError("Path.home called"),
            ):
                d = _desc({"HOME": fake_home, "HERDR_SOCKET_PATH": sock})
        self.assertEqual(d["kind"], "default")

    def test_missing_injected_home_does_not_consult_process_home(self):
        # Absolute conventional-looking path under a fake root, but no config
        # root available → unsupported, and process helpers must not run.
        sock = "/tmp/shepherd-pres-nohome/.config/herdr/herdr.sock"
        with _patch_process_path_helpers():
            with mock.patch(
                "pathlib.Path.home",
                side_effect=AssertionError("Path.home called"),
            ):
                d = _desc({"HERDR_SOCKET_PATH": sock})
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])

    def test_tilde_socket_expands_with_injected_home(self):
        home = "/tmp/shepherd-pres-tilde-home"
        with _patch_process_path_helpers():
            d = _desc({
                "HOME": home,
                "HERDR_SOCKET_PATH": "~/.config/herdr/herdr.sock",
            })
        self.assertEqual(d["kind"], "default")
        self.assertTrue(d["supported"])

    def test_tilde_socket_without_injected_home_unsupported(self):
        with _patch_process_path_helpers():
            d = _desc({"HERDR_SOCKET_PATH": "~/.config/herdr/herdr.sock"})
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])
        self.assertNotIn("~", json.dumps(d))

    def test_tilde_other_user_unsupported(self):
        with _patch_process_path_helpers():
            d = _desc({
                "HOME": "/tmp/shepherd-pres-home",
                "HERDR_SOCKET_PATH": "~otheruser/.config/herdr/herdr.sock",
            })
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])

    def test_absolute_xdg_recognizes_conventional_paths(self):
        xdg = "/tmp/shepherd-pres-xdg-abs"
        sock = xdg + "/herdr/sessions/xdg-sess/herdr.sock"
        with _patch_process_path_helpers():
            d = _desc({
                "XDG_CONFIG_HOME": xdg,
                "HOME": "/tmp/shepherd-pres-home-ignored",
                "HERDR_SOCKET_PATH": sock,
            })
        self.assertEqual(d["kind"], "named")
        self.assertEqual(d["argv"], ["herdr", "--session", "xdg-sess"])

    def test_relative_xdg_not_converted_via_cwd(self):
        with _patch_process_path_helpers():
            d = _desc({
                "XDG_CONFIG_HOME": "relative-xdg-dir",
                "HOME": "/tmp/shepherd-pres-home-fallback-blocked",
                "HERDR_SOCKET_PATH": "/tmp/shepherd-pres-home-fallback-blocked/.config/herdr/herdr.sock",
            })
        # Bad XDG is present → no fallthrough to HOME → unsupported.
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])

    def test_tilde_xdg_not_expanded_via_process_home(self):
        with _patch_process_path_helpers():
            d = _desc({
                "XDG_CONFIG_HOME": "~/evil-xdg",
                "HOME": "/tmp/shepherd-pres-home-realish",
                "HERDR_SOCKET_PATH": "/tmp/shepherd-pres-home-realish/.config/herdr/herdr.sock",
            })
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])

    def test_relative_config_dir_cannot_classify(self):
        with _patch_process_path_helpers():
            d = _desc(
                {"HERDR_SOCKET_PATH": "/tmp/shepherd-pres-relcfg/herdr/herdr.sock"},
                config_dir="relative-config-home",
            )
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])

    def test_prefix_confusion_sibling_herdr_evil_unsupported(self):
        root = "/tmp/shepherd-pres-prefix"
        with _patch_process_path_helpers():
            d = _desc(
                {
                    "HERDR_SOCKET_PATH": root + "/herdr-evil/sessions/x/herdr.sock",
                },
                config_dir=root,
            )
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])

    def test_socket_filename_suffix_trick_unsupported(self):
        root = "/tmp/shepherd-pres-suffix"
        with _patch_process_path_helpers():
            d = _desc(
                {
                    "HERDR_SOCKET_PATH": root + "/herdr/sessions/s1/herdr.sock.bak",
                },
                config_dir=root,
            )
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])

    def test_unicode_session_name_deterministic(self):
        name = "sessión-ユニコード"
        expected_id = "org.omarchy.herdr.session-" + hashlib.sha256(
            name.encode("utf-8")
        ).hexdigest()[:12]
        d = _desc({"HERDR_SESSION": name})
        self.assertEqual(d["kind"], "named")
        self.assertEqual(d["app_id"], expected_id)
        self.assertEqual(d["argv"], ["herdr", "--session", name])
        self.assertNotIn(name, d["app_id"])

    def test_whitespace_only_session_remains_truthy(self):
        name = "   "
        d = _desc({"HERDR_SESSION": name})
        self.assertEqual(d["kind"], "named")
        self.assertEqual(d["argv"], ["herdr", "--session", name])

    def test_whitespace_only_socket_path_precedence_unsupported(self):
        with _patch_process_path_helpers():
            d = _desc({
                "HERDR_SOCKET_PATH": "   ",
                "HERDR_SESSION": "would-be-named",
            })
        self.assertEqual(d["kind"], "socket_override")
        self.assertFalse(d["supported"])
        self.assertEqual(d["argv"], [])

    def test_default_and_named_without_home_still_work(self):
        with _patch_process_path_helpers():
            self.assertEqual(_desc({})["kind"], "default")
            self.assertEqual(
                _desc({"HERDR_SESSION": "no-home-needed"})["argv"][2],
                "no-home-needed",
            )


if __name__ == "__main__":
    unittest.main()
