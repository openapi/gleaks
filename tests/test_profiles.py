"""The profile index: its rules, its data file and its honesty about uncertainty."""

import hashlib
import re
from urllib.parse import urlparse

import pytest

from gleaks.core.models import ActionType, EventKind, IdentifierType, detect_identifier
from gleaks.providers.base import CheckContext, HttpResponse, ProviderError, ScanCancelled
from gleaks.providers.profiles import SITES, ProfileIndexProvider, Site, Verdict


def site(**overrides):
    values = dict(id="s", name="Site", host="s.test", profile="https://s.test/{name}",
                  probe="https://api.s.test/{name}", example="x")
    values.update(overrides)
    return Site(**values)


def response(status=200, body=""):
    return HttpResponse(status, {}, body.encode())


@pytest.mark.parametrize("raw,kind,value", [
    ("Me@Example.com", IdentifierType.EMAIL, "me@example.com"),
    ("francescobianco", IdentifierType.USERNAME, "francescobianco"),
    ("@FrancescoBianco", IdentifierType.USERNAME, "francescobianco"),
    ("first.last-99", IdentifierType.USERNAME, "first.last-99"),
    ("  Mario   Rossi ", IdentifierType.TEXT, "Mario Rossi"),
])
def test_identifier_detection(raw, kind, value):
    assert detect_identifier(raw) == (kind, value)


@pytest.mark.parametrize("raw", ["", " ", "x", "a@b", "bad\x00name x", "y" * 200 + " z"])
def test_invalid_identifiers(raw):
    with pytest.raises(ValueError):
        detect_identifier(raw)


# -- classification ----------------------------------------------------------
@pytest.mark.parametrize("rules,resp,verdict", [
    ({}, response(200), Verdict.FOUND),
    ({}, response(404), Verdict.ABSENT),
    ({}, response(403), Verdict.INCONCLUSIVE),
    ({}, response(429), Verdict.INCONCLUSIVE),
    ({}, response(302), Verdict.INCONCLUSIVE),
    ({}, response(500), Verdict.INCONCLUSIVE),
    ({"absent_exact": "[]"}, response(200, " []\n"), Verdict.ABSENT),
    ({"absent_exact": "[]"}, response(200, '[{"id":1}]'), Verdict.FOUND),
    ({"absent_body": "not found"}, response(200, "profile not found"), Verdict.ABSENT),
    ({"found_body": "marker"}, response(200, "a login wall"), Verdict.INCONCLUSIVE),
    ({"found_body": "marker"}, response(200, "the marker"), Verdict.FOUND),
    ({"absent_status": (400,)}, response(400), Verdict.ABSENT),
])
def test_only_explicit_rules_can_say_absent(rules, resp, verdict):
    assert site(**rules).classify(resp) == verdict


# -- the data file -----------------------------------------------------------
def test_index_is_well_formed():
    assert len({entry.id for entry in SITES}) == len(SITES) >= 20
    for entry in SITES:
        re.compile(entry.pattern)
        assert "{name}" in entry.probe and "{name}" in entry.profile
        assert urlparse(entry.probe).scheme == "https"
        assert urlparse(entry.profile).scheme == "https"
        assert entry.host in urlparse(entry.profile).hostname or urlparse(entry.profile).hostname.endswith(entry.host)
        assert entry.accepts == "email" or entry.example


def test_names_cannot_change_the_url():
    for entry in SITES:
        assert not entry.applies_to("username", "../../admin")
        assert not entry.applies_to("username", "a/b?c=d")


def test_github_is_in_the_index():
    github = next(entry for entry in SITES if entry.id == "github")
    assert github.profile_url("francescobianco") == "https://github.com/francescobianco"


def test_gravatar_receives_only_a_hash():
    entry = next(item for item in SITES if item.id == "gravatar-email")
    digest = hashlib.sha256(b"me@example.com").hexdigest()
    assert digest in entry.probe_url("me@example.com")
    assert "example.com" not in entry.probe_url("me@example.com").replace("gravatar.com", "")


