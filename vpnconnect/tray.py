"""Top-bar VPN icon (spec-tray). Lives next to wifi / sound / battery.

GNOME shows it through the AppIndicator extension (on by default on Ubuntu).
Clicking the icon opens a small menu; "Open VPNConnect" (or a middle-click)
shows the window, which runs as a separate child process (Tk and GTK do not
share a process here).

Threading (BR-TRAY-02): NetworkManager and keyring calls run in worker threads;
results reach GTK through GLib.idle_add. The tray never asks for a password; its
one-click Connect (FR-SAVE-07) reads the user's opted-in saved password from the
keyring inside the worker and hands it to NetworkManager on stdin (BR-SAVE-01).

Signals: SIGUSR1 means "open the window". Its default action kills a process,
so both the tray and the window child neutralise it before anyone can learn
their pid (the tray before it writes the lock, the child before Python even
imports the app).
"""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import keyring_store, nm, settings, ui_model

POLL_SECONDS = 3  # FR-TRAY-02
HOST_WAIT_SECONDS = 20  # autostart may run before GNOME has loaded the extension
ICON_CONNECTED = "network-vpn-symbolic"
ICON_CONNECTING = "network-vpn-acquiring-symbolic"
ICON_OFF = "network-vpn-disconnected-symbolic"
WATCHER = "org.kde.StatusNotifierWatcher"


# ---- Gtk-free logic (BR-TRAY-03) ----------------------------------------------------
def view(status: nm.Status) -> tuple[str, str, bool]:
    """(icon name, status line, show Disconnect) for a status. FR-TRAY-02 / FR-TRAY-03."""
    if status.connected:
        line = f"Connected as {status.username}" if status.username else "Connected"
        return ICON_CONNECTED, line, True
    if status.state == "connecting":
        return ICON_CONNECTING, "Connecting...", True
    if not status.exists:
        return ICON_OFF, "Not set up yet", False
    return ICON_OFF, "Not connected", False


def is_active(status: nm.Status) -> bool:
    return status.connected or status.state == "connecting"


def runtime_dir() -> Path:
    """Per-user private dir for the lock. Never a shared, guessable /tmp path."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    path = Path(base) / "vpnconnect" if base else Path.home() / ".cache" / "vpnconnect"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def acquire_lock(path: Path):
    """Single instance per session (FR-TRAY-01). Returns the open lock file, or None if taken."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    fh = os.fdopen(fd, "r+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def running_pid(path: Path) -> int | None:
    """Pid of the tray holding the lock, if it is alive."""
    try:
        pid = int(path.read_text().strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        return None
    return pid


def window_command(error: str | None = None) -> list[str]:
    """The window as a child process, from the same install as this tray (FR-TRAY-04).

    SIGUSR1 is ignored first thing, so an Open that arrives while the window is
    still starting cannot kill it; gui.run installs the real handler later.
    """
    root = str(Path(__file__).resolve().parent.parent)
    boot = (
        "import signal; signal.signal(signal.SIGUSR1, signal.SIG_IGN); "
        f"import sys; sys.path.insert(0, {root!r}); "
        "from vpnconnect.cli import main; sys.exit(main())"
    )
    cmd = [sys.executable, "-I", "-c", boot, "gui", "--from-tray"]
    if error in ui_model.ERRORS:  # only a known category name, never raw error text
        cmd += ["--error", error]
    return cmd


def load_indicator():
    """(Gtk, GLib, AppIndicator) or None when the bindings are not installed."""
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import GLib, Gtk
    except (ImportError, ValueError):
        return None
    for name in ("AyatanaAppIndicator3", "AppIndicator3"):
        try:
            gi.require_version(name, "0.1")
            module = __import__("gi.repository", fromlist=[name])
            return Gtk, GLib, getattr(module, name)
        except (ImportError, ValueError, AttributeError):
            continue
    return None


def has_icon_host(GLib) -> bool:
    """Is something on the session bus able to show our icon (the AppIndicator extension)?"""
    try:
        from gi.repository import Gio

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "NameHasOwner", GLib.Variant("(s)", (WATCHER,)), GLib.VariantType("(b)"),
            Gio.DBusCallFlags.NONE, 1000, None,
        )
        return bool(reply.unpack()[0])
    except Exception:  # cannot tell: assume yes rather than hide the icon
        return True


