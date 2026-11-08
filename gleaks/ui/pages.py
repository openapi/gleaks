"""The four views of an open profile. Each one redraws itself in ``refresh``."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Pango  # noqa: E402

from ..core.models import (  # noqa: E402
    ActionStatus,
    EventKind,
    LogEntry,
    describe_action,
    describe_identifier_type,
)
from ..core.profile import DuplicateIdentifierError, Profile  # noqa: E402
from ..i18n import _  # noqa: E402
from ..providers.base import ExposureProvider  # noqa: E402
from .common import (  # noqa: E402
    action_row,
    add_status_selector,
    boxed_list,
    clamped,
    describe_check,
    format_time,
)


class _Page(Gtk.Stack):
    """A page that shows an explanation instead of an empty list."""

    def __init__(self, icon: str, title: str, description: str):
        super().__init__(vexpand=True)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.add_named(clamped(self.content), "content")
        self.add_named(Adw.StatusPage(icon_name=icon, title=title, description=description),
                       "empty")

    def show_empty(self, empty: bool) -> None:
        self.set_visible_child_name("empty" if empty else "content")


class DashboardPage(Gtk.Box):
    def __init__(self, source_names: dict[str, str]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self._source_names = source_names
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.append(clamped(body))
        self._tiles = {}
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           max_children_per_line=4, min_children_per_line=2,
                           column_spacing=12, row_spacing=12)
        for key, label in (("identifiers", _("Identifiers")), ("events", _("Known events")),
                           ("new_evidence", _("New evidence")), ("open_actions", _("Open actions"))):
            tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            tile.add_css_class("card")
            tile.add_css_class("stat-tile")
            value = Gtk.Label(label="0")
            value.add_css_class("stat-value")
            caption = Gtk.Label(label=label)
            caption.add_css_class("dim-label")
            tile.append(value)
            tile.append(caption)
            flow.append(tile)
            self._tiles[key] = value
        body.append(flow)
        title = Gtk.Label(label=_("Latest checks"), xalign=0)
        title.add_css_class("heading")
        body.append(title)
        self._checks = boxed_list()
        body.append(self._checks)
        note = Gtk.Label(wrap=True, xalign=0, label=_(
            "Results only cover what each source knows on the date of the check. "
            "An event in the list does not mean an account is compromised today, and "
            "an empty list does not guarantee that nothing has leaked."))
        note.add_css_class("dim-label")
        note.add_css_class("caption")
        body.append(note)

    def refresh(self, profile: Profile) -> None:
        stats = profile.stats()
        for key, label in self._tiles.items():
            label.set_label(str(getattr(stats, key)))
        self._checks.remove_all()
        checks = profile.last_checks()
        for check in checks:
            result = describe_check(check.status, check.error_code, check.found,
                                    check.completed_at)
            source = self._source_names.get(check.provider_id)
            self._checks.append(action_row(check.identifier_value,
                                           f"{source}: {result}" if source else result))
        if not checks:
            self._checks.append(action_row(_("No identifiers yet"),
                                           _("Add an email, nickname or name in the "
                                             "Identifiers tab.")))


class IdentifiersPage(_Page):
    def __init__(self, on_changed: Callable[[], None], notify: Callable[[str], None],
                 confirm_remove: Callable[[str, Callable[[], None]], None]):
        super().__init__("mail-unread-symbolic", "", "")
        self._on_changed, self._notify, self._confirm_remove = on_changed, notify, confirm_remove
        self._profile: Profile | None = None
        self._loading = False
        add_box = boxed_list()
        self._entry = Adw.EntryRow(title=_("Add email, nickname or name"), show_apply_button=True)
        self._entry.connect("apply", self._on_add)
        self._entry.connect("entry-activated", self._on_add)
        add_box.append(self._entry)
        self.content.append(add_box)
        self._list = boxed_list()
        self.content.append(self._list)
        self.show_empty(False)

    def refresh(self, profile: Profile) -> None:
        self._profile = profile
        self._loading = True
        self._list.remove_all()
        identifiers = profile.identifiers()
        self._list.set_visible(bool(identifiers))
        for identifier in identifiers:
            row = action_row(identifier.value, identifier.label
                             or describe_identifier_type(identifier.type))
            switch = Gtk.Switch(active=identifier.enabled, valign=Gtk.Align.CENTER,
                                tooltip_text=_("Include in scans"))
            switch.update_property([Gtk.AccessibleProperty.LABEL],
                                   [_("Include {value} in scans").format(value=identifier.value)])
            switch.connect("notify::active", self._on_toggled, identifier.id)
            remove = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                tooltip_text=_("Remove"))
            remove.add_css_class("flat")
            remove.update_property([Gtk.AccessibleProperty.LABEL],
                                   [_("Remove {value}").format(value=identifier.value)])
            remove.connect("clicked", self._on_remove, identifier)
            row.add_suffix(switch)
            row.add_suffix(remove)
            self._list.append(row)
        self._loading = False

    def _on_add(self, entry):
        value = entry.get_text()
        if not value.strip() or self._profile is None:
            return
        try:
            self._profile.add_identifier(value)
        except DuplicateIdentifierError:
            self._notify(_("This identifier is already in the profile."))
        except ValueError as exc:
            self._notify(str(exc))
        except OSError:
            self._notify(_("The profile could not be saved."))
        else:
            entry.set_text("")
            self._on_changed()

    def _on_toggled(self, switch, _pspec, identifier_id):
        if not self._loading and self._profile is not None:
            self._profile.set_identifier_enabled(identifier_id, switch.get_active())

    def _on_remove(self, _button, identifier):
        def remove():
            self._profile.remove_identifier(identifier.id)
            self._on_changed()

        self._confirm_remove(identifier.value, remove)


class ExposuresPage(_Page):
    def __init__(self, on_open: Callable[[int], None]):
        super().__init__("security-high-symbolic", _("No known exposures"),
                         _("Run a scan to see what your sources know about your identifiers."))
        self._on_open = on_open
        self._profile: Profile | None = None
        self._identifier_ids: list[int | None] = [None]
        self._loading = False
        filters = Gtk.Box(spacing=12)
        self._search = Gtk.SearchEntry(hexpand=True, placeholder_text=_("Search events"))
        self._search.connect("search-changed", lambda *_a: self._populate())
        self._filter = Gtk.DropDown.new_from_strings([_("All identifiers")])
        self._filter.update_property([Gtk.AccessibleProperty.LABEL], [_("Filter by identifier")])
        self._filter.connect("notify::selected", lambda *_a: self._populate())
        filters.append(self._search)
        filters.append(self._filter)
        self.content.append(filters)
        self._list = boxed_list()
        self.content.append(self._list)
        self._no_match = Adw.StatusPage(icon_name="edit-find-symbolic",
                                        title=_("No matching events"))
        self.content.append(self._no_match)

    def refresh(self, profile: Profile) -> None:
        self._profile = profile
        self._loading = True
        selected_id = self._identifier_ids[self._filter.get_selected()]
        identifiers = profile.identifiers()
        self._identifier_ids = [None] + [item.id for item in identifiers]
        self._filter.set_model(Gtk.StringList.new(
            [_("All identifiers")] + [item.value for item in identifiers]))
        self._filter.set_selected(self._identifier_ids.index(selected_id)
                                  if selected_id in self._identifier_ids else 0)
        self._loading = False
        self.show_empty(not profile.exposures())
        self._populate()

    def _populate(self):
        if self._loading or self._profile is None:
            return
        self._list.remove_all()
        identifier_id = self._identifier_ids[self._filter.get_selected()]
        exposures = self._profile.exposures(identifier_id, self._search.get_text().strip())
        self._list.set_visible(bool(exposures))
        self._no_match.set_visible(not exposures)
        for exposure in exposures:
            detail = {EventKind.WEB_MENTION: _("Public web page"),
                      EventKind.PROFILE_PAGE: _("Page with this name")}.get(
                exposure.kind, exposure.event_date or _("Date unknown"))
            row = action_row(exposure.title, f"{exposure.identifier_value} · {detail}",
                             activatable=True)
            if exposure.is_new:
                badge = Gtk.Label(label=_("New"), valign=Gtk.Align.CENTER)
                badge.add_css_class("accent")
                badge.add_css_class("caption-heading")
                row.add_suffix(badge)
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", self._on_row_activated, exposure.id)
            self._list.append(row)

    def _on_row_activated(self, _row, exposure_id):
        self._on_open(exposure_id)


class ActionsPage(_Page):
    def __init__(self, on_status: Callable[[int, ActionStatus], None]):
        super().__init__("emblem-ok-symbolic", _("No actions to follow"),
                         _("Suggested steps appear here when a scan finds an exposure."))
        self._on_status = on_status
        self._profile: Profile | None = None
        self._show_closed = Gtk.CheckButton(label=_("Show completed and dismissed"))
        self._show_closed.connect("toggled", lambda *_a: self.refresh(self._profile))
        self.content.append(self._show_closed)
        self._list = boxed_list()
        self.content.append(self._list)

    def refresh(self, profile: Profile) -> None:
        self._profile = profile
        self.show_empty(not profile.actions())
        statuses = None if self._show_closed.get_active() else (
            ActionStatus.OPEN, ActionStatus.IN_PROGRESS)
        self._list.remove_all()
        actions = profile.actions(statuses=statuses)
        self._list.set_visible(bool(actions))
        for action in actions:
            row = action_row(describe_action(action.type),
                             f"{action.breach_title} · {action.identifier_value}")
            add_status_selector(row, action, self._on_status)
            self._list.append(row)


class _Track:
    """One source's independent progress and log."""

    def __init__(self, parent: Gtk.Box, provider: ExposureProvider):
        title = Gtk.Label(label=provider.info.name, xalign=0, hexpand=True)
        title.add_css_class("heading")
        self.spinner = Gtk.Spinner()
        self.status = Gtk.Label(xalign=1)
        self.status.add_css_class("dim-label")
        header = Gtk.Box(spacing=8)
        header.append(title)
        header.append(self.spinner)
        header.append(self.status)
        parent.append(header)
        self.lines = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.lines.add_css_class("card")
        self.lines.add_css_class("log-card")
        parent.append(self.lines)
        self.set_status(_("Not started"), False)

    def set_status(self, text: str, running: bool) -> None:
        self.status.set_label(text)
        self.spinner.set_spinning(running)

    def clear(self) -> None:
        while child := self.lines.get_first_child():
            self.lines.remove(child)

    def prepend(self, entry: LogEntry) -> None:
        """Newest first, so the current step is visible without scrolling."""
        line = Gtk.Label(label=f"{format_time(entry.at)}  {entry.message}", xalign=0, wrap=True,
                         wrap_mode=Pango.WrapMode.WORD_CHAR, use_markup=False)
        line.add_css_class("log-line")
        if entry.level in ("warning", "error"):
            line.add_css_class(entry.level)
        self.lines.prepend(line)
        self.lines.set_visible(True)


