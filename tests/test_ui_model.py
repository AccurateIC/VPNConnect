import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from vpnconnect import cli, nm, ui_model


class ScreenTests(unittest.TestCase):
    """FR-GUI-01"""

    def test_screen_for_each_state(self):
        self.assertEqual(ui_model.screen_for(nm.Status(False, "missing")), ui_model.SETUP)
        self.assertEqual(ui_model.screen_for(nm.Status(True, "disconnected")), ui_model.SIGN_IN)
        self.assertEqual(ui_model.screen_for(nm.Status(True, "connecting")), ui_model.SIGN_IN)
        self.assertEqual(ui_model.screen_for(nm.Status(True, "connected", "a")), ui_model.CONNECTED)


class ErrorMappingTests(unittest.TestCase):
    """FR-GUI-06: every nm.VPNError message we raise maps to a friendly category."""

    CASES = {
        "Authentication failed - check your username, password (and OTP).": "auth",
        "The NetworkManager OpenVPN plugin is missing (package: network-manager-openvpn-gnome).": "plugin",
        "NetworkManager OpenVPN plugin not found (network-manager-openvpn-gnome).": "plugin",
        "Timed out waiting for NetworkManager.": "timeout",
        "NetworkManager (nmcli) is not installed.": "nm_missing",
        "File not found: /home/a/x.ovpn": "file",
        "Could not read x.ovpn: bad line": "file",
        "NetworkManager refused the profile: invalid": "file",
        "Error: Connection activation failed: something odd": "generic",
    }

    def test_categories(self):
        for msg, key in self.CASES.items():
            with self.subTest(msg=msg):
                self.assertEqual(ui_model.classify_error(msg), key)

    def test_friendly_text_never_echoes_raw(self):
        f = ui_model.friendly_error("Error: secret-ish raw text 10.0.0.1")
        self.assertNotIn("10.0.0.1", f.headline + f.next_step)


class DownloadsTests(unittest.TestCase):
    """FR-GUI-02"""

    def test_newest_ovpn_wins_and_others_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            old, new = Path(d, "old.ovpn"), Path(d, "new.OVPN")
            old.write_text("x")
            new.write_text("x")
            Path(d, "notes.txt").write_text("x")
            Path(d, "dir.ovpn").mkdir()
            now = time.time()
            os.utime(old, (now - 100, now - 100))
            os.utime(new, (now, now))
            self.assertEqual(ui_model.newest_profile(Path(d)), new)

    def test_none_when_empty_or_missing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(ui_model.newest_profile(Path(d)))
            self.assertIsNone(ui_model.newest_profile(Path(d, "nope")))


class TimeTests(unittest.TestCase):
    """FR-GUI-04"""

    def test_format_duration(self):
        self.assertEqual(ui_model.format_duration(42), "0:42")
        self.assertEqual(ui_model.format_duration(725), "12:05")
        self.assertEqual(ui_model.format_duration(3723), "1:02:03")
        self.assertEqual(ui_model.format_duration(-5), "0:00")

    def test_minutes_left(self):
        self.assertIsNone(ui_model.minutes_left(0, 100))
        self.assertEqual(ui_model.minutes_left(30, 0), 30)
        self.assertEqual(ui_model.minutes_left(30, 61), 29)
        self.assertEqual(ui_model.minutes_left(30, 1799), 1)
        self.assertEqual(ui_model.minutes_left(30, 5000), 0)

    def test_format_minutes(self):
        self.assertEqual(ui_model.format_minutes(45), "45 min")
        self.assertEqual(ui_model.format_minutes(480), "8 h")
        self.assertEqual(ui_model.format_minutes(90), "1 h 30 min")


class GuiRequirementsTests(unittest.TestCase):
    """FR-GUI-08"""

    def test_gui_shows_window_and_keeps_exit_code(self):
        with mock.patch.object(nm, "check_requirements", return_value=["no plugin"]), \
             mock.patch("vpnconnect.gui.show_problems") as show, \
             mock.patch("sys.stderr"):
            self.assertEqual(cli.main(["gui"]), 2)
        show.assert_called_once_with(["no plugin"])

    def test_cli_commands_do_not_open_window(self):
        with mock.patch.object(nm, "check_requirements", return_value=["no plugin"]), \
             mock.patch("vpnconnect.gui.show_problems") as show, \
             mock.patch("sys.stderr"):
            self.assertEqual(cli.main(["status"]), 2)
        show.assert_not_called()

    def test_window_failure_still_returns_2(self):
        with mock.patch.object(nm, "check_requirements", return_value=["no plugin"]), \
             mock.patch("vpnconnect.gui.show_problems", side_effect=RuntimeError("no display")), \
             mock.patch("sys.stderr"):
            self.assertEqual(cli.main(["gui"]), 2)


if __name__ == "__main__":
    unittest.main()


class ErrorMappingExtraTests(unittest.TestCase):
    def test_openvpn_log_does_not_fake_plugin_error(self):
        msg = "Error: activation failed\n\nOpenVPN log:\nPLUGIN_INIT: loaded\nTLS handshake failed"
        self.assertEqual(ui_model.classify_error(msg), "generic")

    def test_libnm_missing_is_plugin(self):
        self.assertEqual(ui_model.classify_error(
            "libnm Python bindings are missing (packages: python3-gi gir1.2-nm-1.0)."), "plugin")

    def test_auth_copy_without_otp(self):
        f = ui_model.friendly_error("Authentication failed", otp=False)
        self.assertNotIn("code", f.headline)