def wait_for_icon_host(GLib, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while True:
        if has_icon_host(GLib):
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(1)


# ---- the indicator --------------------------------------------------------------------
class Tray:
    def __init__(self, cfg: settings.Settings, Gtk, GLib, AI):
        self.cfg, self.Gtk, self.GLib = cfg, Gtk, GLib
        self.status = nm.Status(exists=False, state="missing")
        self.child: subprocess.Popen | None = None
        self.polling = False
        self.quitting = False

        self.indicator = AI.Indicator.new("vpnconnect", ICON_OFF, AI.IndicatorCategory.SYSTEM_SERVICES)
        self.indicator.set_title("VPNConnect")
        self.indicator.set_status(AI.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()
        self.status_item = Gtk.MenuItem(label="Checking...")
        self.status_item.set_sensitive(False)
        self.open_item = Gtk.MenuItem(label="Open VPNConnect")
        self.open_item.connect("activate", lambda _w: self.open_window())
        self.connect_item = Gtk.MenuItem(label="Connect")
        self.connect_item.connect("activate", lambda _w: self.connect())
        self.disconnect_item = Gtk.MenuItem(label="Disconnect")
        self.disconnect_item.connect("activate", lambda _w: self.disconnect())
        quit_item = Gtk.MenuItem(label="Quit VPNConnect")
        quit_item.connect("activate", lambda _w: self.quit())
        for item in (self.status_item, self.open_item, self.connect_item, self.disconnect_item,
                     Gtk.SeparatorMenuItem(), quit_item):
            menu.append(item)
        menu.show_all()
        self.disconnect_item.set_visible(False)
        self.connect_item.set_visible(False)
        self.connecting = False
        self.indicator.set_menu(menu)
        self.indicator.set_secondary_activate_target(self.open_item)  # middle-click = Open

        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._on_open_signal)
        for sig in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self._on_stop_signal)
        GLib.timeout_add_seconds(POLL_SECONDS, self._poll)
        self._poll()

    # status
    def _poll(self):
        if self.child is not None and self.child.poll() is not None:
            self.child = None  # reap a closed window (no zombies)
        if not self.polling and not self.quitting:
            self.polling = True
            threading.Thread(target=self._fetch, daemon=True).start()
        return True  # keep the timer

    def _poll_once(self):
        self._poll()
        return False

    def _fetch(self):
        try:
            st = nm.status(self.cfg.connection_name)
        except Exception:  # NetworkManager hiccup: keep the last known state
            st = None
        can_connect = st is not None and self._one_click_possible(st)
        self.GLib.idle_add(self._apply, st, can_connect)

    def _one_click_possible(self, st: nm.Status) -> bool:
        """FR-SAVE-07 (worker side): profile, not active, no OTP, allowed, password saved."""
        if not st.exists or is_active(st) or self.cfg.otp or not self.cfg.allow_save_password:
            return False
        # Existence only: never load the secret just to show a menu item (BR-SAVE-01),
        # and never trigger a keyring unlock prompt from a 3 s poll.
        return keyring_store.has_saved(self.cfg.connection_name, st.username)

    def _apply(self, st, can_connect=False):
        self.polling = False
        if st is not None:
            self.status = st
            icon, line, show_disconnect = view(st)
            if self.connecting and not is_active(st):
                icon, line = ICON_CONNECTING, "Connecting..."
            self.indicator.set_icon_full(icon, line)
            self.status_item.set_label(line)
            self.disconnect_item.set_visible(show_disconnect)
            self.connect_item.set_visible(can_connect and not self.connecting)
        return False  # run once

    # actions
    def open_window(self):
        """FR-TRAY-04: one window; raise it if it is already open."""
        if self.quitting:
            return
        if self.child is not None and self.child.poll() is None:
            self.child.send_signal(signal.SIGUSR1)
        else:
            self.child = subprocess.Popen(window_command())

    def connect(self):
        """FR-SAVE-07: one-click connect with the saved password. Failure opens the window."""
        if self.connecting or self.quitting:
            return
        self.connecting = True
        self.connect_item.set_visible(False)
        self.indicator.set_icon_full(ICON_CONNECTING, "Connecting...")
        self.status_item.set_label("Connecting...")
        conn, username = self.cfg.connection_name, self.status.username

        def job():
            ok, error = False, "generic"
            try:
                if self.quitting:
                    return
                password = keyring_store.lookup(conn, username)
                if not password:
                    error = "saved_auth"  # gone or unreadable: the window asks for it
                else:
                    nm.connect(conn, password)
                    ok = True
                    if self.quitting and self.cfg.disconnect_on_exit:
                        nm.disconnect(conn)  # Quit was chosen while we were connecting
            except nm.VPNError as exc:
                error = ui_model.classify_error(str(exc))
                if error == "auth":  # no OTP on this path, so it really is the password
                    keyring_store.forget(conn)  # FR-SAVE-05
                    error = "saved_auth"
            except Exception:
                pass
            finally:
                self.GLib.idle_add(self._connect_done, ok, error)

        threading.Thread(target=job, daemon=True).start()

    def _connect_done(self, ok: bool, error: str = "generic"):
        self.connecting = False
        if not ok and not self.quitting:
            # Show why in a fresh window (an open one may still show "Password: saved").
            if self.child is not None and self.child.poll() is None:
                self.child.terminate()
                try:
                    self.child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.child.kill()
            self.child = subprocess.Popen(window_command(error))
        self._poll()
        return False

    def disconnect(self):
        def job():
            try:
                nm.disconnect(self.cfg.connection_name)
            except Exception:
                pass
            self.GLib.idle_add(self._poll_once)  # refresh through the normal, guarded path

        threading.Thread(target=job, daemon=True).start()

    def quit(self):
        """FR-TRAY-06 / BR-TRAY-04: quitting VPNConnect honours disconnect_on_exit.

        Also used at logout (SIGTERM). The window is closed first so it cannot
        start a new connection, then the state is read fresh, never from the
        last poll.
        """
        if self.quitting:
            return
        self.quitting = True
        child = self.child

        def job():
            try:
                if child is not None and child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill()
                if self.cfg.disconnect_on_exit:
                    try:
                        if is_active(nm.status(self.cfg.connection_name)):
                            nm.disconnect(self.cfg.connection_name)
                    except Exception:
                        pass
            finally:
                self.GLib.idle_add(self._finish)

        threading.Thread(target=job, daemon=True).start()

    def _finish(self):
        if self.child is not None and self.child.poll() is None:
            self.child.kill()
        self.Gtk.main_quit()
        return False

    def _on_open_signal(self):
        self.open_window()
        return True

    def _on_stop_signal(self):
        # Logout counts as quitting VPNConnect (DECISIONS 2026-11-19, BR-TRAY-04).
        self.quit()
        return True


