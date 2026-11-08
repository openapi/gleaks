"""Dialogs: profile password entry, event details and preferences."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..core.crypto import MIN_PASSWORD_LENGTH  # noqa: E402
from ..core.models import ActionStatus, Exposure, Verification, describe_action  # noqa: E402
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
        if exposure.description:
            about = Adw.PreferencesGroup(title=_("What happened"))
            text = Gtk.Label(label=exposure.description, wrap=True, xalign=0)
            about.add(text)
            page.add(about)

        facts = Adw.PreferencesGroup(title=_("Details"))
        rows = [
            (_("Service"), exposure.domain or exposure.title),
            (_("Date of the event"), exposure.event_date or _("Unknown")),
            (_("Data involved"), ", ".join(exposure.data_classes) or _("Not specified")),
            (_("Identifiers involved"), ", ".join(profile.identifiers_for_breach(exposure.breach_id))),
            (_("Source"), attribution),
            (_("Reliability"), _VERIFICATION[exposure.verification]),
            (_("First found"), format_datetime(exposure.first_seen_at)),
            (_("Last confirmed"), format_datetime(exposure.last_seen_at)),
        ]
        for title, value in rows:
            row = action_row(title, value)
            row.add_css_class("property")
            facts.add(row)
        if exposure.source_url:
            link = action_row(_("Disclosure notice"), exposure.source_url, activatable=True)
            link.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
            link.connect("activated", self._open_link, exposure.source_url)
            facts.add(link)
        page.add(facts)

        steps = Adw.PreferencesGroup(
            title=_("Suggested actions"),
            description=_("This event is a historical fact. It stays in your record "
                          "even after you complete these steps."))
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
    def __init__(self, profile: Profile, provider: ExposureProvider,
                 notify: Callable[[str], None]):
        super().__init__(title=_("Preferences"))
        self._profile, self._provider, self._notify = profile, provider, notify
        info = provider.info
        page = Adw.PreferencesPage(title=_("Sources"), icon_name="network-server-symbolic")

        source = Adw.PreferencesGroup(title=info.name, description=info.costs)
        self._key_row = Adw.PasswordEntryRow(title=_("API key"), show_apply_button=True)
        self._key_row.connect("apply", self._on_key_apply)
        source.add(self._key_row)
        self._key_status = action_row(_("Stored key"), _("Checking the keyring…"))
        self._remove_key = Gtk.Button(label=_("Remove"), valign=Gtk.Align.CENTER, sensitive=False)
        self._remove_key.connect("clicked", self._on_key_remove)
        self._key_status.add_suffix(self._remove_key)
        source.add(self._key_status)
        get_key = action_row(_("Get an API key"), info.api_key_url, activatable=True)
        get_key.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
        get_key.connect("activated", self._open_url, info.api_key_url)
        source.add(get_key)

        self._modes = list(info.modes)
        self._mode_row = Adw.ComboRow(
            title=_("Search method"),
            model=Gtk.StringList.new([mode.label for mode in self._modes]))
        current = info.mode(profile.provider_mode(info.id, info.modes[0].id))
        self._mode_row.set_selected(self._modes.index(current))
        self._mode_row.connect("notify::selected", self._on_mode_changed)
        source.add(self._mode_row)
        page.add(source)

        disclosure = Adw.PreferencesGroup(title=_("What this source receives"))
        self._sent_row = action_row(_("Sent"), "")
        disclosure.add(self._sent_row)
        self._plan_row = action_row(_("Requires"), "")
        disclosure.add(self._plan_row)
        for title, value in ((_("Sent to"), info.destination), (_("Returned"), info.returns),
                             (_("Request limits"), info.rate_limits)):
            disclosure.add(action_row(title, value))
        page.add(disclosure)
        self._update_disclosure()
        self.add(page)

        security = Adw.PreferencesPage(title=_("Profile"), icon_name="dialog-password-symbolic")
        group = Adw.PreferencesGroup(
            title=_("Change password"),
            description=_("API keys stay in this computer's keyring and do not travel "
                          "with the profile file."))
        self._new_password = Adw.PasswordEntryRow(title=_("New password"))
        self._repeat_password = Adw.PasswordEntryRow(title=_("Repeat new password"))
        apply_row = action_row(_("Apply"), "")
        self._apply_password = Gtk.Button(label=_("Change Password"), valign=Gtk.Align.CENTER)
        self._apply_password.connect("clicked", self._on_change_password)
        apply_row.add_suffix(self._apply_password)
        for row in (self._new_password, self._repeat_password, apply_row):
            group.add(row)
        security.add(group)
        self.add(security)
        self._refresh_key_status()

    def _update_disclosure(self):
        mode = self._modes[self._mode_row.get_selected()]
        self._sent_row.set_subtitle(mode.transmits)
        self._plan_row.set_subtitle(mode.requirement)

    def _on_mode_changed(self, *_args):
        mode = self._modes[self._mode_row.get_selected()]
        self._update_disclosure()
        self._guard_save(lambda: self._profile.set_provider_mode(self._provider.info.id, mode.id))

    def _guard_save(self, operation):
        try:
            operation()
        except OSError:
            self._notify(_("The profile could not be saved."))

    def _refresh_key_status(self):
        def done(key):
            self._key_status.set_subtitle(
                _("A key is stored in the keyring") if key else _("No key stored"))
            self._remove_key.set_sensitive(bool(key))

        def failed(_exc):
            self._key_status.set_subtitle(_("The desktop keyring is not available"))

        run_async(lambda: secret_store.get_api_key(self._provider.info.id), done, failed)

    def _on_key_apply(self, row):
        key = row.get_text().strip()
        if not key:
            return
        row.set_text("")

        def failed(_exc):
            self._notify(_("The key could not be saved to the keyring."))

        run_async(lambda: secret_store.set_api_key(self._provider.info.id, key),
                  lambda _r: self._refresh_key_status(), failed)

    def _on_key_remove(self, _button):
        def failed(_exc):
            self._notify(_("The key could not be removed from the keyring."))

        run_async(lambda: secret_store.delete_api_key(self._provider.info.id),
                  lambda _r: self._refresh_key_status(), failed)

    def _open_url(self, _row, url):
        Gtk.UriLauncher.new(url).launch(self.get_root(), None, None, None)

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
