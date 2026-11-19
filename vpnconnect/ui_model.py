"""Tk-free logic behind the GUI (BR-GUI-03): which screen to show, friendly
error text, finding a downloaded profile, and time formatting.

Nothing here imports tkinter, so it is unit-tested without a display.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import nm

# FR-GUI-01: the three screens.
SETUP = "setup"
SIGN_IN = "sign_in"
CONNECTED = "connected"


def screen_for(status: nm.Status) -> str:
    """FR-GUI-01: pick the screen from the NetworkManager status."""
    if not status.exists:
        return SETUP
    if status.connected:
        return CONNECTED
    return SIGN_IN


@dataclass(frozen=True)
class Friendly:
    """FR-GUI-06: one headline plus one next step. Raw text goes to Details only."""

    headline: str
    next_step: str


# Prefix the GUI puts on an auth failure that happened with the saved password.
SAVED_REJECTED = "The saved password was rejected and has been forgotten: "

ERRORS = {
    "saved_auth": Friendly(
        "Your saved password didn't work, so it was removed.",
        "Type your current password.",
    ),
    "auth": Friendly(
        "Wrong username, password or code.",
        "Use exactly the login of the VPN portal (capital letters matter). "
        "Too many tries can block you for a while. If you use a code, wait for a new one.",
    ),
    "plugin": Friendly(
        "This computer is missing the VPN add-on.",
        "Ask IT to run the VPNConnect installer on this computer.",
    ),
    "timeout": Friendly(
        "The VPN server did not answer in time.",
        "Check that you are online. If you just typed a wrong password a few times, the "
        "server may block you for a while: wait 10 minutes, then try once.",
    ),
    "nm_missing": Friendly(
        "This computer's network manager was not found.",
        "Ask IT to run the VPNConnect installer on this computer.",
    ),
    "file": Friendly(
        "That file is not a VPN file we can use.",
        "Download your .ovpn file from the VPN portal again and choose it.",
    ),
    "generic": Friendly(
        "Something went wrong.",
        "Try again. If it keeps happening, open Details and send them to IT.",
    ),
}


def classify_error(message: str) -> str:
    """Map a raw VPNError message to an ERRORS key."""
    # Judge only our own message: nm.connect appends the raw OpenVPN log, whose
    # lines (e.g. PLUGIN_INIT) must not be mistaken for a missing plugin.
    if message.startswith(SAVED_REJECTED):
        return "saved_auth"
    head, _, log = message.partition("OpenVPN log:")
    text = head.lower()
    # FR-SAVE-10: nmcli's own reason too, not only the journal most users can't read.
    if any(k in text for k in ("authentication failed", "login failed", "login/authentication")) \
            or "auth_failed" in log.lower():
        return "auth"
    if "plugin" in text or "network-manager-openvpn" in text or "libnm" in text:
        return "plugin"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "nmcli" in text and "not installed" in text:
        return "nm_missing"
    if "could not read" in text or "file not found" in text or "refused the profile" in text:
        return "file"
    return "generic"


def friendly_error(message: str, otp: bool = True) -> Friendly:
    kind = classify_error(message)
    if kind == "auth" and not otp:
        return Friendly("Wrong username or password.",
                        "Use exactly the login of the VPN portal (capital letters matter). "
                        "Too many tries can block you for a while.")
    return ERRORS[kind]


def downloads_dir() -> Path:
    """OQ-GUI-02 assumption: the XDG download dir, else ~/Downloads."""
    try:
        proc = subprocess.run(
            ["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=2
        )
        path = proc.stdout.strip()
        if proc.returncode == 0 and path and Path(path) != Path.home():
            return Path(path)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path.home() / "Downloads"


def newest_profile(folder: Path | None = None) -> Path | None:
    """FR-GUI-02: newest *.ovpn directly inside the downloads folder, or None."""
    folder = folder or downloads_dir()
    try:
        files = [
            p for p in folder.iterdir()
            if p.suffix.lower() == ".ovpn" and p.is_file() and os.access(p, os.R_OK)
        ]
    except OSError:
        return None
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def format_duration(seconds: float) -> str:
    """FR-GUI-04: 0:42 / 12:05 / 1:02:03."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def minutes_left(limit_minutes: int, elapsed_seconds: float) -> int | None:
    """FR-GUI-04: whole minutes until the session limit (rounded up), None when no limit."""
    if limit_minutes <= 0:
        return None
    remaining = limit_minutes * 60 - elapsed_seconds
    return max(0, -(-int(remaining) // 60))


def format_minutes(minutes: int) -> str:
    """FR-GUI-04: 45 min / 8 h / 1 h 30 min."""
    h, m = divmod(max(0, minutes), 60)
    if not h:
        return f"{m} min"
    return f"{h} h" if not m else f"{h} h {m} min"
