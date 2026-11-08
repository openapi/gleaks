"""Headless tests for encryption, the profile store and the scan engine."""

import sqlite3
import threading

import pytest

from gleaks.core import crypto
from gleaks.core.migrations import SCHEMA_VERSION, NewerSchemaError
from gleaks.core.models import (
    ActionStatus,
    ActionType,
    ErrorCode,
    NormalizedEvent,
    ScanStatus,
    normalize_email,
    recommended_actions,
)
from gleaks.core.profile import DamagedProfileError, DuplicateIdentifierError, Profile
from gleaks.core.scanning import ScanOutcome, ScanRequest, run_scan
from gleaks.providers.base import CheckContext, ExposureProvider, ProviderError, ProviderInfo

FAST = crypto.KdfParams(log2n=10)
PASSWORD = "correct horse battery"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "me.gleaks"


@pytest.fixture
def profile(path):
    created = Profile.create(path, PASSWORD, "Me", params=FAST)
    yield created
    created.close()


def event(name="Adobe", classes=("Email addresses", "Passwords")):
    return NormalizedEvent(source="fake", source_event_id=name, title=name, event_date="2013-10-04",
                           data_classes=tuple(classes))


def outcome(identifier_id, events=(), status=ScanStatus.COMPLETED, error=None):
    return ScanOutcome("fake", identifier_id, "direct", "2026-11-08T10:00:00Z",
                       "2026-11-08T10:00:01Z", status, error, tuple(events))


# -- container ---------------------------------------------------------------
def test_file_holds_no_plaintext(path, profile):
    profile.add_email("secret.person@example.com")
    blob = path.read_bytes()
    assert blob.startswith(crypto.MAGIC)
    assert b"secret.person" not in blob
    assert b"SQLite format" not in blob


def test_save_leaves_only_the_profile_with_private_permissions(path, profile):
    profile.add_email("a@example.com")
    assert [item.name for item in path.parent.iterdir()] == [path.name]
    assert path.stat().st_mode & 0o777 == 0o600


def test_every_save_uses_a_new_nonce(path, profile):
    profile.save()
    first = path.read_bytes()
    profile.save()
    assert first[:-16] != path.read_bytes()[:-16]


def test_reopen_keeps_the_data(path):
    created = Profile.create(path, PASSWORD, "Me", params=FAST)
    identifier = created.add_email("a@example.com")
    created.record_outcome(outcome(identifier.id, [event()]))
    created.close()
    reopened = Profile.open(path, PASSWORD)
    assert reopened.name == "Me"
    assert [item.value for item in reopened.identifiers()] == ["a@example.com"]
    assert reopened.exposures()[0].title == "Adobe"
    reopened.close()


def test_wrong_password_is_rejected(path, profile):
    with pytest.raises(crypto.WrongPasswordError):
        Profile.open(path, "not the password")


def test_tampering_is_detected(path, profile):
    blob = bytearray(path.read_bytes())
    blob[-1] ^= 1
    path.write_bytes(blob)
    with pytest.raises(crypto.WrongPasswordError):
        Profile.open(path, PASSWORD)


def test_header_is_authenticated(path, profile):
    blob = bytearray(path.read_bytes())
    blob[len(crypto.MAGIC) + 5] ^= 1  # first salt byte: derives another key
    path.write_bytes(blob)
    with pytest.raises(crypto.WrongPasswordError):
        Profile.open(path, PASSWORD)


@pytest.mark.parametrize("content", [b"", b"short", b"PK\x03\x04" + b"x" * 200])
def test_foreign_files_are_rejected(tmp_path, content):
    target = tmp_path / "x.gleaks"
    target.write_bytes(content)
    with pytest.raises(crypto.ContainerError):
        Profile.open(target, PASSWORD)


def test_hostile_kdf_parameters_are_refused(path, profile):
    blob = bytearray(path.read_bytes())
    blob[len(crypto.MAGIC) + 2] = 40  # log2(n) that would exhaust memory
    path.write_bytes(blob)
    with pytest.raises(crypto.ContainerError):
        Profile.open(path, PASSWORD)


def _rewrite(path, password, mutate=None, raw=None):
    """Seal arbitrary database bytes into a valid container."""
    params, salt = crypto.read_header(path.read_bytes())
    key = crypto.derive_key(password, salt, params)
    plain = raw
    if plain is None:
        conn = sqlite3.connect(":memory:")
        conn.deserialize(crypto.open_sealed(key, path.read_bytes()))
        mutate(conn)
        plain = conn.serialize()
    path.write_bytes(crypto.seal(key, salt, params, plain))


