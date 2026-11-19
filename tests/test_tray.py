import os
import signal
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vpnconnect import cli, nm, settings, tray


class ViewTests(unittest.TestCase):
    """FR-TRAY-02 / FR-TRAY-03"""

    def test_icons_and_lines(self):
        self.assertEqual(tray.view(nm.Status(True, "connected", "alex")),
                         (tray.ICON_CONNECTED, "Connected as alex", True))
        self.assertEqual(tray.view(nm.Status(True, "connecting")),
                         (tray.ICON_CONNECTING, "Connecting...", True))
        self.assertEqual(tray.view(nm.Status(True, "disconnected")),
                         (tray.ICON_OFF, "Not connected", False))
        self.assertEqual(tray.view(nm.Status(False, "missing")),
                         (tray.ICON_OFF, "Not set up yet", False))


class LockTests(unittest.TestCase):
    """FR-TRAY-01: one tray per session."""

    def test_second_lock_fails_and_pid_is_ours(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "tray.lock")
            first = tray.acquire_lock(path)
            self.assertIsNotNone(first)
            self.assertIsNone(tray.acquire_lock(path))
            self.assertEqual(tray.running_pid(path), os.getpid())
            first.close()
            again = tray.acquire_lock(path)
            self.assertIsNotNone(again)
            again.close()

    def test_dead_or_garbage_pid(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "tray.lock")
            path.write_text("not-a-pid")
            self.assertIsNone(tray.running_pid(path))
            self.assertIsNone(tray.running_pid(Path(d, "missing")))

    def test_window_command_runs_gui_from_tray(self):
        cmd = tray.window_command()
        self.assertEqual(cmd[-2:], ["gui", "--from-tray"])
        self.assertIn(str(Path(tray.__file__).resolve().parent.parent), cmd[3])


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": self.tmp.name})
        p.start()
        self.addCleanup(p.stop)
        self.cfg = settings.Settings()

    def test_no_bindings_exits_2(self):  # FR-TRAY-09
        with mock.patch.object(tray, "load_indicator", return_value=None), mock.patch("sys.stderr"):
            self.assertEqual(tray.run(self.cfg), 2)

    def test_no_bindings_open_falls_back_to_window(self):  # FR-TRAY-07
        with mock.patch.object(tray, "load_indicator", return_value=None), \
             mock.patch("vpnconnect.gui.run", return_value=0) as window:
            self.assertEqual(tray.run(self.cfg, open_window=True), 0)
        window.assert_called_once_with(self.cfg)

    def test_running_tray_is_asked_to_open(self):  # FR-TRAY-07
        lock = tray.acquire_lock(tray.runtime_dir() / "tray.lock")
        self.addCleanup(lock.close)
        with mock.patch.object(tray, "running_pid", return_value=4242), \
             mock.patch.object(tray.os, "kill") as kill, \
             mock.patch.object(tray, "load_indicator") as load:
            self.assertEqual(tray.run(self.cfg, open_window=True), 0)
        kill.assert_called_once_with(4242, signal.SIGUSR1)
        load.assert_not_called()

    def test_second_autostart_is_a_no_op(self):
        lock = tray.acquire_lock(tray.runtime_dir() / "tray.lock")
        self.addCleanup(lock.close)
        with mock.patch.object(tray, "load_indicator") as load:
            self.assertEqual(tray.run(self.cfg), 0)
        load.assert_not_called()


class TrayActionTests(unittest.TestCase):
    """FR-TRAY-04 / FR-TRAY-06 with a fake GTK."""

    def make(self, **cfg):
        Gtk, GLib, AI = mock.MagicMock(), mock.MagicMock(), mock.MagicMock()
        GLib.idle_add.side_effect = lambda fn, *a: fn(*a)
        with mock.patch.object(nm, "status", return_value=nm.Status(True, "connected", "alex")), \
             mock.patch.object(tray.threading, "Thread") as Thread:
            Thread.side_effect = lambda target, daemon: mock.Mock(start=target)
            t = tray.Tray(settings.Settings(**cfg), Gtk, GLib, AI)
        return t, Gtk

    def test_open_starts_one_window_then_raises_it(self):
        t, _ = self.make()
        child = mock.Mock()
        child.poll.return_value = None
        with mock.patch.object(tray.subprocess, "Popen", return_value=child) as popen:
            t.open_window()
            t.open_window()
        popen.assert_called_once()
        child.send_signal.assert_called_once_with(signal.SIGUSR1)

    def test_poll_applies_status(self):
        t, _ = self.make()
        self.assertTrue(t.status.connected)
        t.indicator.set_icon_full.assert_called_with(tray.ICON_CONNECTED, "Connected as alex")

    def test_quit_disconnects_when_policy_says_so(self):
        for policy, expected in ((True, 1), (False, 0)):
            t, Gtk = self.make(disconnect_on_exit=policy)
            with mock.patch.object(nm, "disconnect") as disc, \
                 mock.patch.object(tray.threading, "Thread") as Thread:
                Thread.side_effect = lambda target, daemon: mock.Mock(start=target)
                t.quit()
            self.assertEqual(disc.call_count, expected)
            Gtk.main_quit.assert_called_once()


class CliTrayTests(unittest.TestCase):
    def test_tray_open_missing_requirements_shows_window(self):
        with mock.patch.object(nm, "check_requirements", return_value=["no plugin"]), \
             mock.patch("vpnconnect.gui.show_problems") as show, mock.patch("sys.stderr"):
            self.assertEqual(cli.main(["tray", "--open"]), 2)
        show.assert_called_once()

    def test_autostart_tray_missing_requirements_stays_quiet(self):
        with mock.patch.object(nm, "check_requirements", return_value=["no plugin"]), \
             mock.patch("vpnconnect.gui.show_problems") as show, mock.patch("sys.stderr"):
            self.assertEqual(cli.main(["tray"]), 2)
        show.assert_not_called()


if __name__ == "__main__":
    unittest.main()
