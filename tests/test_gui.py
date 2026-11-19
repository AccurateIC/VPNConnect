"""GUI behaviour with NetworkManager stubbed. Needs a display; skipped without one."""

import os
import threading
import time
import unittest
from unittest import mock

from vpnconnect import nm, settings, ui_model

try:
    import tkinter as tk

    from vpnconnect import gui

    _root = tk.Tk() if (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) else None
    if _root is not None:
        _root.destroy()
    HAVE_DISPLAY = _root is not None
except Exception:  # no tkinter or no usable display
    HAVE_DISPLAY = False

PASSWORD, CODE = "hunter2-S3cret", "987654"
# Keep every App alive for the whole run: if a worker thread dropped the last
# reference, Tk objects would be freed off the main thread and Tcl aborts.
_KEEP = []


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.st = nm.Status(True, "disconnected", "alex")
        self.calls = []
        patches = [
            mock.patch.object(nm, "status", side_effect=lambda name: self._status()),
            mock.patch.object(nm, "connect", side_effect=self._connect),
            mock.patch.object(nm, "disconnect", side_effect=lambda name: self.calls.append("disconnect")),
            mock.patch.object(nm, "_run", side_effect=AssertionError("real nmcli reached")),
            mock.patch.object(ui_model, "newest_profile", return_value=None),
            mock.patch.object(settings, "SYSTEM_PROFILE", settings.SYSTEM_DIR / "__none__.ovpn"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.status_error = None
        self.connect_error = None
        self.connect_gate = threading.Event()
        self.connect_gate.set()
        self.threads_before = threading.active_count()
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self._teardown)

    def _teardown(self):
        self.connect_gate.set()
        end = time.time() + 5  # let this test's worker threads finish first
        while threading.active_count() > self.threads_before and time.time() < end:
            try:
                self.root.update()
            except tk.TclError:
                pass
            time.sleep(0.01)
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _status(self):
        if self.status_error:
            raise self.status_error
        return self.st

    def _connect(self, name, password, username=""):
        self.calls.append(("connect", password))
        self.connect_gate.wait(5)
        if self.connect_error:
            raise self.connect_error

    def app(self, **cfg):
        a = gui.App(self.root, settings.Settings(**cfg))
        _KEEP.append(a)
        self.pump(lambda: not a.busy and a.loaded or a.load_failed)
        return a

    def pump(self, until, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            self.root.update()
            if until():
                return
            time.sleep(0.01)
        self.fail("condition not reached")

    def log_text(self, app):
        return app.log_box.get("1.0", "end")

    # BR-GUI-01
    def test_password_never_in_details_and_fields_cleared(self):
        app = self.app(otp=True)
        self.assertEqual(app.screen, ui_model.SIGN_IN)
        self.assertEqual(app.username.get(), "alex")  # FR-GUI-03 pre-filled
        self.connect_error = nm.VPNError("Authentication failed - check your username, password (and OTP).")
        app.password.insert(0, PASSWORD)
        app.otp.insert(0, CODE)
        app.on_connect()
        self.assertEqual(app.password.get(), "")
        self.assertEqual(app.otp.get(), "")
        self.pump(lambda: not app.busy)
        self.assertEqual(self.calls[0], ("connect", PASSWORD + CODE))
        self.assertNotIn(PASSWORD, self.log_text(app))
        self.assertNotIn(CODE, self.log_text(app))
        self.assertEqual(app.error, ui_model.ERRORS["auth"])  # US-GUI-4
        self.assertEqual(app.password.get(), "")
        self.assertEqual(str(app.password.cget("exportselection")), "0")

    def test_empty_fields_send_nothing(self):
        app = self.app(otp=True)
        app.password.insert(0, PASSWORD)
        app.on_connect()  # no code typed
        self.assertEqual(self.calls, [])
        self.assertIsNotNone(app.error)

    # BR-GUI-02 / audit finding 1
    def test_status_crash_after_failed_connect_unlocks_ui(self):
        app = self.app()
        self.connect_error = nm.VPNError("Error: activation failed")
        self.status_error = PermissionError("nmcli")
        app.password.insert(0, PASSWORD)
        app.on_connect()
        self.pump(lambda: not app.busy)
        self.assertFalse(app.connecting)
        self.assertEqual(str(app.connect_btn.cget("text")), "Connect")

    # audit finding 4
    def test_status_unreadable_at_start_shows_problem_not_checking(self):
        self.status_error = nm.VPNError("Timed out waiting for NetworkManager.")
        app = self.app()
        self.assertEqual(app.screen, "problem")
        self.assertEqual(app.error, ui_model.ERRORS["timeout"])
        self.status_error = None
        app.on_retry()
        self.pump(lambda: app.screen == ui_model.SIGN_IN)

    # FR-GUI-09 / audit finding 2
    def test_close_while_connecting_disconnects_and_stays_locked(self):
        app = self.app()
        self.connect_gate.clear()
        app.password.insert(0, PASSWORD)
        app.on_connect()
        app.on_close()
        self.assertTrue(app.closing)
        self.connect_gate.set()
        self.pump(lambda: "disconnect" in self.calls)
        app.on_connect()  # ignored while closing
        self.assertEqual([c for c in self.calls if c != "disconnect"], [("connect", PASSWORD)])

    # FR-GUI-10 / audit finding 3
    def test_session_limit_retries_failed_disconnect(self):
        self.st = nm.Status(True, "connected", "alex")
        app = self.app(session_limit_minutes=1)
        self.assertEqual(app.screen, ui_model.CONNECTED)
        app.connected_at -= 61
        nm.disconnect.side_effect = nm.VPNError("busy")
        app._tick()
        self.pump(lambda: not app.busy)
        self.assertIsNotNone(app.connected_at)
        app.limit_retry_at = 0
        nm.disconnect.side_effect = lambda name: self.calls.append("disconnect")
        app._tick()
        self.pump(lambda: "disconnect" in self.calls)

    # FR-TRAY-05
    def test_window_from_tray_closes_without_disconnecting(self):
        self.st = nm.Status(True, "connected", "alex")
        a = gui.App(self.root, settings.Settings(disconnect_on_exit=True), from_tray=True)
        _KEEP.append(a)
        self.pump(lambda: a.loaded and not a.busy)
        a.on_close()
        self.assertNotIn("disconnect", self.calls)

    def test_real_sigusr1_raises_window(self):
        import signal as sig

        app = self.app()
        old = sig.getsignal(sig.SIGUSR1)
        self.addCleanup(sig.signal, sig.SIGUSR1, old)
        gui.install_raise_handler(app)
        with mock.patch.object(app, "bring_to_front") as front:
            os.kill(os.getpid(), sig.SIGUSR1)
            self.pump(lambda: front.called)

    def test_unexpected_drop_shows_note(self):
        self.st = nm.Status(True, "connected", "alex")
        app = self.app()
        self.st = nm.Status(True, "disconnected", "alex")
        app._apply_status(self.st)
        self.assertIn("dropped", app.notice)
        self.assertEqual(app.screen, ui_model.SIGN_IN)

    def test_setup_screen_without_profile(self):
        self.st = nm.Status(False, "missing")
        app = self.app(portal_url="https://portal.invalid")
        self.assertEqual(app.screen, ui_model.SETUP)  # FR-GUI-01
        labels = [str(b.cget("text")) for b in app.setup_buttons]
        self.assertEqual(labels[0], "Choose VPN file...")


if __name__ == "__main__":
    unittest.main()
