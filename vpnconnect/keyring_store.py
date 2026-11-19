"""Opt-in saved password in the user's keyring (spec-save-password, BR-SAVE-01).

Uses libsecret (the Secret Service: GNOME Keyring, or KWallet's bridge). The
password lives only there: never in a file, argv, log or widget. Every
function is safe to call when no keyring exists. Errors mean "nothing saved"
and are never raised (BR-SAVE-02). These calls are D-Bus round trips and may
show an unlock prompt, so call them from worker threads, not a UI main loop.
"""

from __future__ import annotations

SCHEMA_NAME = "com.accurateic.vpnconnect.Password"

_lib = None


def _secret():
    """(Secret module, schema) or None."""
    global _lib
    if _lib is None:
        try:
            import gi

            gi.require_version("Secret", "1")
            from gi.repository import Secret

            schema = Secret.Schema.new(
                SCHEMA_NAME, Secret.SchemaFlags.NONE,
                {"connection": Secret.SchemaAttributeType.STRING,
                 "username": Secret.SchemaAttributeType.STRING},
            )
            _lib = (Secret, schema)
        except Exception:
            _lib = False
    return _lib or None


def available() -> bool:
    """Is a keyring service reachable for this user?"""
    lib = _secret()
    if lib is None:
        return False
    Secret, _ = lib
    try:
        Secret.Service.get_sync(Secret.ServiceFlags.NONE, None)
        return True
    except Exception:
        return False


def _items(connection: str, username: str | None = None):
    """Matching keyring items WITHOUT loading or unlocking their secrets (no prompt)."""
    lib = _secret()
    if lib is None:
        return []
    Secret, schema = lib
    attrs = {"connection": connection}
    if username is not None:
        attrs["username"] = username
    try:
        service = Secret.Service.get_sync(Secret.ServiceFlags.NONE, None)
        return service.search_sync(schema, attrs, Secret.SearchFlags.ALL, None) or []
    except Exception:
        return []


def has_saved(connection: str, username: str) -> bool:
    """Is a password saved for this user? Never reads the secret, never prompts.

    Use this for UI decisions; use lookup() only right before connecting (BR-SAVE-01).
    """
    return bool(username) and bool(_items(connection, username))


def lookup(connection: str, username: str) -> str | None:
    lib = _secret()
    if lib is None or not username:
        return None
    Secret, schema = lib
    try:
        value = Secret.password_lookup_sync(
            schema, {"connection": connection, "username": username}, None)
    except Exception:
        return None
    return value or None


def store(connection: str, username: str, password: str) -> bool:
    lib = _secret()
    if lib is None or not username or not password:
        return False
    Secret, schema = lib
    try:
        # Store first (replaces this user's item), so a failed store never loses the old one.
        ok = bool(Secret.password_store_sync(
            schema, {"connection": connection, "username": username},
            Secret.COLLECTION_DEFAULT, f"VPNConnect password for {username} ({connection})",
            password, None))
    except Exception:
        return False
    if ok:  # one saved password per connection: drop other users' items
        for item in _items(connection):
            try:
                if item.get_attributes().get("username") != username:
                    item.delete_sync(None)
            except Exception:
                pass
    return ok


def forget(connection: str) -> None:
    lib = _secret()
    if lib is None:
        return
    Secret, schema = lib
    try:
        Secret.password_clear_sync(schema, {"connection": connection}, None)
    except Exception:
        pass
