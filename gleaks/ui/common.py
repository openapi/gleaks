"""Small helpers shared by the interface.

Identifiers and provider responses are untrusted text. Libadwaita rows and
toasts parse Pango markup by default, so every one here is built with markup off.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from ..core.models import (  # noqa: E402
    Action,
    ActionStatus,
    describe_action,
    describe_error,
    describe_status,
)
from ..i18n import _, ngettext  # noqa: E402

log = logging.getLogger(__name__)


def run_async(work: Callable[[], object], on_done: Callable[[object], None],
              on_error: Callable[[Exception], None]) -> None:
    """Run ``work`` on a thread and deliver its result on the main loop."""

    def deliver(callback, value):
        callback(value)
        return GLib.SOURCE_REMOVE

    def runner():
        try:
            result = work()
        except Exception as exc:  # Handed to on_error, which reports it.
            GLib.idle_add(deliver, on_error, exc)
        else:
            GLib.idle_add(deliver, on_done, result)

    threading.Thread(target=runner, daemon=True).start()


def action_row(title: str, subtitle: str = "", activatable: bool = False) -> Adw.ActionRow:
    return Adw.ActionRow(title=title, subtitle=subtitle, use_markup=False,
                         activatable=activatable, subtitle_lines=3)


def boxed_list() -> Gtk.ListBox:
    box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
    box.add_css_class("boxed-list")
    return box


def clamped(child: Gtk.Widget) -> Gtk.ScrolledWindow:
    """Center a page's content at a readable width, scrolling when needed."""
    clamp = Adw.Clamp(child=child, maximum_size=760, margin_top=18, margin_bottom=24,
                      margin_start=12, margin_end=12)
    return Gtk.ScrolledWindow(child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)


def format_datetime(value: str | None) -> str:
    if not value:
        return _("Unknown")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime(
            "%x %H:%M")
    except ValueError:
        return _("Unknown")


def format_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
    except ValueError:
        return ""


def describe_check(status: str | None, error_code: str | None, found: int,
                   completed_at: str | None) -> str:
    if status is None:
        return _("Not checked yet")
    when = format_datetime(completed_at)
    if status == "failed":
        return _("Check failed on {date}: {reason}").format(
            date=when, reason=describe_error(error_code or ""))
    if status == "running":
        return _("Search in progress, see Activity")
    if status == "cancelled":
        return _("Check cancelled on {date}").format(date=when)
    if found:
        return ngettext("Known to the source in {count} event, checked on {date}",
                        "Known to the source in {count} events, checked on {date}",
                        found).format(count=found, date=when)
    return _("Nothing known to the source, checked on {date}").format(date=when)


_STATUSES = list(ActionStatus)


def add_status_selector(row: Adw.ActionRow, action: Action,
                        on_change: Callable[[int, ActionStatus], None]) -> None:
    """Add a drop-down that sets an action's status to ``row``."""
    selector = Gtk.DropDown.new_from_strings([describe_status(s) for s in _STATUSES])
    selector.set_valign(Gtk.Align.CENTER)
    selector.set_selected(_STATUSES.index(action.status))
    selector.update_property([Gtk.AccessibleProperty.LABEL], [describe_action(action.type)])

    def changed(dropdown, _pspec):
        on_change(action.id, _STATUSES[dropdown.get_selected()])

    selector.connect("notify::selected", changed)
    row.add_suffix(selector)
