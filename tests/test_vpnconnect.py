import subprocess
import unittest
from unittest import mock

from vpnconnect import cli, nm, settings


def proc(rc=0, out="", err=""):
    return subprocess.CompletedProcess([], rc, out, err)


class StatusTests(unittest.TestCase):
    def test_connected_with_username(self):
        out = "GENERAL.STATE:activated\nvpn.data:remote = 1.2.3.4:443, username = alice, password-flags = 2\n"
        with mock.patch.object(nm, "_run", return_value=proc(out=out)):
            st = nm.status("X")
        self.assertTrue(st.connected)
        self.assertEqual(st.username, "alice")

    def test_inactive_profile(self):
        with mock.patch.object(nm, "_run", return_value=proc(out="vpn.data:username = bob\n")):
            st = nm.status("X")
        self.assertEqual((st.exists, st.state, st.username), (True, "disconnected", "bob"))

    def test_missing(self):
        with mock.patch.object(nm, "_run", return_value=proc(rc=10, err="no such connection")):
            self.assertEqual(nm.status("X").state, "missing")


class ConnectTests(unittest.TestCase):
    def test_password_goes_to_stdin_not_argv(self):
        with mock.patch.object(nm, "_run", return_value=proc()) as run:
            nm.connect("Company VPN", "s3cr:et")
        args, kwargs = run.call_args
        self.assertNotIn("s3cr:et", " ".join(args[0]))
        self.assertEqual(kwargs["input"], "vpn.secrets.password:s3cr:et\n")
        self.assertIn("/dev/stdin", args[0])

    def test_auth_failure_is_friendly(self):
        with mock.patch.object(nm, "_run", return_value=proc(rc=4, err="activation failed")), \
             mock.patch.object(nm, "recent_openvpn_log", return_value="AUTH: Received control message: AUTH_FAILED"):
            with self.assertRaisesRegex(nm.VPNError, "Authentication failed"):
                nm.connect("X", "pw")

    def test_newline_rejected(self):
        with self.assertRaises(nm.VPNError):
            nm.connect("X", "a\nb")


class SettingsTests(unittest.TestCase):
    def test_user_overrides_system(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            sys_cfg, user_cfg = pathlib.Path(d, "a.conf"), pathlib.Path(d, "b.conf")
            sys_cfg.write_text("[vpnconnect]\nconnection_name = Acme VPN\nsession_limit_minutes = 30\notp = yes\n")
            user_cfg.write_text("[vpnconnect]\nsession_limit_minutes = bogus\ndisconnect_on_exit = no\n")
            s = settings.load([sys_cfg, user_cfg])
        self.assertEqual(s.connection_name, "Acme VPN")
        self.assertEqual(s.session_limit_minutes, 30)  # invalid user value ignored
        self.assertTrue(s.otp)
        self.assertFalse(s.disconnect_on_exit)


class CliTests(unittest.TestCase):
    def setUp(self):
        # Hermetic: never read the developer's real /etc or ~/.config settings.
        empty = settings.SYSTEM_DIR / "__vpnconnect_test_does_not_exist__.conf"
        for name in ("SYSTEM_CONFIG", "USER_CONFIG"):
            patcher = mock.patch.object(settings, name, empty)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch("sys.stdout")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_status_exit_codes(self):
        with mock.patch.object(nm, "check_requirements", return_value=[]), \
             mock.patch.object(nm, "status", return_value=nm.Status(True, "connected", "alice")):
            self.assertEqual(cli.main(["status"]), 0)
        with mock.patch.object(nm, "check_requirements", return_value=[]), \
             mock.patch.object(nm, "status", return_value=nm.Status(True, "disconnected")):
            self.assertEqual(cli.main(["status"]), 3)

    def test_missing_requirements(self):
        with mock.patch.object(nm, "check_requirements", return_value=["no plugin"]), \
             mock.patch("sys.stderr"):
            self.assertEqual(cli.main(["status"]), 2)


if __name__ == "__main__":
    unittest.main()
