"""Dialogs: profile password entry, event details and preferences."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..core.crypto import MIN_PASSWORD_LENGTH  # noqa: E402
from ..core.models import ActionStatus, EventKind, Exposure, Verification, describe_action  # noqa: E402
from ..core.profile import Profile  # noqa: E402
from ..i18n import _  # noqa: E402
from ..providers.base import ExposureProvider  # noqa: E402
from .. import secret_store  # noqa: E402
from .common import (  # noqa: E402
    action_row,
    add_status_selector,
    clamped,
    format_datetime,
    run_async,
)


def password_problem(password: str, confirmation: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return _("Use at least {count} characters.").format(count=MIN_PASSWORD_LENGTH)
    if password != confirmation:
        return _("The passwords do not match.")
    return None


class _FormDialog(Adw.Dialog):
    """A small dialog with one list of rows and one main button."""

    def __init__(self, title: str, button_label: str):
        super().__init__(title=title, content_width=420)
        header = Adw.HeaderBar()
        self.button = Gtk.Button(label=button_label)
        self.button.add_css_class("suggested-action")
        self.button.connect("clicked", lambda *_a: self.submit())
        header.pack_end(self.button)
        self.rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.rows.add_css_class("boxed-list")
        self.message = Gtk.Label(wrap=True, xalign=0, visible=False)
        self.message.add_css_class("error")
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12,
                       margin_bottom=18, margin_start=18, margin_end=18)
        body.append(self.rows)
        body.append(self.message)
        view = Adw.ToolbarView(content=body)
        view.add_top_bar(header)
        self.set_child(view)

    def submit(self) -> None:
        raise NotImplementedError

    def show_message(self, text: str | None) -> None:
        self.message.set_label(text or "")
        self.message.set_visible(bool(text))

    def set_busy(self, busy: bool) -> None:
        self.button.set_sensitive(not busy)


class CreateProfileDialog(_FormDialog):
    def __init__(self, on_submit: Callable[[str, str], None]):
        super().__init__(_("New Profile"), _("Choose Location…"))
        self._on_submit = on_submit
        self.name = Adw.EntryRow(title=_("Name"), text=_("Personal"))
        self.password = Adw.PasswordEntryRow(title=_("Password"))
        self.confirmation = Adw.PasswordEntryRow(title=_("Repeat password"))
        self.confirmation.connect("entry-activated", lambda *_a: self.submit())
        for row in (self.name, self.password, self.confirmation):
            self.rows.append(row)
        hint = Gtk.Label(wrap=True, xalign=0, label=_(
            "The password encrypts the whole profile. It cannot be recovered if you lose it."))
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        self.rows.get_parent().append(hint)

    def submit(self) -> None:
        problem = password_problem(self.password.get_text(), self.confirmation.get_text())
        if not self.name.get_text().strip():
            problem = _("Give the profile a name.")
        self.show_message(problem)
        if not problem:
            self._on_submit(self.name.get_text().strip(), self.password.get_text())


class UnlockDialog(_FormDialog):
    def __init__(self, filename: str, on_submit: Callable[[str], None]):
        super().__init__(_("Unlock {name}").format(name=filename), _("Unlock"))
        self._on_submit = on_submit
        self.password = Adw.PasswordEntryRow(title=_("Password"))
        self.password.connect("entry-activated", lambda *_a: self.submit())
        self.rows.append(self.password)
        self.set_focus(self.password)

    def submit(self) -> None:
        if self.password.get_text():
            self._on_submit(self.password.get_text())


_VERIFICATION = {
    Verification.VERIFIED: _("Verified by the source"),
    Verification.UNVERIFIED: _("Not verified by the source"),
    Verification.FABRICATED: _("Reported by the source as possibly fabricated"),
}


class ExposureDialog(Adw.Dialog):
    def __init__(self, profile: Profile, exposure: Exposure, attribution: str,
                 on_status: Callable[[int, ActionStatus], None]):
        super().__init__(title=exposure.title, content_width=560, content_height=640)
        page = Adw.PreferencesPage()
        is_web = exposure.kind != EventKind.BREACH
        if exposure.description:
            about = Adw.PreferencesGroup(title=_("What the page says") if is_web
                                         else _("What happened"))
            text = Gtk.Label(label=exposure.description, wrap=True, xalign=0)
            about.add(text)
            page.add(about)

        facts = Adw.PreferencesGroup(title=_("Details"))
        rows = [
            (_("Service"), exposure.domain or exposure.title),
            *(() if is_web else (
                (_("Date of the event"), exposure.event_date or _("Unknown")),
                (_("Data involved"), ", ".join(exposure.data_classes) or _("Not specified")),
            )),
            (_("Identifiers involved"), ", ".join(profile.identifiers_for_breach(exposure.breach_id))),
            (_("Source"), attribution),
            (_("Reliability"), {
                EventKind.WEB_MENTION: _("A search result. GLeaks has not checked this page."),
                EventKind.PROFILE_PAGE: _("A page with this name exists. It may belong to "
                                          "someone else."),
            }.get(exposure.kind, _VERIFICATION[exposure.verification])),
            (_("First found"), format_datetime(exposure.first_seen_at)),
            (_("Last confirmed"), format_datetime(exposure.last_seen_at)),
        ]
        for title, value in rows:
            row = action_row(title, value)
            row.add_css_class("property")
            facts.add(row)
        if exposure.source_url:
            link = action_row(_("Open page") if is_web else _("Disclosure notice"),
                              exposure.source_url, activatable=True)
            link.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
            link.connect("activated", self._open_link, exposure.source_url)
            facts.add(link)
        page.add(facts)

        steps = Adw.PreferencesGroup(
            title=_("Suggested actions"),
            description=_("This stays in your record even after you complete these steps."))
        for action in exposure.actions:
            row = action_row(describe_action(action.type))
            add_status_selector(row, action, on_status)
            steps.add(row)
        page.add(steps)

        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)

    def _open_link(self, _row, url):
        Gtk.UriLauncher.new(url).launch(self.get_root(), None, None, None)


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, profile: Profile, providers: list[ExposureProvider],
                 notify: Callable[[str], None]):
        super().__init__(title=_("Preferences"))
        self._profile, self._notify = profile, notify
        for category, title, icon in (
            ("gleaks", _("GLeaks Tools"), "system-search-symbolic"),
            ("third-party", _("Third-Party Services"), "network-server-symbolic"),
        ):
            members = [p for p in providers if p.info.category == category]
            if members:
                page = Adw.PreferencesPage(title=title, icon_name=icon)
                if category == "gleaks":
                    page.add(self._slow_search_group())
                for provider in members:
                    page.add(self._provider_group(provider))
                self.add(page)
        self.add(self._security_page())

    def _guard_save(self, operation):
        try:
            operation()
        except OSError:
            self._notify(_("The profile could not be saved."))

    # -- slow searches -------------------------------------------------------
    def _slow_search_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title=_("Slow searches"),
            description=_("GLeaks tools make one request at a time, spread out over time, so "
                          "that no site gets flooded. A search can take a while, and it "
                          "resumes where it stopped."))
        paces = [(30, _("Gentle: one request every 30 seconds")),
                 (120, _("Slow: one request every 2 minutes")),
                 (600, _("Very slow: one request every 10 minutes"))]
        repeats = [(0, _("Off")), (1, _("Every day")), (7, _("Every week")), (30, _("Every month"))]
        pace_row = self._choice_row(_("Pace"), paces, self._profile.pace(), self._profile.set_pace)
        repeat_row = self._choice_row(_("Repeat automatically"), repeats,
                                      self._profile.repeat_days(), self._profile.set_repeat_days)
        repeat_row.set_subtitle(_("While on, GLeaks searches your enabled identifiers with its "
                                  "own tools without asking each time. It runs only while "
                                  "GLeaks is open or in the background."))
        background = Adw.SwitchRow(title=_("Keep new searches going after the window closes"),
                                   active=self._profile.background_by_default())
        background.connect("notify::active", lambda row, _p: self._guard_save(
            lambda: self._profile.set_background_by_default(row.get_active())))
        for row in (pace_row, repeat_row, background):
            group.add(row)
        return group

    def _choice_row(self, title, choices, current, apply) -> Adw.ComboRow:
        values = [value for value, _label in choices]
        row = Adw.ComboRow(title=title, model=Gtk.StringList.new([label for _v, label in choices]))
        if current in values:
            row.set_selected(values.index(current))

        def changed(combo, _pspec):
            self._guard_save(lambda: apply(values[combo.get_selected()]))

        row.connect("notify::selected", changed)
        return row

    # -- sources -------------------------------------------------------------
    def _provider_group(self, provider: ExposureProvider) -> Adw.PreferencesGroup:
        info = provider.info
        group = Adw.PreferencesGroup(title=info.name, description=info.costs)
        enabled = Adw.SwitchRow(title=_("Use this source"),
                                active=self._profile.provider_enabled(info.id))
        enabled.connect("notify::active", self._on_enabled, info)
        group.add(enabled)
        if info.requires_api_key:
            self._add_key_rows(group, info)
        modes = list(info.modes)
        current = info.mode(self._profile.provider_mode(info.id, modes[0].id))
        sent = action_row(_("Sent"), current.transmits)
        requires = action_row(_("Requires"), current.requirement)
        if len(modes) > 1:
            combo = Adw.ComboRow(title=_("Search method"),
                                 model=Gtk.StringList.new([mode.label for mode in modes]))
            combo.set_selected(modes.index(current))
            combo.connect("notify::selected", self._on_mode_changed, info, modes, sent, requires)
            group.add(combo)
        group.add(sent)
        group.add(requires)
        for title, value in ((_("Sent to"), info.destination), (_("Returned"), info.returns),
                             (_("Request limits"), info.rate_limits)):
            group.add(action_row(title, value))
        if info.destinations:
            sites = Adw.ExpanderRow(title=_("All sites ({count})").format(
                count=len(info.destinations)))
            for destination in info.destinations:
                sites.add_row(action_row(destination))
            group.add(sites)
        return group

    def _on_enabled(self, row, _pspec, info):
        self._guard_save(lambda: self._profile.set_provider_enabled(
            info.id, row.get_active(), info.modes[0].id))

    def _on_mode_changed(self, combo, _pspec, info, modes, sent, requires):
        mode = modes[combo.get_selected()]
        sent.set_subtitle(mode.transmits)
        requires.set_subtitle(mode.requirement)
        self._guard_save(lambda: self._profile.set_provider_mode(info.id, mode.id))

    def _add_key_rows(self, group, info):
        entry = Adw.PasswordEntryRow(title=_("API key (optional)"), show_apply_button=True)
        status = action_row(_("Stored key"), _("Checking the keyring…"))
        remove = Gtk.Button(label=_("Remove"), valign=Gtk.Align.CENTER, sensitive=False)
        status.add_suffix(remove)
        link = action_row(_("Get an API key"), info.api_key_url, activatable=True)
        link.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
        link.connect("activated", self._open_url, info.api_key_url)
        for row in (entry, status, link):
            group.add(row)

        def refresh(*_unused):
            def done(key):
                status.set_subtitle(_("A key is stored in the keyring") if key else
                                    _("No key stored. This source is skipped."))
                remove.set_sensitive(bool(key))

            def failed(_exc):
                status.set_subtitle(_("The desktop keyring is not available"))

            run_async(lambda: secret_store.get_api_key(info.id), done, failed)

        def apply_key(row):
            key = row.get_text().strip()
            if key:
                row.set_text("")
                run_async(lambda: secret_store.set_api_key(info.id, key), refresh,
                          lambda _exc: self._notify(_("The key could not be saved to the keyring.")))

        def remove_key(_button):
            run_async(lambda: secret_store.delete_api_key(info.id), refresh,
                      lambda _exc: self._notify(_("The key could not be removed from the keyring.")))

        entry.connect("apply", apply_key)
        remove.connect("clicked", remove_key)
        refresh()

    def _open_url(self, _row, url):
        Gtk.UriLauncher.new(url).launch(self.get_root(), None, None, None)

    # -- profile -------------------------------------------------------------
    def _security_page(self) -> Adw.PreferencesPage:
        security = Adw.PreferencesPage(title=_("Profile"), icon_name="dialog-password-symbolic")
        group = Adw.PreferencesGroup(
            title=_("Change password"),
            description=_("API keys stay in this computer's keyring and do not travel "
                          "with the profile file."))
        self._new_password = Adw.PasswordEntryRow(title=_("New password"))
        self._repeat_password = Adw.PasswordEntryRow(title=_("Repeat new password"))
        apply_row = action_row(_("Apply"), "")
        button = Gtk.Button(label=_("Change Password"), valign=Gtk.Align.CENTER)
        button.connect("clicked", self._on_change_password)
        apply_row.add_suffix(button)
        for row in (self._new_password, self._repeat_password, apply_row):
            group.add(row)
        security.add(group)
        return security

    def _on_change_password(self, button):
        password = self._new_password.get_text()
        problem = password_problem(password, self._repeat_password.get_text())
        if problem:
            self._notify(problem)
            return
        button.set_sensitive(False)

        def done(prepared):
            button.set_sensitive(True)
            try:
                self._profile.apply_password(prepared)
            except OSError:
                failed(None)
                return
            self._new_password.set_text("")
            self._repeat_password.set_text("")
            self._notify(_("Password changed."))

        def failed(_exc):
            button.set_sensitive(True)
            self._notify(_("The password could not be changed."))

        run_async(lambda: self._profile.prepare_password(password), done, failed)
