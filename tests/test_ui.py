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
from gleaks.providers.base import ExposureProvider, ProviderError, ProviderInfo, ProviderMode, StepwiseProvider  # noqa: E402
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


class Keyless(Fake):
    info = ProviderInfo("keyless", "Keyless Source", "1", "MIT", "https://x", "free.example",
                        ("email", "username"), (ProviderMode("exact", "Exact", "The query", "No key"),),
                        False, "", "Free", "None", "Pages", "Found by Keyless",
                        min_request_interval=0)

    def check(self, value, ctx):
        self.seen.append((value, ctx.api_key))
        ctx.log("Sending query")
        return []


class Slow(StepwiseProvider):
    info = ProviderInfo("slow", "Slow Tool", "1", "MIT", "https://x", "slow.example", ("email",),
                        (ProviderMode("exact", "Exact", "The query", "No key"),), False, "",
                        "Free", "None", "Pages", "Found by Slow", category="gleaks")

    def __init__(self):
        self.steps_run = []

    def check(self, value, ctx):
        raise AssertionError("slow tools must go through the queue")

    def plan(self, value):
        return ["one", "two", "three"]

    def run_step(self, value, step, ctx):
        self.steps_run.append(step)
        ctx.log(f"did {step}")
        return []


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
    fake, keyless = Fake(), Keyless()
    monkeypatch.setattr(window_module, "PROVIDERS", {"fake": fake, "keyless": keyless})
    win = MainWindow(application=app)
    win.fake, win.keyless = fake, keyless
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
    add_address(harness, "a@b")
    assert harness.profile.identifiers() == []


def test_a_nickname_only_reaches_sources_that_accept_it(harness):
    add_address(harness, "francescobianco")
    assert harness.profile.identifiers()[0].type == "username"
    body = scan(harness)
    assert "free.example" in body and "fake.example" not in body
    assert harness.fake.seen == []
    assert harness.keyless.seen == [("francescobianco", None)]


def test_consent_precedes_every_transmission(harness):
    add_address(harness)
    body = scan(harness, consent="cancel")
    assert harness.fake.seen == [] and harness.keyless.seen == []
    assert "me@example.com" in body and "fake.example" in body and "The full address" in body
    assert "free.example" in body


def test_full_flow_with_hostile_text(harness):
    add_address(harness)
    scan(harness)
    assert harness.fake.seen == [("me@example.com", "KEY")]
    assert harness.keyless.seen == [("me@example.com", None)]
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
    harness.fake.fail = True
    scan(harness)
    assert harness.profile.exposures() == []
    subtitles = [row.get_subtitle() for row in rows(harness.dashboard._checks)]
    assert subtitles[0].startswith("Fake Source: Check failed")
    assert "Nothing known" not in subtitles[0]
    # The other source is independent of the failure.
    assert subtitles[1].startswith("Keyless Source: Nothing known")


def test_api_key_is_optional(harness, monkeypatch):
    monkeypatch.setattr(secret_store, "get_api_key", lambda _p: None)
    add_address(harness)
    body = scan(harness)
    assert "Fake Source: skipped" in body
    assert harness.fake.seen == []
    assert harness.keyless.seen == [("me@example.com", None)]


def test_scan_process_is_logged_per_source(harness):
    add_address(harness)
    scan(harness)
    assert harness.views.get_visible_child_name() == "activity"
    assert any("Sending query" in e.message for e in harness.profile.log_entries("keyless"))
    assert harness.activity.tracks["keyless"].lines.get_first_child() is not None
    assert harness.activity.tracks["keyless"].status.get_label() == "Finished"
    harness._clear_log()
    assert harness.profile.log_entries("keyless") == []


def test_with_no_runnable_source_preferences_open(harness, monkeypatch):
    monkeypatch.setattr(secret_store, "get_api_key", lambda _p: None)
    harness.profile.set_provider_enabled("keyless", False, "exact")
    add_address(harness)
    harness.start_scan()
    assert isinstance(visible_dialog(harness), Adw.PreferencesDialog)
    assert harness.fake.seen == []
    harness.get_visible_dialog().force_close()
    pump(lambda: harness.get_visible_dialog() is None)


@pytest.fixture
def slow(app, tmp_path, monkeypatch):
    """A window with one slow tool only, and no pause between steps."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(secret_store, "get_api_key", lambda _p: None)
    tool = Slow()
    monkeypatch.setattr(window_module, "PROVIDERS", {"slow": tool})
    win = MainWindow(application=app)
    win.tool = tool
    win.present()
    profile = Profile.create(tmp_path / "s.gleaks", "password1", "S", params=FAST)
    profile.set_pace(0)
    profile.add_email("me@example.com")
    win._show_profile(profile)
    yield win
    win._release_profile()
    win.destroy()
    pump(timeout=0.05)


def start_slow(win):
    win.start_scan()
    answer(win, "scan")


def test_slow_tools_run_step_by_step_and_finish(slow):
    start_slow(slow)
    assert slow.profile.jobs()[0].total == 3
    assert pump(lambda: slow.profile.jobs() == [], timeout=6)
    assert slow.tool.steps_run == ["one", "two", "three"]
    assert slow.profile.last_checks()[0].status == "completed"
    assert any("did two" in e.message for e in slow.profile.log_entries("slow"))


def test_paused_job_stops_and_resumes(slow):
    slow.profile.set_pace(3600)
    start_slow(slow)
    job = slow.profile.jobs()[0]
    slow._job_command("pause", job.id)
    assert pump(lambda: slow.profile.jobs()[0].status == "paused")
    pump(timeout=1.2)  # Lets a step already under way finish.
    done_before = len(slow.tool.steps_run)
    slow.profile.set_pace(0)
    pump(timeout=2.2)
    assert len(slow.tool.steps_run) == done_before
    slow._job_command("resume", job.id)
    assert pump(lambda: slow.profile.jobs() == [], timeout=6)


def test_background_job_hides_the_window_and_keeps_running(slow):
    slow.profile.set_pace(3600)
    identifier = slow.profile.identifiers()[0]
    job = slow.profile.create_job("slow", "exact", identifier.id, ["one", "two"])
    slow._set_job_background(job, True)
    assert pump(lambda: slow.profile.jobs()[0].background)
    slow.close()
    assert pump(lambda: not slow.get_visible())
    assert slow.profile is not None
    slow.present()
    assert slow.get_visible()
    assert slow._in_background is False


def test_closing_without_background_jobs_keeps_them_for_next_time(slow):
    slow.profile.set_pace(3600)
    start_slow(slow)
    path = slow.profile.path
    slow.close_profile()
    reopened = Profile.open(path, "password1")
    assert [job.status for job in reopened.jobs()] == ["running"]
    reopened.close()


def test_repeat_queues_a_search_when_due(slow, monkeypatch):
    slow.profile.set_repeat_days(1, now="2020-01-01T00:00:00Z")
    assert pump(lambda: slow.tool.steps_run or slow.profile.jobs(), timeout=4)
    assert not slow.profile.repeat_due()


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
