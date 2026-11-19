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
        # audit finding 1: SIGUSR1 is ignored before anything else runs in the child
        self.assertTrue(cmd[3].startswith("import signal; signal.signal(signal.SIGUSR1, signal.SIG_IGN)"))
        self.assertEqual(cmd[1], "-I")
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

    def test_held_lock_without_pid_never_starts_second_tray(self):  # audit finding 7
        lock = tray.acquire_lock(tray.runtime_dir() / "tray.lock")
        self.addCleanup(lock.close)
        (tray.runtime_dir() / "tray.lock").write_text("")
        with mock.patch.object(tray, "load_indicator") as load, mock.patch.object(tray.time, "sleep"):
            self.assertEqual(tray.run(self.cfg, open_window=True), 0)
        load.assert_not_called()

    def test_open_signal_during_startup_is_remembered(self):  # audit finding 2
        import signal as sig

        old = sig.getsignal(sig.SIGUSR1)
        self.addCleanup(sig.signal, sig.SIGUSR1, old)

        def slow_gtk_import():
            os.kill(os.getpid(), sig.SIGUSR1)  # someone opens VPNConnect right now
            return mock.MagicMock(), mock.MagicMock(), mock.MagicMock()

        with mock.patch.object(tray, "load_indicator", side_effect=slow_gtk_import), \
             mock.patch.object(tray, "wait_for_icon_host", return_value=True), \
             mock.patch.object(tray, "Tray") as Tray:
            self.assertEqual(tray.run(self.cfg), 0)
        Tray.return_value.open_window.assert_called_once()

    def test_no_icon_host_falls_back_to_window(self):  # audit finding 5
        libs = (mock.MagicMock(), mock.MagicMock(), mock.MagicMock())
        with mock.patch.object(tray, "load_indicator", return_value=libs), \
             mock.patch.object(tray, "wait_for_icon_host", return_value=False), \
             mock.patch("vpnconnect.gui.run", return_value=0) as window:
            self.assertEqual(tray.run(self.cfg, open_window=True), 0)
        window.assert_called_once_with(self.cfg)
        with mock.patch.object(tray, "load_indicator", return_value=libs), \
             mock.patch.object(tray, "wait_for_icon_host", return_value=False), \
             mock.patch("sys.stderr"):
            self.assertEqual(tray.run(self.cfg), 2)

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

    def run_quit(self, t, now_status, disconnect=None):
        with mock.patch.object(nm, "status", return_value=now_status), \
             mock.patch.object(nm, "disconnect", side_effect=disconnect) as disc, \
             mock.patch.object(tray.threading, "Thread") as Thread:
            Thread.side_effect = lambda target, daemon: mock.Mock(start=target)
            t.quit()
        return disc

    def test_quit_disconnects_when_policy_says_so(self):  # FR-TRAY-06
        for policy, expected in ((True, 1), (False, 0)):
            t, Gtk = self.make(disconnect_on_exit=policy)
            child = mock.Mock()
            child.poll.return_value = None
            t.child = child
            disc = self.run_quit(t, nm.Status(True, "connected", "alex"))
            self.assertEqual(disc.call_count, expected)
            child.terminate.assert_called_once()  # window closed first
            Gtk.main_quit.assert_called_once()

    def test_quit_reads_fresh_status_not_last_poll(self):  # audit finding 3
        t, _ = self.make(disconnect_on_exit=True)
        t.status = nm.Status(True, "disconnected")  # stale poll
        disc = self.run_quit(t, nm.Status(True, "connecting"))
        self.assertEqual(disc.call_count, 1)

    def test_quit_finishes_even_if_disconnect_crashes(self):  # audit finding 3
        t, Gtk = self.make(disconnect_on_exit=True)
        self.run_quit(t, nm.Status(True, "connected"), disconnect=PermissionError("nmcli"))
        Gtk.main_quit.assert_called_once()

    def test_logout_signal_counts_as_quit(self):  # BR-TRAY-04
        t, _ = self.make(disconnect_on_exit=True)
        with mock.patch.object(t, "quit") as q:
            self.assertTrue(t._on_stop_signal())
        q.assert_called_once()

    def test_closed_window_is_reaped(self):  # audit finding 8
        t, _ = self.make()
        child = mock.Mock()
        child.poll.return_value = 0
        t.child = child
        t._poll()
        self.assertIsNone(t.child)


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