def test_valid_container_with_garbage_is_damaged(path, profile):
    _rewrite(path, PASSWORD, raw=b"this is not a database" * 100)
    with pytest.raises(DamagedProfileError):
        Profile.open(path, PASSWORD)


def test_newer_schema_is_refused(path, profile):
    _rewrite(path, PASSWORD, lambda c: c.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}"))
    with pytest.raises(NewerSchemaError):
        Profile.open(path, PASSWORD)


def test_change_password(path, profile):
    profile.change_password("a completely new one")
    with pytest.raises(crypto.WrongPasswordError):
        Profile.open(path, PASSWORD)
    other = Profile.open(path, "a completely new one")
    other._conn.close()


def test_failed_save_keeps_the_previous_file_and_stays_dirty(path, profile, monkeypatch):
    profile.add_email("a@example.com")
    before = path.read_bytes()
    import gleaks.core.profile as module

    def broken(*_a):
        raise OSError("disk full")

    monkeypatch.setattr(module.os, "replace", broken)
    with pytest.raises(OSError):
        profile.save()
    assert path.read_bytes() == before
    assert profile.dirty
    assert [item.name for item in path.parent.iterdir()] == [path.name]
    monkeypatch.undo()
    profile.save()
    assert not profile.dirty


# -- identifiers -------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("  User@Example.COM ", "user@example.com"),
    ("a.b+c@sub.example.it", "a.b+c@sub.example.it"),
])
def test_email_normalization(raw, expected):
    assert normalize_email(raw) == expected


@pytest.mark.parametrize("raw", ["", "x", "a@b", "a b@example.com", "a@@example.com",
                                 "a@example..com", "a@example.com\n@x", "a" * 250 + "@example.com"])
def test_invalid_emails(raw):
    with pytest.raises(ValueError):
        normalize_email(raw)


def test_duplicates_are_rejected_regardless_of_case(profile):
    profile.add_email("a@example.com")
    with pytest.raises(DuplicateIdentifierError):
        profile.add_email("A@EXAMPLE.com")


def test_removing_an_identifier_removes_only_what_it_alone_supported(profile):
    first = profile.add_email("a@example.com")
    second = profile.add_email("b@example.com")
    profile.record_outcome(outcome(first.id, [event("Shared"), event("OnlyFirst")]))
    profile.record_outcome(outcome(second.id, [event("Shared")]))
    profile.remove_identifier(first.id)
    assert [item.title for item in profile.exposures()] == ["Shared"]
    assert profile.stats().events == 1


def test_disabled_identifiers_are_excluded_from_scans(profile):
    identifier = profile.add_email("a@example.com")
    profile.set_identifier_enabled(identifier.id, False)
    assert profile.identifiers(enabled_only=True) == []


# -- evidence and history ----------------------------------------------------
def test_new_exposures_are_counted_once(profile):
    identifier = profile.add_email("a@example.com")
    assert profile.record_outcome(outcome(identifier.id, [event()])) == 1
    assert profile.record_outcome(outcome(identifier.id, [event()])) == 0
    assert len(profile.exposures()) == 1


def test_one_event_can_involve_several_identifiers(profile):
    first = profile.add_email("a@example.com")
    second = profile.add_email("b@example.com")
    profile.record_outcome(outcome(first.id, [event()]))
    profile.record_outcome(outcome(second.id, [event()]))
    assert profile.stats().events == 1
    exposures = profile.exposures()
    assert len(exposures) == 2
    assert profile.identifiers_for_breach(exposures[0].breach_id) == ["a@example.com",
                                                                      "b@example.com"]


@pytest.mark.parametrize("status,error", [(ScanStatus.FAILED, ErrorCode.NETWORK),
                                          (ScanStatus.FAILED, ErrorCode.RATE_LIMITED),
                                          (ScanStatus.CANCELLED, None)])
def test_a_failed_check_never_changes_the_evidence(profile, status, error):
    identifier = profile.add_email("a@example.com")
    profile.record_outcome(outcome(identifier.id, [event()]))
    before = profile.exposures()
    profile.record_outcome(outcome(identifier.id, [event("Ignored")], status, error))
    assert profile.exposures() == before
    check = profile.last_checks()[0]
    assert check.status == status and check.error_code == error and check.found == 0


def test_a_clean_check_differs_from_an_unchecked_identifier(profile):
    identifier = profile.add_email("a@example.com")
    assert profile.last_checks()[0].status is None
    profile.record_outcome(outcome(identifier.id))
    check = profile.last_checks()[0]
    assert check.status == ScanStatus.COMPLETED and check.found == 0


