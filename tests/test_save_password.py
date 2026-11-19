"""Saved password outside the GUI: settings, error mapping, CLI, tray, live keyring."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vpnconnect import cli, keyring_store, nm, settings, tray, ui_model


class SettingsTests(unittest.TestCase):  # FR-SAVE-08 / CR-2
    def test_user_file_cannot_reenable(self):  # audit 5, CR-2 amendment
        with tempfile.TemporaryDirectory() as d:
            sys_cfg, user_cfg = Path(d, "a.conf"), Path(d, "b.conf")
            sys_cfg.write_text("[vpnconnect]\nallow_save_password = false\n")
            user_cfg.write_text("[vpnconnect]\nallow_save_password = true\n")
            self.assertFalse(settings.load([sys_cfg, user_cfg]).allow_save_password)
            sys_cfg.write_text("[vpnconnect]\nallow_save_password = true\n")
            user_cfg.write_text("[vpnconnect]\nallow_save_password = false\n")
            self.assertFalse(settings.load([sys_cfg, user_cfg]).allow_save_password)

    def test_default_true_and_parsed(self):
        self.assertTrue(settings.Settings().allow_save_password)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "a.conf")
            p.write_text("[vpnconnect]\nallow_save_password = no\n")
            self.assertFalse(settings.load([p]).allow_save_password)


class JournalTests(unittest.TestCase):  # audit 3
    def test_connect_reads_only_this_attempts_log(self):
        with mock.patch.object(nm, "_run", return_value=mock.Mock(returncode=4, stderr="Error: interrupted", stdout="")), \
             mock.patch.object(nm, "recent_openvpn_log", return_value="") as log, \
             mock.patch.object(nm.time, "time", return_value=1000.0):
            with self.assertRaises(nm.VPNError):
                nm.connect("X", "pw")
        log.assert_called_once_with(since=999)

    def test_since_is_passed_to_journalctl(self):
        with mock.patch.object(nm.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="")) as run:
            nm.recent_openvpn_log(since=1234)
        self.assertIn("@1234", run.call_args[0][0])


class ErrorTests(unittest.TestCase):  # FR-SAVE-10
    def test_nmcli_login_failed_is_auth(self):
        self.assertEqual(ui_model.classify_error(
            "Error: Connection activation failed: Login/authentication failed"), "auth")
        self.assertEqual(ui_model.classify_error("Error: ... the VPN service login failed"), "auth")

    def test_saved_rejected(self):
        self.assertEqual(ui_model.classify_error(ui_model.SAVED_REJECTED + "x"), "saved_auth")


class CliTests(unittest.TestCase):  # FR-SAVE-09
    def setUp(self):
        for p in (mock.patch.object(nm, "check_requirements", return_value=[]),
                  mock.patch.object(nm, "status", return_value=nm.Status(True, "disconnected", "alex")),
                  mock.patch.object(settings, "load", return_value=settings.Settings()),
                  mock.patch("sys.stdout"), mock.patch("sys.stderr")):
            p.start()
            self.addCleanup(p.stop)

    def run_connect(self, saved, argv=("connect",), connect_error=None):
        with mock.patch.object(keyring_store, "lookup", return_value=saved), \
             mock.patch.object(keyring_store, "forget") as forget, \
             mock.patch.object(nm, "connect", side_effect=connect_error) as connect, \
             mock.patch("getpass.getpass", return_value="typed") as ask:
            rc = cli.main(list(argv))
        return rc, connect, ask, forget

    def test_uses_saved_password_without_prompt(self):
        rc, connect, ask, _ = self.run_connect("saved-pw")
        self.assertEqual(rc, 0)
        self.assertEqual(connect.call_args[0][1], "saved-pw")
        ask.assert_not_called()

    def test_ask_flag_forces_prompt(self):
        rc, connect, ask, _ = self.run_connect("saved-pw", ("connect", "--ask"))
        self.assertEqual(rc, 0)
        self.assertEqual(connect.call_args[0][1], "typed")

    def test_wrong_code_keeps_saved_password(self):  # audit 1
        rc, connect, _, forget = self.run_connect(
            "saved-pw", ("connect", "--otp"), connect_error=nm.VPNError("Authentication failed"))
        self.assertEqual(rc, 1)
        self.assertEqual(connect.call_args[0][1], "saved-pw" + "typed")
        forget.assert_not_called()

    def test_network_error_keeps_saved_password(self):
        rc, _, _, forget = self.run_connect("saved-pw", connect_error=nm.VPNError("Timed out"))
        forget.assert_not_called()

    def test_policy_off_forgets_and_prompts(self):
        settings.load.return_value = settings.Settings(allow_save_password=False)
        rc, connect, ask, forget = self.run_connect("saved-pw")
        forget.assert_called()
        self.assertEqual(connect.call_args[0][1], "typed")

    def test_rejected_saved_password_forgotten(self):
        rc, _, _, forget = self.run_connect(
            "old", connect_error=nm.VPNError("Authentication failed - check your username"))
        self.assertEqual(rc, 1)
        forget.assert_called_once()

    def test_forget_password_command(self):
        with mock.patch.object(keyring_store, "forget") as forget:
            self.assertEqual(cli.main(["forget-password"]), 0)
        forget.assert_called_once_with("Company VPN")


class TrayConnectTests(unittest.TestCase):  # FR-SAVE-07
    def make(self, **cfg):
        Gtk, GLib, AI = mock.MagicMock(), mock.MagicMock(), mock.MagicMock()
        GLib.idle_add.side_effect = lambda fn, *a: fn(*a)
        self.thread = mock.patch.object(tray.threading, "Thread",
                                        side_effect=lambda target, daemon: mock.Mock(start=target))
        self.thread.start()
        self.addCleanup(self.thread.stop)
        with mock.patch.object(nm, "status", return_value=nm.Status(True, "disconnected", "alex")), \
             mock.patch.object(keyring_store, "has_saved", return_value=True):
            t = tray.Tray(settings.Settings(**cfg), Gtk, GLib, AI)
        return t

    def test_connect_item_only_when_possible(self):
        t = self.make()
        t.connect_item.set_visible.assert_called_with(True)
        st = nm.Status(True, "disconnected", "alex")
        with mock.patch.object(keyring_store, "has_saved", return_value=False):
            self.assertFalse(t._one_click_possible(st))
        with mock.patch.object(keyring_store, "has_saved", return_value=True):
            self.assertTrue(t._one_click_possible(st))
            self.assertFalse(t._one_click_possible(nm.Status(True, "connected", "alex")))
            t.cfg.otp = True
            self.assertFalse(t._one_click_possible(st))
            t.cfg.otp, t.cfg.allow_save_password = False, False
            self.assertFalse(t._one_click_possible(st))

    def test_one_click_connect_uses_saved_password(self):
        t = self.make()
        with mock.patch.object(keyring_store, "lookup", return_value="pw"), \
             mock.patch.object(nm, "connect") as connect, \
             mock.patch.object(nm, "status", return_value=nm.Status(True, "connected", "alex")), \
             mock.patch.object(t, "open_window") as open_window:
            t.connect()
        connect.assert_called_once_with("Company VPN", "pw")
        open_window.assert_not_called()

    def failed_connect(self, error):
        t = self.make()
        old = mock.Mock()
        old.poll.return_value = None  # a window is already open, showing "Password: saved"
        t.child = old
        with mock.patch.object(keyring_store, "lookup", return_value="old"), \
             mock.patch.object(keyring_store, "forget") as forget, \
             mock.patch.object(nm, "connect", side_effect=error), \
             mock.patch.object(nm, "status", return_value=nm.Status(True, "disconnected", "alex")), \
             mock.patch.object(tray.subprocess, "Popen") as popen:
            t.connect()
        return forget, popen, old

    def test_rejected_forgets_and_window_explains(self):  # FR-SAVE-05/07, audit 4
        forget, popen, old = self.failed_connect(nm.VPNError("Authentication failed"))
        forget.assert_called_once()
        old.terminate.assert_called_once()  # stale window replaced
        self.assertEqual(popen.call_args[0][0][-2:], ["--error", "saved_auth"])

    def test_network_failure_keeps_password_and_explains(self):  # audit 3
        forget, popen, _ = self.failed_connect(nm.VPNError("Timed out waiting for NetworkManager."))
        forget.assert_not_called()
        self.assertEqual(popen.call_args[0][0][-2:], ["--error", "timeout"])

    def test_poll_never_reads_the_secret(self):  # audit 2, BR-SAVE-01
        t = self.make()
        with mock.patch.object(keyring_store, "lookup") as lookup, \
             mock.patch.object(keyring_store, "has_saved", return_value=True) as has, \
             mock.patch.object(nm, "status", return_value=nm.Status(True, "disconnected", "alex")):
            for _ in range(5):
                t.polling = False
                t._poll()
        lookup.assert_not_called()
        self.assertEqual(has.call_count, 5)

    def test_quit_during_one_click_connect_disconnects(self):  # audit 8
        t = self.make(disconnect_on_exit=True)

        def connect_then_quit(*_a):
            t.quitting = True

        with mock.patch.object(keyring_store, "lookup", return_value="pw"), \
             mock.patch.object(nm, "connect", side_effect=connect_then_quit), \
             mock.patch.object(nm, "disconnect") as disc, \
             mock.patch.object(nm, "status", return_value=nm.Status(True, "connected", "alex")):
            t.connect()
        disc.assert_called_once()


@unittest.skipUnless(os.environ.get("VPNCONNECT_KEYRING_TEST"), "set VPNCONNECT_KEYRING_TEST=1 to use the real keyring")
class LiveKeyringTests(unittest.TestCase):  # BR-SAVE-01, real libsecret
    def test_round_trip(self):
        conn = "VPNConnect selftest (delete me)"
        self.addCleanup(keyring_store.forget, conn)
        self.assertTrue(keyring_store.available())
        self.assertTrue(keyring_store.store(conn, "tester", "pw-123"))
        self.assertEqual(keyring_store.lookup(conn, "tester"), "pw-123")
        self.assertTrue(keyring_store.has_saved(conn, "tester"))
        self.assertTrue(keyring_store.store(conn, "other", "pw-456"))  # replaces the first user
        self.assertFalse(keyring_store.has_saved(conn, "tester"))
        self.assertIsNone(keyring_store.lookup(conn, "someone-else"))
        keyring_store.forget(conn)
        self.assertFalse(keyring_store.has_saved(conn, "other"))
