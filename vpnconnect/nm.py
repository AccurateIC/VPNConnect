"""Thin wrapper around NetworkManager (libnm for import, nmcli for everything else).

Why NetworkManager instead of running `openvpn` directly:
  * no root / sudo needed - works for every employee, not just admins;
  * DNS pushed by the VPN server is applied correctly (systemd-resolved);
  * the connection also shows up in the normal GNOME network menu.

The password is never written to disk: the profile is saved with
password-flags=2 ("always ask") and the secret is piped to nmcli on stdin.
"""

from __future__ import annotations

import getpass
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

OPENVPN_SERVICE = "org.freedesktop.NetworkManager.openvpn"
CONNECT_TIMEOUT = 60


class VPNError(Exception):
    pass


@dataclass
class Status:
    exists: bool
    state: str  # "disconnected", "connecting", "connected", "missing"
    username: str = ""

    @property
    def connected(self) -> bool:
        return self.state == "connected"


def _run(args: list[str], *, input: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["nmcli", *args], input=input, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError as exc:
        raise VPNError("NetworkManager (nmcli) is not installed.") from exc
    except subprocess.TimeoutExpired as exc:
        raise VPNError("Timed out waiting for NetworkManager.") from exc


def _err(proc: subprocess.CompletedProcess) -> str:
    return (proc.stderr or proc.stdout).strip() or f"nmcli exited with code {proc.returncode}"


def check_requirements() -> list[str]:
    """Return a list of human-readable problems (empty if everything is fine)."""
    problems = []
    if not shutil.which("nmcli"):
        problems.append("NetworkManager is not installed (package: network-manager).")
    if not any(
        Path(d, "nm-openvpn-service.name").exists()
        for d in ("/usr/lib/NetworkManager/VPN", "/etc/NetworkManager/VPN")
    ):
        problems.append(
            "The NetworkManager OpenVPN plugin is missing (package: network-manager-openvpn-gnome)."
        )
    return problems


# Lines some VPN gateways write into .ovpn files that NetworkManager's importer rejects,
# although NetworkManager already does what they ask:
#   Sophos Firewall: "route remote_host 255.255.255.255 net_gateway" (reach the VPN server
#   itself via the normal gateway). NetworkManager adds that route on its own.
_UNSUPPORTED_LINES = [re.compile(r"^\s*route\s+remote_host\b")]


def compatible_copy(ovpn: Path) -> Path | None:
    """A private copy of `ovpn` without lines NetworkManager can't import, or None if none.

    The copy holds the user's key material, so it goes in a fresh 0700 directory under
    XDG_RUNTIME_DIR (tmpfs, per user) as a 0600 file, and the caller deletes it right after
    import. It keeps the original file name, so the certificates NetworkManager extracts get
    the same names as from the original.
    """
    lines = ovpn.read_text(errors="replace").splitlines(keepends=True)
    kept = [line for line in lines if not any(p.match(line) for p in _UNSUPPORTED_LINES)]
    if len(kept) == len(lines):
        return None
    folder = Path(tempfile.mkdtemp(prefix="vpnconnect-", dir=os.environ.get("XDG_RUNTIME_DIR") or None))
    copy = folder / ovpn.name
    fd = os.open(copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.writelines(kept)
    return copy


def import_profile(ovpn: str | Path, name: str, username: str = "") -> None:
    """Import an .ovpn file as a connection owned by (and visible only to) the current user.

    Replaces any existing connection with the same name.
    """
    ovpn = Path(ovpn).expanduser().resolve()
    if not ovpn.is_file():
        raise VPNError(f"File not found: {ovpn}")

    try:
        import gi

        gi.require_version("NM", "1.0")
        from gi.repository import GLib, NM
    except (ImportError, ValueError) as exc:
        raise VPNError(
            "libnm Python bindings are missing (packages: python3-gi gir1.2-nm-1.0)."
        ) from exc

    info = NM.VpnPluginInfo.new_search_file(None, OPENVPN_SERVICE)
    if info is None:
        raise VPNError("NetworkManager OpenVPN plugin not found (network-manager-openvpn-gnome).")
    copy = compatible_copy(ovpn)
    try:
        con = info.load_editor_plugin().import_(str(copy or ovpn))
    except GLib.Error as exc:
        raise VPNError(f"Could not read {ovpn.name}: {exc.message}") from exc
    finally:
        if copy is not None:
            copy.unlink(missing_ok=True)
            copy.parent.rmdir()

    s_con = con.get_setting_connection()
    s_con.set_property(NM.SETTING_CONNECTION_ID, name)
    # Owned by this user only -> no admin password needed, and colleagues on a
    # shared machine can't use or see it.
    s_con.add_permission("user", getpass.getuser(), None)
    s_con.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, False)

    s_vpn = con.get_setting_vpn()
    s_vpn.add_data_item("password-flags", "2")  # always ask, never store
    if username:
        s_vpn.add_data_item("username", username)

    delete(name, missing_ok=True)

    client = NM.Client.new(None)
    loop = GLib.MainLoop()
    result: dict = {}

    def done(c, res, _data):
        try:
            result["con"] = c.add_connection_finish(res)
        except GLib.Error as exc:
            result["error"] = exc.message
        loop.quit()

    client.add_connection_async(con, True, None, done, None)
    loop.run()
    if "error" in result:
        raise VPNError(f"NetworkManager refused the profile: {result['error']}")


def delete(name: str, *, missing_ok: bool = False) -> None:
    proc = _run(["connection", "delete", "id", name])
    if proc.returncode != 0 and not missing_ok:
        raise VPNError(_err(proc))


def set_username(name: str, username: str) -> None:
    proc = _run(["connection", "modify", "id", name, "+vpn.data", f"username={username}"])
    if proc.returncode != 0:
        raise VPNError(_err(proc))


def status(name: str) -> Status:
    proc = _run(["-t", "-f", "GENERAL.STATE,vpn.data", "connection", "show", "id", name])
    if proc.returncode != 0:
        return Status(exists=False, state="missing")
    state, username = "disconnected", ""
    for line in proc.stdout.splitlines():
        key, _, value = line.partition(":")
        if key == "GENERAL.STATE":
            state = {"activated": "connected", "activating": "connecting"}.get(value, value or state)
        elif key == "vpn.data":
            username = parse_vpn_data(value).get("username", "")
    return Status(exists=True, state=state, username=username)


def parse_vpn_data(value: str) -> dict[str, str]:
    data = {}
    for item in value.split(","):
        k, sep, v = item.partition("=")
        if sep:
            data[k.strip()] = v.strip()
    return data


def connect(name: str, password: str, username: str = "") -> None:
    if username:
        set_username(name, username)
    if "\n" in password:
        raise VPNError("Password must not contain a newline.")
    started = int(time.time()) - 1  # only this attempt's OpenVPN log lines count
    proc = _run(
        ["--wait", str(CONNECT_TIMEOUT), "connection", "up", "id", name, "passwd-file", "/dev/stdin"],
        input=f"vpn.secrets.password:{password}\n",
        timeout=CONNECT_TIMEOUT + 10,
    )
    if proc.returncode != 0:
        detail = _err(proc)
        log = recent_openvpn_log(since=started)
        if "AUTH_FAILED" in log:
            detail = "Authentication failed - check your username, password (and OTP)."
        elif log:
            detail += "\n\nOpenVPN log:\n" + log
        raise VPNError(detail)


def disconnect(name: str) -> None:
    proc = _run(["connection", "down", "id", name])
    if proc.returncode != 0 and "not an active connection" not in _err(proc):
        raise VPNError(_err(proc))


def recent_openvpn_log(lines: int = 12, since: int | None = None) -> str:
    """Best effort: nm-openvpn journal lines since `since` (epoch seconds; default the last
    2 minutes). Needs the user to be in group adm/systemd-journal.

    An old AUTH_FAILED from an earlier attempt must not make this attempt look like a
    wrong password, because that now deletes a saved password (spec-save-password).
    """
    since_arg = f"@{since}" if since is not None else "-2min"
    try:
        proc = subprocess.run(
            ["journalctl", "-t", "nm-openvpn", "--since", since_arg, "-n", str(lines), "-o", "cat", "--no-pager"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""