def test_an_exposure_missing_from_a_later_answer_is_kept(profile):
    identifier = profile.add_email("a@example.com")
    profile.record_outcome(outcome(identifier.id, [event()]))
    profile.record_outcome(outcome(identifier.id, []))
    assert len(profile.exposures()) == 1


def test_review_clears_the_new_flag(profile):
    identifier = profile.add_email("a@example.com")
    profile.record_outcome(outcome(identifier.id, [event()]))
    assert profile.stats().new_evidence == 1
    profile.mark_reviewed(profile.exposures()[0].id)
    assert profile.stats().new_evidence == 0


def test_search_treats_wildcards_literally(profile):
    identifier = profile.add_email("a@example.com")
    profile.record_outcome(outcome(identifier.id, [event("Adobe"), event("Shop_100%")]))
    assert [item.title for item in profile.exposures(query="adob")] == ["Adobe"]
    assert [item.title for item in profile.exposures(query="_100%")] == ["Shop_100%"]
    assert profile.exposures(query="%") != profile.exposures()


# -- actions -----------------------------------------------------------------
def test_recommendations_follow_the_exposed_data():
    assert ActionType.CHANGE_PASSWORD in recommended_actions(("Passwords",))
    assert ActionType.CHANGE_PASSWORD not in recommended_actions(("Email addresses",))
    assert ActionType.REVIEW_RECOVERY in recommended_actions(("Security questions and answers",))
    assert recommended_actions(()) == (ActionType.CHECK_SIGNINS,)


def test_completing_actions_keeps_the_evidence(profile):
    identifier = profile.add_email("a@example.com")
    profile.record_outcome(outcome(identifier.id, [event()]))
    for action in profile.actions():
        profile.set_action_status(action.id, ActionStatus.COMPLETED)
    assert profile.stats().open_actions == 0
    assert len(profile.exposures()) == 1
    assert all(item.completed_at for item in profile.actions())


def test_repeat_scans_do_not_reset_or_duplicate_actions(profile):
    identifier = profile.add_email("a@example.com")
    profile.record_outcome(outcome(identifier.id, [event()]))
    first = profile.actions()[0]
    profile.set_action_status(first.id, ActionStatus.DISMISSED)
    count = len(profile.actions())
    profile.record_outcome(outcome(identifier.id, [event()]))
    assert len(profile.actions()) == count
    assert profile.actions(statuses=(ActionStatus.DISMISSED,))[0].id == first.id


# -- engine ------------------------------------------------------------------
class FakeProvider(ExposureProvider):
    info = ProviderInfo("fake", "Fake", "1", "MIT", "https://x", "x", ("email",), (), False, "",
                        "", "", "", "")

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = []

    def check(self, value, ctx):
        self.calls.append(value)
        return self.behaviour(value, ctx)


def collect(provider, values, ctx=None):
    results = []
    run_scan(provider, [ScanRequest(i, v) for i, v in enumerate(values)],
             ctx or CheckContext(mode="direct"), results.append)
    return results


def test_one_failure_does_not_stop_the_other_checks():
    def behaviour(value, _ctx):
        if value == "bad":
            raise ProviderError(ErrorCode.RATE_LIMITED)
        return [event()]

    results = collect(FakeProvider(behaviour), ["bad", "good"])
    assert [r.status for r in results] == [ScanStatus.FAILED, ScanStatus.COMPLETED]
    assert results[0].error_code == ErrorCode.RATE_LIMITED and results[0].events == ()


def test_connector_bugs_become_errors_without_leaking_details(caplog):
    def behaviour(value, _ctx):
        raise RuntimeError(f"boom {value}")

    results = collect(FakeProvider(behaviour), ["private@example.com"])
    assert results[0].error_code == ErrorCode.INTERNAL
    assert "private@example.com" not in caplog.text


def test_cancel_stops_remaining_checks():
    ctx = CheckContext(mode="direct")

    def behaviour(_value, context):
        context.cancel.set()
        return []

    provider = FakeProvider(behaviour)
    results = collect(provider, ["a", "b", "c"], ctx)
    assert len(results) == 1 and provider.calls == ["a"]


def test_requests_are_paced():
    provider = FakeProvider(lambda *_a: [])
    provider.info = ProviderInfo("fake", "Fake", "1", "MIT", "https://x", "x", ("email",), (),
                                 False, "", "", "", "", "", min_request_interval=0.05)
    waits = []
    ctx = CheckContext(mode="direct")

    class Spy(threading.Event):
        def wait(self, timeout=None):
            waits.append(timeout)
            return False

    ctx.cancel = Spy()
    collect(provider, ["a", "b", "c"], ctx)
    assert waits == [0.05, 0.05]