def _plain_window(cfg: settings.Settings) -> int:
    from .gui import run as run_window

    return run_window(cfg)


def run(cfg: settings.Settings, open_window: bool = False) -> int:
    # An "open" can arrive as soon as our pid is in the lock file, long before
    # GTK is up. Remember it instead of dying (SIGUSR1's default action).
    pending = {"open": open_window}
    signal.signal(signal.SIGUSR1, lambda *_a: pending.update(open=True))

    lock_path = runtime_dir() / "tray.lock"
    lock = acquire_lock(lock_path)
    if lock is None:  # a tray is already running in this session
        if open_window:
            for _ in range(20):  # it may not have written its pid yet
                pid = running_pid(lock_path)
                if pid:
                    os.kill(pid, signal.SIGUSR1)  # FR-TRAY-07: ask it to open the window
                    break
                time.sleep(0.05)
        return 0  # never start a second tray

    libs = load_indicator()
    if libs is not None and not wait_for_icon_host(libs[1], 0 if open_window else HOST_WAIT_SECONDS):
        libs = None  # bindings present but nothing can show the icon (extension off)
    if libs is None:
        lock.close()
        if pending["open"]:  # FR-TRAY-07: no top-bar icon possible, plain window as before
            return _plain_window(cfg)
        print("vpnconnect tray: the top bar cannot show the icon here (needs "
              "gir1.2-ayatanaappindicator3-0.1 and GNOME's AppIndicator extension).",
              file=sys.stderr)  # FR-TRAY-09
        return 2

    Gtk, GLib, AI = libs
    tray = Tray(cfg, Gtk, GLib, AI)  # installs GLib's SIGUSR1 handler
    if pending["open"]:
        tray.open_window()
    Gtk.main()
    lock.close()
    return 0
