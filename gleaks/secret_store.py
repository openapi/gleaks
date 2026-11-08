"""API keys live in the desktop keyring (libsecret), never in the profile file.

Inside the Flatpak sandbox libsecret goes through the Secret portal by itself,
so the manifest needs no keyring permission. These calls can block on a keyring
prompt: run them off the main thread.
"""

from __future__ import annotations

import gi

gi.require_version("Secret", "1")
from gi.repository import GLib, Secret  # noqa: E402

from . import APP_ID  # noqa: E402

_SCHEMA = Secret.Schema.new(f"{APP_ID}.ProviderKey", Secret.SchemaFlags.NONE,
                            {"provider": Secret.SchemaAttributeType.STRING})


class SecretStoreError(Exception):
    """The desktop keyring is missing or refused the operation."""


def _guarded(function, *args):
    try:
        return function(*args)
    except GLib.Error as exc:
        raise SecretStoreError(exc.message) from exc


def get_api_key(provider_id: str) -> str | None:
    return _guarded(Secret.password_lookup_sync, _SCHEMA, {"provider": provider_id}, None)


def set_api_key(provider_id: str, key: str) -> None:
    _guarded(Secret.password_store_sync, _SCHEMA, {"provider": provider_id},
             Secret.COLLECTION_DEFAULT, f"GLeaks API key: {provider_id}", key, None)


def delete_api_key(provider_id: str) -> None:
    _guarded(Secret.password_clear_sync, _SCHEMA, {"provider": provider_id}, None)