# -- the connector -----------------------------------------------------------
class Http:
    def __init__(self, answers):
        self.answers = answers
        self.requests = []

    def __call__(self, url, headers, timeout):
        self.requests.append((url, dict(headers)))
        answer = self.answers[urlparse(url).hostname]
        if isinstance(answer, Exception):
            raise answer
        return answer


def provider(*hosts):
    return ProfileIndexProvider([site(id=h, name=h, host=h, profile=f"https://{h}/{{name}}",
                                      probe=f"https://{h}/{{name}}") for h in hosts])


def run(prov, http, value="francescobianco", lines=None):
    ctx = CheckContext(mode="exact", http=http)
    ctx.cancel.wait = lambda timeout=None: False
    if lines is not None:
        ctx.log = lambda message, level="info": lines.append((level, message))
    return prov.check(value, ctx)


def test_found_pages_become_unconfirmed_profile_events():
    events = run(provider("a.test", "b.test"), Http({"a.test": response(200), "b.test": response(404)}))
    assert len(events) == 1
    event = events[0]
    assert event.kind == EventKind.PROFILE_PAGE
    assert event.source_url == "https://a.test/francescobianco"
    assert event.verification == "unverified"


def test_profile_pages_suggest_checking_ownership():
    from gleaks.core.models import recommended_actions

    assert recommended_actions((), EventKind.PROFILE_PAGE) == (ActionType.REVIEW_PROFILE,)


def test_every_site_is_logged_with_its_outcome():
    lines = []
    run(provider("a.test", "b.test", "c.test"),
        Http({"a.test": response(200), "b.test": response(404), "c.test": response(403)}), lines=lines)
    text = "\n".join(message for _level, message in lines)
    assert "a.test: page found" in text and "b.test: no page" in text
    assert "c.test: could not tell (HTTP 403)" in text
    assert "1 found, 1 without a page, 1 could not be checked" in text


def test_one_failing_site_does_not_stop_the_others():
    from gleaks.core.models import ErrorCode

    http = Http({"a.test": ProviderError(ErrorCode.NETWORK), "b.test": response(200)})
    assert len(run(provider("a.test", "b.test"), http)) == 1


def test_all_sites_failing_is_an_error_not_an_empty_result():
    from gleaks.core.models import ErrorCode

    with pytest.raises(ProviderError) as info:
        run(provider("a.test"), Http({"a.test": response(403)}))
    assert info.value.code == ErrorCode.NETWORK


def test_sites_that_refuse_the_name_get_no_request():
    prov = ProfileIndexProvider([site(pattern=r"^[0-9]+$")])
    http = Http({})
    with pytest.raises(ProviderError):
        run(prov, http)
    assert not http.requests


def test_cancel_stops_between_sites():
    prov = provider("a.test", "b.test")
    http = Http({"a.test": response(404), "b.test": response(404)})
    ctx = CheckContext(mode="exact", http=http)
    ctx.cancel.wait = lambda timeout=None: True
    with pytest.raises(ScanCancelled):
        prov.check("francescobianco", ctx)
    assert len(http.requests) == 1


def test_only_gravatar_receives_an_email():
    http = Http({"gravatar.com": response(404)})
    run(ProfileIndexProvider(), http, value="me@example.com")
    assert len(http.requests) == 1
    assert "gravatar.com" in http.requests[0][0]


# -- slow steps --------------------------------------------------------------
def test_each_site_is_one_step():
    prov = provider("a.test", "b.test")
    assert prov.plan("francescobianco") == ["a.test", "b.test"]
    http = Http({"a.test": response(200), "b.test": response(404)})
    ctx = CheckContext(mode="exact", http=http)
    assert len(prov.run_step("francescobianco", "a.test", ctx)) == 1
    assert len(http.requests) == 1


@pytest.mark.parametrize("status,code", [(429, "rate_limited"), (403, "unavailable")])
def test_an_unclear_step_raises_so_it_can_be_retried(status, code):
    ctx = CheckContext(mode="exact", http=Http({"a.test": response(status)}))
    with pytest.raises(ProviderError) as info:
        provider("a.test").run_step("francescobianco", "a.test", ctx)
    assert info.value.code == code
