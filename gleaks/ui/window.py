"""The main window: welcome screen, open profile, and the scan flow."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .. import APP_ID, APP_NAME, config, secret_store  # noqa: E402
from ..core.crypto import ContainerError, WrongPasswordError  # noqa: E402
from ..core.migrations import NewerSchemaError  # noqa: E402
from ..core.models import ActionStatus, ScanStatus, describe_error  # noqa: E402
from ..core.profile import DamagedProfileError, Profile  # noqa: E402
from ..core.scanning import ScanOutcome, ScanRequest, run_scan  # noqa: E402
from ..i18n import _, ngettext  # noqa: E402
from ..providers import PROVIDERS  # noqa: E402
from ..providers.base import CheckContext, ExposureProvider  # noqa: E402
from .common import action_row, boxed_list, clamped, run_async  # noqa: E402
from .dialogs import CreateProfileDialog, ExposureDialog, PreferencesDialog, UnlockDialog  # noqa: E402
from .pages import ActionsPage, ActivityPage, DashboardPage, ExposuresPage, IdentifiersPage  # noqa: E402

log = logging.getLogger(__name__)
_SAVE_FAILED = _("The profile could not be saved. Your latest changes are not on disk yet.")


class _ScanRun:
    def __init__(self, total: int, sources: int):
        self.cancel = threading.Event()
        self.total = total
        self.sources_left = sources
        self.source_errors: dict[str, int] = {}
        self.done = 0
        self.new = 0
        self.errors: list[str] = []
        self.cancelled = False


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(default_width=880, default_height=680, title=APP_NAME, **kwargs)
        self.set_size_request(360, 400)
        self.profile: Profile | None = None
        self._scan: _ScanRun | None = None
        self.providers = list(PROVIDERS.values())
        self.toasts = Adw.ToastOverlay()
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.toasts.set_child(self.stack)
        self.set_content(self.toasts)
        self.stack.add_named(self._build_welcome(), "welcome")
        self.stack.add_named(self._build_profile_view(), "profile")
        self._refresh_recent()
        self.connect("close-request", self._on_close_request)

    # -- construction --------------------------------------------------------
    def _menu_button(self, with_profile: bool) -> Gtk.MenuButton:
        menu = Gio.Menu()
        if with_profile:
            menu.append(_("Preferences"), "app.preferences")
            menu.append(_("Close Profile"), "app.close-profile")
        else:
            menu.append(_("New Profile…"), "app.new-profile")
            menu.append(_("Open Profile…"), "app.open-profile")
        menu.append(_("About GLeaks"), "app.about")
        button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                primary=True, tooltip_text=_("Main Menu"))
        return button

    def _build_welcome(self) -> Gtk.Widget:
        header = Adw.HeaderBar()
        header.pack_end(self._menu_button(False))
        status = Adw.StatusPage(icon_name=APP_ID, title=APP_NAME,
                                description=_("Know where your data has leaked."))
        buttons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          halign=Gtk.Align.CENTER)
        create = Gtk.Button(label=_("Create Profile"), action_name="app.new-profile")
        create.add_css_class("pill")
        create.add_css_class("suggested-action")
        open_button = Gtk.Button(label=_("Open Profile"), action_name="app.open-profile")
        open_button.add_css_class("pill")
        buttons.append(create)
        buttons.append(open_button)
        self._recent_title = Gtk.Label(label=_("Recent profiles"), xalign=0, margin_top=18)
        self._recent_title.add_css_class("heading")
        self._recent_list = boxed_list()
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        wrapper.append(buttons)
        wrapper.append(self._recent_title)
        wrapper.append(self._recent_list)
        status.set_child(Adw.Clamp(child=wrapper, maximum_size=480))
        view = Adw.ToolbarView(content=status)
        view.add_top_bar(header)
        return view

    def _build_profile_view(self) -> Gtk.Widget:
        self.views = Adw.ViewStack(vexpand=True)
        self.dashboard = DashboardPage({p.info.id: p.info.name for p in self.providers})
        self.identifiers = IdentifiersPage(self._refresh_pages, self.show_toast,
                                           self._confirm_remove)
        self.exposures = ExposuresPage(self._open_exposure)
        self.actions_page = ActionsPage(self._set_action_status)
        self.activity = ActivityPage(self.providers, self._clear_log)
        for page, name, title, icon in (
            (self.dashboard, "dashboard", _("Overview"), "view-grid-symbolic"),
            (self.identifiers, "identifiers", _("Identifiers"), "mail-unread-symbolic"),
            (self.exposures, "exposures", _("Exposures"), "dialog-warning-symbolic"),
            (self.actions_page, "actions", _("Actions"), "emblem-ok-symbolic"),
            (self.activity, "activity", _("Activity"), "utilities-terminal-symbolic"),
        ):
            self.views.add_titled_with_icon(page, name, title, icon)

        self.title_widget = Adw.WindowTitle(title=APP_NAME)
        switcher = Adw.ViewSwitcher(stack=self.views, policy=Adw.ViewSwitcherPolicy.WIDE)
        self.header = Adw.HeaderBar(title_widget=switcher)
        self.scan_button = Gtk.Button(label=_("Scan"), action_name="app.scan",
                                      tooltip_text=_("Check your identifiers"))
        self.scan_button.add_css_class("suggested-action")
        self.header.pack_start(self.scan_button)
        self.header.pack_end(self._menu_button(True))
        self.banner = Adw.Banner(button_label=_("Cancel"), use_markup=False)
        self.banner.connect("button-clicked", lambda *_a: self.cancel_scan())
        bottom = Adw.ViewSwitcherBar(stack=self.views)

        view = Adw.ToolbarView(content=self.views)
        view.add_top_bar(self.header)
        view.add_top_bar(self.banner)
        view.add_bottom_bar(bottom)

        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 620sp"))
        narrow.add_setter(bottom, "reveal", True)
        narrow.add_setter(self.header, "title-widget", self.title_widget)
        self.add_breakpoint(narrow)
        return view

    # -- feedback ------------------------------------------------------------
    def show_toast(self, text: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=text, use_markup=False, timeout=5))

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", _("Close"))
        dialog.present(self)

    def _refresh_recent(self) -> None:
        self._recent_list.remove_all()
        recent = config.recent_profiles()
        self._recent_title.set_visible(bool(recent))
        self._recent_list.set_visible(bool(recent))
        for path in recent:
            row = action_row(Path(path).name, str(Path(path).parent), activatable=True)
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", self._on_recent_activated, path)
            self._recent_list.append(row)

    def _on_recent_activated(self, _row, path):
        self.request_open(path)

    # -- opening and creating profiles --------------------------------------
    @staticmethod
    def _file_filters() -> Gio.ListStore:
        file_filter = Gtk.FileFilter(name=_("GLeaks profiles"))
        file_filter.add_suffix("gleaks")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(file_filter)
        return filters

    def choose_profile(self) -> None:
        dialog = Gtk.FileDialog(title=_("Open Profile"), filters=self._file_filters())
        dialog.open(self, None, self._on_open_chosen)

    def _on_open_chosen(self, dialog, result):
        try:
            chosen = dialog.open_finish(result)
        except GLib.Error:
            return  # Dismissed.
        if chosen and chosen.get_path():
            self.request_open(chosen.get_path())

    def request_open(self, path: str) -> None:
        def submit(password):
            unlock.set_busy(True)
            unlock.show_message(None)
            run_async(lambda: Profile.open(path, password), done, failed)

        def done(profile):
            unlock.close()
            self._show_profile(profile)

        def failed(exc):
            unlock.set_busy(False)
            unlock.show_message(self._open_error(exc))

        unlock = UnlockDialog(Path(path).name, submit)
        unlock.present(self)

    @staticmethod
    def _open_error(exc: Exception) -> str:
        if isinstance(exc, WrongPasswordError):
            return _("Wrong password, or the file is damaged.")
        if isinstance(exc, ContainerError):
            return _("This file is not a GLeaks profile this version can read.")
        if isinstance(exc, NewerSchemaError):
            return _("This profile was saved by a newer version of GLeaks.")
        if isinstance(exc, DamagedProfileError):
            return _("The profile is damaged and cannot be opened.")
        if isinstance(exc, OSError):
            return _("The file could not be read.")
        log.error("profile could not be opened: %s", type(exc).__name__)
        return _("The profile could not be opened.")

    def create_profile(self) -> None:
        form = None

        def submit(name, password):
            filename = "".join(c for c in name if c.isalnum() or c in " -_").strip() or "profile"
            chooser = Gtk.FileDialog(title=_("Save Profile"), initial_name=f"{filename}.gleaks",
                                     filters=self._file_filters())
            chooser.save(self, None, chosen, password, name)

        def chosen(chooser, result, password, name):
            try:
                target = chooser.save_finish(result)
            except GLib.Error:
                return  # Dismissed.
            path = target.get_path() if target else None
            if not path:
                form.show_message(_("This location cannot be used."))
                return
            form.set_busy(True)
            run_async(lambda: Profile.create(path, password, name), done, failed)

        def done(profile):
            form.close()
            self._show_profile(profile)

        def failed(_exc):
            form.set_busy(False)
            form.show_message(_("The profile could not be created at this location."))

        form = CreateProfileDialog(submit)
        form.present(self)

    def _show_profile(self, profile: Profile) -> None:
        if not self._release_profile():
            profile.close()
            return
        self.profile = profile
        config.remember_profile(str(profile.path))
        self.set_title(f"{profile.name} – {APP_NAME}")
        self.title_widget.set_title(profile.name)
        self.views.set_visible_child_name("dashboard")
        self._refresh_pages()
        self.activity.refresh(profile)
        self.stack.set_visible_child_name("profile")

    def _release_profile(self) -> bool:
        """Stop any scan and close the current profile; False if it cannot be saved."""
        self.cancel_scan()
        self._scan = None
        self.banner.set_revealed(False)
        self.scan_button.set_sensitive(True)
        if self.profile is None:
            return True
        try:
            self.profile.close()
        except OSError:
            self._show_error(_("Profile Not Saved"), _SAVE_FAILED)
            return False
        self.profile = None
        return True

    def close_profile(self) -> None:
        if self.profile is not None and self._release_profile():
            self.set_title(APP_NAME)
            self._refresh_recent()
            self.stack.set_visible_child_name("welcome")

    def _on_close_request(self, _window):
        return not self._release_profile()

    # -- refresh and edits ---------------------------------------------------
    def _refresh_pages(self) -> None:
        if self.profile is None:
            return
        for page in (self.dashboard, self.identifiers, self.exposures, self.actions_page):
            page.refresh(self.profile)

    def _confirm_remove(self, value: str, remove) -> None:
        dialog = Adw.AlertDialog(
            heading=_("Remove Identifier?"),
            body=_("{value} and the evidence linked to it will be deleted from this "
                   "profile.").format(value=value))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def responded(_dialog, response):
            if response == "remove":
                try:
                    remove()
                except OSError:
                    self.show_toast(_SAVE_FAILED)

        dialog.connect("response", responded)
        dialog.present(self)

    def _open_exposure(self, exposure_id: int) -> None:
        try:
            self.profile.mark_reviewed(exposure_id)
        except OSError:
            self.show_toast(_SAVE_FAILED)
        exposure = self.profile.exposure(exposure_id)
        source = next((p.info.attribution for p in self.providers
                       if p.info.id == exposure.source), exposure.source)
        dialog = ExposureDialog(self.profile, exposure, source, self._set_action_status)
        dialog.connect("closed", lambda *_a: self._refresh_pages())
        dialog.present(self)

    def _set_action_status(self, action_id: int, status: ActionStatus) -> None:
        def apply():
            if self.profile is None:
                return GLib.SOURCE_REMOVE
            try:
                self.profile.set_action_status(action_id, status)
            except OSError:
                self.show_toast(_SAVE_FAILED)
            self.dashboard.refresh(self.profile)
            self.actions_page.refresh(self.profile)
            return GLib.SOURCE_REMOVE

        # The selector that fired this may be rebuilt by the refresh: defer it.
        GLib.idle_add(apply)

    def show_preferences(self) -> None:
        if self.profile is not None:
            PreferencesDialog(self.profile, self.providers, self.show_toast).present(self)

    def _clear_log(self) -> None:
        if self.profile is None:
            return
        try:
            self.profile.clear_log()
        except OSError:
            self.show_toast(_SAVE_FAILED)
        self.activity.refresh(self.profile)

    # -- scanning ------------------------------------------------------------
    def start_scan(self) -> None:
        if self.profile is None or self._scan is not None:
            return
        identifiers = self.profile.identifiers(enabled_only=True)
        if not identifiers:
            self.show_toast(_("Add an email, nickname or name to scan first."))
            self.views.set_visible_child_name("identifiers")
            return
        requests = [ScanRequest(item.id, item.value, item.type) for item in identifiers]
        sources = [p for p in self.providers if self.profile.provider_enabled(p.info.id)
                   and self._requests_for(p, requests)]

        def keys_found(keys):
            plan = [(p, keys.get(p.info.id), self._requests_for(p, requests)) for p in sources
                    if keys.get(p.info.id) or not p.info.requires_api_key]
            skipped = [p for p in sources if p.info.requires_api_key and not keys.get(p.info.id)]
            if not plan:
                self.show_toast(_("No source can run. Turn on a source or add an API key."))
                self.show_preferences()
                return
            self._ask_consent(requests, plan, skipped)

        run_async(lambda: self._read_keys(sources), keys_found, lambda _exc: keys_found({}))

    @staticmethod
    def _requests_for(provider: ExposureProvider, requests: list[ScanRequest]) -> list[ScanRequest]:
        return [r for r in requests if r.kind in provider.info.supported_identifiers]

    @staticmethod
    def _read_keys(providers: list[ExposureProvider]) -> dict[str, str | None]:
        """Keys are optional: a source whose key cannot be read is skipped."""
        keys: dict[str, str | None] = {}
        for provider in providers:
            if provider.info.requires_api_key:
                try:
                    keys[provider.info.id] = secret_store.get_api_key(provider.info.id)
                except secret_store.SecretStoreError:
                    keys[provider.info.id] = None
        return keys

    def _mode_for(self, provider: ExposureProvider):
        info = provider.info
        return info.mode(self.profile.provider_mode(info.id, info.modes[0].id))

    def _ask_consent(self, requests: list[ScanRequest], plan: list, skipped: list) -> None:
        """Nothing leaves this computer before the user has seen exactly what will."""
        sections = [_("Only check identifiers that belong to you.\n\n{addresses}").format(
            addresses="\n".join(request.value for request in requests))]
        for provider, _key, _requests in plan:
            info = provider.info
            sections.append(
                _("{source} ({destination})\nSent: {sent}.\nReturned: {returned}\n"
                  "Limits: {limits}").format(
                    source=info.name, destination=info.destination,
                    sent=self._mode_for(provider).transmits, returned=info.returns,
                    limits=info.rate_limits))
        for provider in skipped:
            sections.append(_("{source}: skipped, no API key.").format(source=provider.info.name))
        dialog = Adw.AlertDialog(heading=_("Check These Identifiers?"),
                                 body="\n\n".join(sections))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("scan", _("Send and Check"))
        dialog.set_response_appearance("scan", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def responded(_dialog, response):
            if response == "scan" and self.profile is not None:
                self._run_scan(plan, skipped)

        dialog.connect("response", responded)
        dialog.present(self)

    def _run_scan(self, plan: list, skipped: list) -> None:
        run = _ScanRun(sum(len(requests) for _p, _k, requests in plan), len(plan))
        self._scan = run
        self.scan_button.set_sensitive(False)
        self._update_banner(run)
        self.banner.set_revealed(True)
        self.views.set_visible_child_name("activity")
        for provider in skipped:
            self.activity.set_status(provider.info.id, _("Skipped, no API key"), False)
        for provider, key, requests in plan:
            self.activity.set_status(provider.info.id, _("Running…"), True)
            # Each source has its own thread: one being slow or failing cannot hold up another.
            mode = self._mode_for(provider).id
            threading.Thread(target=self._source_worker, args=(run, provider, key, mode, requests),
                             daemon=True).start()

    def _source_worker(self, run: _ScanRun, provider: ExposureProvider, key, mode: str,
                       requests: list[ScanRequest]) -> None:
        info = provider.info

        def log(message, level="info"):
            GLib.idle_add(self._on_log, run, info.id, level, message)

        ctx = CheckContext(mode=mode, api_key=key, cancel=run.cancel, log=log)
        try:
            run_scan(provider, requests, ctx,
                     lambda outcome: GLib.idle_add(self._on_outcome, run, outcome))
        finally:
            GLib.idle_add(self._on_source_finished, run, info.id)

    def _on_log(self, run: _ScanRun, provider_id: str, level: str, message: str):
        if run is self._scan and self.profile is not None:
            self.activity.add_entry(self.profile.add_log(provider_id, level, message))
        return GLib.SOURCE_REMOVE

    def _update_banner(self, run: _ScanRun) -> None:
        self.banner.set_title(_("Checking {done} of {total}…").format(
            done=min(run.done + 1, run.total), total=run.total))

    def _on_outcome(self, run: _ScanRun, outcome: ScanOutcome):
        if run is not self._scan or self.profile is None:
            return GLib.SOURCE_REMOVE  # The profile was closed during the scan.
        run.done += 1
        if outcome.status == ScanStatus.CANCELLED:
            run.cancelled = True
        elif outcome.status == ScanStatus.FAILED:
            run.errors.append(outcome.error_code or "")
            run.source_errors[outcome.provider_id] = run.source_errors.get(outcome.provider_id, 0) + 1
        try:
            run.new += self.profile.record_outcome(outcome)
        except OSError:
            self.show_toast(_SAVE_FAILED)
        self._update_banner(run)
        self._refresh_pages()
        return GLib.SOURCE_REMOVE

    def _on_source_finished(self, run: _ScanRun, provider_id: str):
        if run is not self._scan:
            return GLib.SOURCE_REMOVE
        failed = run.source_errors.get(provider_id, 0)
        self.activity.set_status(provider_id, (
            _("Cancelled") if run.cancel.is_set() else
            _("Finished with {count} failed").format(count=failed) if failed else _("Finished")),
            False)
        run.sources_left -= 1
        if run.sources_left:
            return GLib.SOURCE_REMOVE
        try:
            self.profile.save()
        except OSError:
            self.show_toast(_SAVE_FAILED)
        self._scan = None
        self.banner.set_revealed(False)
        self.scan_button.set_sensitive(True)
        message = self._scan_summary(run)
        self.show_toast(message)
        if not self.is_active():
            notification = Gio.Notification.new(APP_NAME)
            notification.set_body(message)
            self.get_application().send_notification("scan-finished", notification)
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _scan_summary(run: _ScanRun) -> str:
        if run.cancelled or run.cancel.is_set():
            return _("Scan cancelled.")
        if run.errors:
            return _("{failed} of {total} checks failed: {reason} "
                     "Failed checks say nothing about those addresses.").format(
                failed=len(run.errors), total=run.total, reason=describe_error(run.errors[0]))
        if run.new:
            return ngettext("Scan finished: {count} new exposure to review.",
                            "Scan finished: {count} new exposures to review.",
                            run.new).format(count=run.new)
        return _("Scan finished: nothing new known to the source.")

    def cancel_scan(self) -> None:
        if self._scan is not None:
            self._scan.cancel.set()
            self.banner.set_title(_("Cancelling…"))

    def is_scanning(self) -> bool:
        return self._scan is not None
