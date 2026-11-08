"""Tells the desktop that GLeaks keeps working with no window open."""

from __future__ import annotations

import logging
import os

from gi.repository import Gio, GLib

log = logging.getLogger(__name__)
_PORTAL = "org.freedesktop.portal.Desktop"
_PATH = "/org/freedesktop/portal/desktop"


def request_background(reason: str) -> None:
    """Ask the Background portal for permission. Only sandboxed apps need it."""
    if not os.path.exists("/.flatpak-info"):
        return

    def finished(connection, result):
        try:
            connection.call_finish(result)
        except GLib.Error as exc:
            log.warning("background portal: %s", exc.message)

    def connected(_source, result):
        try:
            connection = Gio.bus_get_finish(result)
        except GLib.Error as exc:
            log.warning("session bus: %s", exc.message)
            return
        options = {"reason": GLib.Variant("s", reason), "autostart": GLib.Variant("b", False)}
        connection.call(_PORTAL, _PATH, "org.freedesktop.portal.Background", "RequestBackground",
                        GLib.Variant("(sa{sv})", ("", options)), None, Gio.DBusCallFlags.NONE, -1,
                        None, finished)

    Gio.bus_get(Gio.BusType.SESSION, None, connected)
