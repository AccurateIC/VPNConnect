"""Settings: organisation defaults in /etc, optional per-user overrides in ~/.config."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path

SYSTEM_DIR = Path(os.environ.get("VPNCONNECT_SYSTEM_DIR", "/etc/vpnconnect"))
USER_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "vpnconnect"

SYSTEM_CONFIG = SYSTEM_DIR / "vpnconnect.conf"
USER_CONFIG = USER_DIR / "vpnconnect.conf"
# Optional company-wide profile dropped in by IT; imported automatically on first run.
SYSTEM_PROFILE = SYSTEM_DIR / "profile.ovpn"


@dataclass
class Settings:
    connection_name: str = "Company VPN"
    portal_url: str = ""
    session_limit_minutes: int = 0
    otp: bool = False
    disconnect_on_exit: bool = True
    allow_save_password: bool = True  # CR-2 / FR-SAVE-08


def _str2bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load(paths: list[Path] | None = None) -> Settings:
    """Apply each file in order; later files override earlier ones. Invalid values are ignored."""
    s = Settings()
    for path in paths or [SYSTEM_CONFIG, USER_CONFIG]:
        parser = configparser.ConfigParser()
        try:
            parser.read(path)
        except configparser.Error:
            continue
        if parser.has_section("vpnconnect"):
            _apply(s, parser["vpnconnect"])
    return s


def _apply(s: Settings, section) -> None:
    if section.get("connection_name", "").strip():
        s.connection_name = section["connection_name"].strip()
    if "portal_url" in section:
        s.portal_url = section["portal_url"].strip()
    if "session_limit_minutes" in section:
        try:
            s.session_limit_minutes = max(0, int(section["session_limit_minutes"]))
        except ValueError:
            pass
    if "otp" in section:
        s.otp = _str2bool(section["otp"])
    if "disconnect_on_exit" in section:
        s.disconnect_on_exit = _str2bool(section["disconnect_on_exit"])
    if "allow_save_password" in section:
        # Can only be turned OFF by a later file: an employee's ~/.config cannot
        # re-enable saved passwords that IT disabled in /etc (CR-2 amendment 1).
        s.allow_save_password = s.allow_save_password and _str2bool(section["allow_save_password"])
