"""Command line interface: `vpnconnect [gui|tray|import|connect|disconnect|status|remove]`."""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from . import __version__, keyring_store, nm, settings, ui_model


def _ensure_profile(cfg: settings.Settings) -> nm.Status:
    st = nm.status(cfg.connection_name)
    if not st.exists and settings.SYSTEM_PROFILE.is_file():
        print(f"Importing company profile {settings.SYSTEM_PROFILE} ...")
        nm.import_profile(settings.SYSTEM_PROFILE, cfg.connection_name)
        st = nm.status(cfg.connection_name)
    if not st.exists:
        hint = f"\nDownload your .ovpn file from: {cfg.portal_url}" if cfg.portal_url else ""
        raise nm.VPNError(
            f"No VPN profile set up yet. Run: vpnconnect import /path/to/file.ovpn{hint}"
        )
    return st


def cmd_import(args, cfg):
    nm.import_profile(args.file, cfg.connection_name, args.username or "")
    print(f"Imported '{cfg.connection_name}'. Connect with: vpnconnect connect")


def cmd_connect(args, cfg):
    st = _ensure_profile(cfg)
    if st.connected:
        print("Already connected.")
        return
    username = args.username or st.username or input("Username: ").strip()
    conn = cfg.connection_name
    if not cfg.allow_save_password:  # FR-SAVE-08
        keyring_store.forget(conn)
    saved = None
    if cfg.allow_save_password and not args.ask:  # FR-SAVE-09
        saved = keyring_store.lookup(conn, username)
    if saved:
        print(f"Using your saved password for {username} (--ask to type it instead).")
    password = saved or getpass.getpass("Password: ")
    code = getpass.getpass("OTP code: ").strip() if (args.otp or cfg.otp) else ""
    print("Connecting ...")
    try:
        nm.connect(conn, password + code, username if username != st.username else "")
    except nm.VPNError as exc:
        # With a code, AUTH_FAILED may be just a wrong code: keep the saved password.
        if saved and not code and ui_model.classify_error(str(exc)) == "auth":
            keyring_store.forget(conn)  # FR-SAVE-05
            raise nm.VPNError("Your saved password didn't work, so it was removed. "
                              "Run 'vpnconnect connect' again and type your current password.") from None
        raise
    print(f"Connected to {cfg.connection_name}. Disconnect with: vpnconnect disconnect")


def cmd_forget_password(args, cfg):
    keyring_store.forget(cfg.connection_name)
    print("Saved password forgotten.")


def cmd_disconnect(args, cfg):
    nm.disconnect(cfg.connection_name)
    print("Disconnected.")


def cmd_status(args, cfg):
    st = nm.status(cfg.connection_name)
    if not st.exists:
        print("No VPN profile imported.")
        return 1
    print(f"{cfg.connection_name}: {st.state}" + (f" (user {st.username})" if st.username else ""))
    return 0 if st.connected else 3


def cmd_remove(args, cfg):
    nm.delete(cfg.connection_name)
    keyring_store.forget(cfg.connection_name)
    print(f"Removed '{cfg.connection_name}'.")


def cmd_gui(args, cfg):
    from .gui import run

    return run(cfg, from_tray=getattr(args, "from_tray", False), error=getattr(args, "error", None))


def cmd_tray(args, cfg):
    from .tray import run

    return run(cfg, open_window=getattr(args, "open", False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vpnconnect", description="Company VPN client.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("gui", help="open the graphical client (default)")
    p.add_argument("--from-tray", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--error", choices=sorted(ui_model.ERRORS), help=argparse.SUPPRESS)
    p = sub.add_parser("tray", help="run the VPN icon in the top bar")
    p.add_argument("--open", action="store_true", help="also open the window")
    p = sub.add_parser("import", help="import your .ovpn profile")
    p.add_argument("file")
    p.add_argument("-u", "--username")
    p = sub.add_parser("connect", help="connect (prompts for password)")
    p.add_argument("-u", "--username")
    p.add_argument("--otp", action="store_true", help="also prompt for a one-time code")
    p.add_argument("--ask", action="store_true", help="type the password even if one is saved")
    sub.add_parser("disconnect", help="disconnect")
    sub.add_parser("status", help="show connection state (exit 0 when connected)")
    sub.add_parser("remove", help="delete the imported profile")
    sub.add_parser("forget-password", help="delete the saved password from your keyring")

    args = parser.parse_args(argv)
    command = args.command
    if command is None:
        command = "gui" if (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) else "status"

    problems = nm.check_requirements()
    if problems:
        print("\n".join(f"error: {p}" for p in problems), file=sys.stderr)
        print("Ask IT to run install.sh, or: sudo apt install network-manager-openvpn-gnome", file=sys.stderr)
        if command == "gui" or (command == "tray" and getattr(args, "open", False)):
            # FR-GUI-08: launched from the app menu there is no terminal, so show a window.
            try:
                from .gui import show_problems

                show_problems(problems)
            except Exception:  # no display / no tkinter: stderr above is all we can do
                pass
        return 2

    cfg = settings.load()
    handler = {
        "gui": cmd_gui, "tray": cmd_tray, "import": cmd_import, "connect": cmd_connect,
        "disconnect": cmd_disconnect, "status": cmd_status, "remove": cmd_remove,
        "forget-password": cmd_forget_password,
    }[command]
    try:
        return handler(args, cfg) or 0
    except nm.VPNError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