class ActivityPage(Gtk.Box):
    """Shows, source by source, what each search did and what it sent."""

    def __init__(self, providers: list[ExposureProvider], on_clear: Callable[[], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.append(clamped(body))
        intro = Gtk.Box(spacing=12)
        note = Gtk.Label(wrap=True, xalign=0, hexpand=True, label=_(
            "Each source runs on its own. This log stays inside your encrypted profile."))
        note.add_css_class("dim-label")
        note.add_css_class("caption")
        clear = Gtk.Button(label=_("Clear Log"), valign=Gtk.Align.CENTER)
        clear.connect("clicked", lambda *_a: on_clear())
        intro.append(note)
        intro.append(clear)
        body.append(intro)
        self.tracks = {provider.info.id: _Track(body, provider) for provider in providers}

    def refresh(self, profile: Profile) -> None:
        for provider_id, track in self.tracks.items():
            track.clear()
            entries = profile.log_entries(provider_id)
            for entry in entries:
                track.prepend(entry)
            track.lines.set_visible(bool(entries))
            track.set_status(_("Not started"), False)

    def add_entry(self, entry: LogEntry) -> None:
        track = self.tracks.get(entry.provider_id)
        if track is not None:
            track.prepend(entry)

    def set_status(self, provider_id: str, text: str, running: bool) -> None:
        track = self.tracks.get(provider_id)
        if track is not None:
            track.set_status(text, running)
