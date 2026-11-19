"""Top-bar VPN icon (spec-tray). Lives next to wifi / sound / battery.

GNOME shows it through the AppIndicator extension (on by default on Ubuntu).
Clicking the icon opens a small menu; "Open VPNConnect" (or a middle-click)
shows the window, which runs as a separate child process (Tk and GTK do not
share a process here).

Threading (BR-TRAY-02): NetworkManager calls run in worker threads; results
reach GTK through GLib.idle_add. The tray never touches a password (BR-TRAY-01).
"""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from . import nm, settings

POLL_SECONDS = 3  # FR-TRAY-02
ICON_CONNECTED = "network-vpn-symbolic"
ICON_CONNECTING = "network-vpn-acquiring-symbolic"
ICON_OFF = "network-vpn-disconnected-symbolic"


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


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/vpnconnect-{os.getuid()}"
    path = Path(base) / "vpnconnect"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def acquire_lock(path: Path):
    """Single instance per session (FR-TRAY-01). Returns the open lock file, or None if taken."""
    fh = open(path, "a+")
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


def window_command() -> list[str]:
    """The window as a child process, from the same install as this tray (FR-TRAY-04)."""
    root = str(Path(__file__).resolve().parent.parent)
    boot = f"import sys; sys.path.insert(0, {root!r}); from vpnconnect.cli import main; sys.exit(main())"
    return [sys.executable, "-P", "-c", boot, "gui", "--from-tray"]


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
        self.disconnect_item = Gtk.MenuItem(label="Disconnect")
        self.disconnect_item.connect("activate", lambda _w: self.disconnect())
        quit_item = Gtk.MenuItem(label="Quit VPNConnect")
        quit_item.connect("activate", lambda _w: self.quit())
        for item in (self.status_item, self.open_item, self.disconnect_item,
                     Gtk.SeparatorMenuItem(), quit_item):
            menu.append(item)
        menu.show_all()
        self.disconnect_item.set_visible(False)
        self.indicator.set_menu(menu)
        self.indicator.set_secondary_activate_target(self.open_item)  # middle-click = Open

        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._on_open_signal)
        for sig in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self._on_stop_signal)
        GLib.timeout_add_seconds(POLL_SECONDS, self._poll)
        self._poll()

    # status
    def _poll(self):
        if not self.polling and not self.quitting:
            self.polling = True
            threading.Thread(target=self._fetch, daemon=True).start()
        return True  # keep the timer

    def _fetch(self):
        try:
            st = nm.status(self.cfg.connection_name)
        except Exception:  # NetworkManager hiccup: keep the last known state
            st = None
        self.GLib.idle_add(self._apply, st)

    def _apply(self, st):
        self.polling = False
        if st is not None:
            self.status = st
            icon, line, show_disconnect = view(st)
            self.indicator.set_icon_full(icon, line)
            self.status_item.set_label(line)
            self.disconnect_item.set_visible(show_disconnect)
        return False  # run once

    # actions
    def open_window(self):
        """FR-TRAY-04: one window; raise it if it is already open."""
        if self.child is not None and self.child.poll() is None:
            self.child.send_signal(signal.SIGUSR1)
        else:
            self.child = subprocess.Popen(window_command())

    def disconnect(self):
        def job():
            try:
                nm.disconnect(self.cfg.connection_name)
            except nm.VPNError:
                pass
            self._fetch()

        threading.Thread(target=job, daemon=True).start()

    def quit(self):
        """FR-TRAY-06 / BR-TRAY-04: quitting VPNConnect honours disconnect_on_exit."""
        if self.quitting:
            return
        self.quitting = True
        active = self.status.connected or self.status.state == "connecting"

        def job():
            if active and self.cfg.disconnect_on_exit:
                try:
                    nm.disconnect(self.cfg.connection_name)
                except nm.VPNError:
                    pass
            self.GLib.idle_add(self._finish)

        threading.Thread(target=job, daemon=True).start()

    def _finish(self):
        if self.child is not None and self.child.poll() is None:
            self.child.terminate()
        self.Gtk.main_quit()
        return False

    def _on_open_signal(self):
        self.open_window()
        return True

    def _on_stop_signal(self):
        # Logout / kill: just go away. The session ending is not "quit VPNConnect".
        self._finish()
        return False


def run(cfg: settings.Settings, open_window: bool = False) -> int:
    lock_path = runtime_dir() / "tray.lock"
    lock = acquire_lock(lock_path)
    if lock is None:  # a tray is already running in this session
        if open_window:
            pid = running_pid(lock_path)
            if pid:
                os.kill(pid, signal.SIGUSR1)  # FR-TRAY-07: ask it to open the window
                return 0
        else:
            return 0

    libs = load_indicator()
    if libs is None:
        if lock is not None:
            lock.close()
        if open_window:  # FR-TRAY-07: no top-bar support, plain window as before
            from .gui import run as run_window

            return run_window(cfg)
        print("vpnconnect tray: top-bar icon support is not installed "
              "(gir1.2-ayatanaappindicator3-0.1).", file=sys.stderr)  # FR-TRAY-09
        return 2

    Gtk, GLib, AI = libs
    tray = Tray(cfg, Gtk, GLib, AI)
    if open_window:
        tray.open_window()
    Gtk.main()
    if lock is not None:
        lock.close()
    return 0
