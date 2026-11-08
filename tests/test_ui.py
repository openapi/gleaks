"""Drives the real window. Skipped where GTK or a display is missing."""

import time

import pytest

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Secret", "1")
    from gi.repository import Adw, Gdk, Gio, GLib, Gtk
except (ValueError, ImportError):
    pytest.skip("GTK 4, Libadwaita or libsecret not available", allow_module_level=True)
if Gtk.init_check() is False or Gdk.Display.get_default() is None:
    pytest.skip("no display", allow_module_level=True)

from gleaks import secret_store  # noqa: E402
from gleaks.core import crypto  # noqa: E402
from gleaks.core.models import ActionStatus, ErrorCode, NormalizedEvent  # noqa: E402
from gleaks.core.profile import Profile  # noqa: E402
from gleaks.providers.base import ExposureProvider, ProviderError, ProviderInfo, ProviderMode  # noqa: E402
from gleaks.ui import window as window_module  # noqa: E402
from gleaks.ui.window import MainWindow  # noqa: E402

FAST = crypto.KdfParams(log2n=10)


def pump(condition=lambda: False, timeout=2.0):
    context = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while time.monotonic() < end and not condition():
        while context.pending():
            context.iteration(False)
        time.sleep(0.005)
    return condition()


class Fake(ExposureProvider):
    info = ProviderInfo("fake", "Fake Source", "1", "MIT", "https://x", "fake.example", ("email",),
                        (ProviderMode("direct", "Direct", "The full address", "Any plan"),),
                        True, "https://x/key", "Free", "None", "Breaches", "Data from Fake",
                        min_request_interval=0)

    def __init__(self):
        self.fail = False
        self.seen = []

    def check(self, value, ctx):
        self.seen.append((value, ctx.api_key))
        if self.fail:
            raise ProviderError(ErrorCode.NETWORK)
        return [NormalizedEvent(
            source="fake", source_event_id="Evil", title="<b>Evil</b> & Co",
            description="<i>not markup</i> & text", event_date="2020-01-02",
            data_classes=("Passwords",))]


@pytest.fixture(scope="module")
def app():
    application = Adw.Application(application_id="io.github.openapi.GLeaks.Test",
                                  flags=Gio.ApplicationFlags.NON_UNIQUE)
    application.register(None)
    return application


@pytest.fixture
def harness(app, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(secret_store, "get_api_key", lambda _p: "KEY")
    win = MainWindow(application=app)
    win.provider = Fake()
    win.present()
    profile = Profile.create(tmp_path / "t.gleaks", "password1", "<i>Test</i>", params=FAST)
    win._show_profile(profile)
    pump(timeout=0.1)
    yield win
    win._release_profile()
    win.destroy()
    pump(timeout=0.05)


def visible_dialog(win):
    pump(lambda: win.get_visible_dialog() is not None)
    return win.get_visible_dialog()


def answer(win, response):
    dialog = visible_dialog(win)
    assert isinstance(dialog, Adw.AlertDialog)
    body = dialog.get_body()
    dialog.emit("response", response)
    dialog.force_close()
    pump(lambda: win.get_visible_dialog() is None)
    return body


def rows(listbox):
    child, found = listbox.get_first_child(), []
    while child:
        found.append(child)
        child = child.get_next_sibling()
    return found


def add_address(win, value="me@example.com"):
    win.identifiers._entry.set_text(value)
    win.identifiers._on_add(win.identifiers._entry)


def scan(win, consent="scan"):
    win.start_scan()
    body = answer(win, consent)
    pump(lambda: not win.is_scanning())
    return body


def test_opens_on_the_overview(harness):
    assert harness.stack.get_visible_child_name() == "profile"
    assert harness.views.get_visible_child_name() == "dashboard"


def test_scan_without_identifiers_explains_itself(harness):
    harness.start_scan()
    pump(timeout=0.05)
    assert harness.views.get_visible_child_name() == "identifiers"
    assert harness.get_visible_dialog() is None


def test_invalid_address_is_not_added(harness):
    add_address(harness, "nope")
    assert harness.profile.identifiers() == []


def test_consent_precedes_every_transmission(harness):
    add_address(harness)
    body = scan(harness, consent="cancel")
    assert harness.provider.seen == []
    assert "me@example.com" in body and "fake.example" in body and "The full address" in body


def test_full_flow_with_hostile_text(harness):
    add_address(harness)
    scan(harness)
    assert harness.provider.seen == [("me@example.com", "KEY")]
    stats = harness.profile.stats()
    assert (stats.events, stats.new_evidence) == (1, 1)

    row = rows(harness.exposures._list)[0]
    assert row.get_title() == "<b>Evil</b> & Co" and row.get_use_markup() is False
    exposure = harness.profile.exposures()[0]
    harness._open_exposure(exposure.id)
    dialog = visible_dialog(harness)
    pump(timeout=0.05)
    assert harness.profile.stats().new_evidence == 0
    dialog.force_close()
    pump(lambda: harness.get_visible_dialog() is None)

    action = harness.profile.actions()[0]
    harness._set_action_status(action.id, ActionStatus.COMPLETED)
    pump(lambda: harness.profile.actions()[0].status == ActionStatus.COMPLETED)


def test_failed_scan_is_not_shown_as_clean(harness):
    add_address(harness)
    harness.provider.fail = True
    scan(harness)
    assert harness.profile.exposures() == []
    subtitle = rows(harness.dashboard._checks)[0].get_subtitle()
    assert subtitle.startswith("Check failed")
    assert "Nothing known" not in subtitle


def test_missing_api_key_opens_preferences(harness, monkeypatch):
    monkeypatch.setattr(secret_store, "get_api_key", lambda _p: None)
    add_address(harness)
    harness.start_scan()
    assert isinstance(visible_dialog(harness), Adw.PreferencesDialog)
    assert harness.provider.seen == []
    harness.get_visible_dialog().force_close()
    pump(lambda: harness.get_visible_dialog() is None)


def test_close_profile_returns_to_welcome_and_persists(harness):
    add_address(harness)
    path = harness.profile.path
    harness.close_profile()
    assert harness.profile is None
    assert harness.stack.get_visible_child_name() == "welcome"
    reopened = Profile.open(path, "password1")
    assert [item.value for item in reopened.identifiers()] == ["me@example.com"]
    reopened.close()


def test_window_module_uses_shipped_provider_by_default():
    assert window_module.PROVIDERS["hibp"].info.name == "Have I Been Pwned"
