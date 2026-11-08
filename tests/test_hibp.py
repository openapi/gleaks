"""The HIBP connector against simulated responses, modelled on the v3 API docs."""

import hashlib
import json

import pytest

from gleaks.core.models import ErrorCode, Verification
from gleaks.providers.base import CheckContext, HttpResponse, ProviderError, ScanCancelled
from gleaks.providers.hibp import MODE_DIRECT, MODE_KANON, HibpProvider, normalize_breach, plain_text

ADOBE = {
    "Name": "Adobe", "Title": "Adobe", "Domain": "adobe.com", "BreachDate": "2013-10-04",
    "AddedDate": "2013-12-04T00:00:00Z", "PwnCount": 152445165,
    "Description": 'In 2013 <em>accounts</em> were <a href="http://x">breached</a> &amp; sold.',
    "LogoPath": "https://logos.haveibeenpwned.com/Adobe.png", "DisclosureUrl": None,
    "DataClasses": ["Email addresses", "Passwords"], "IsVerified": True, "IsFabricated": False,
    "IsSensitive": False, "IsRetired": False, "IsSpamList": False, "IsMalware": False,
}
KEY = "0" * 32
EMAIL = "someone@example.com"


class Http:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, url, headers, timeout):
        self.requests.append((url, dict(headers)))
        return self.responses.pop(0)


def ok(payload):
    return HttpResponse(200, {}, json.dumps(payload).encode())


def status(code, headers=None, body=b""):
    return HttpResponse(code, headers or {}, body)


def check(http, mode=MODE_DIRECT, key=KEY, email=EMAIL, cancel=None):
    ctx = CheckContext(mode=mode, api_key=key, http=http)
    if cancel:
        ctx.cancel.set()
    return HibpProvider().check(email, ctx)


def test_direct_search_contract():
    http = Http(ok([ADOBE]))
    events = check(http)
    url, headers = http.requests[0]
    assert url == ("https://haveibeenpwned.com/api/v3/breachedaccount/"
                   "someone%40example.com?truncateResponse=false")
    assert headers["hibp-api-key"] == KEY
    assert headers["user-agent"].startswith("GLeaks/")
    event = events[0]
    assert (event.source, event.source_event_id, event.event_date) == ("hibp", "Adobe", "2013-10-04")
    assert event.data_classes == ("Email addresses", "Passwords")
    assert event.verification == Verification.VERIFIED


def test_404_means_no_known_exposure():
    assert check(Http(status(404))) == []


def test_missing_key_never_reaches_the_network():
    http = Http()
    with pytest.raises(ProviderError) as info:
        check(http, key=None)
    assert info.value.code == ErrorCode.MISSING_CREDENTIALS and not http.requests


@pytest.mark.parametrize("code,expected", [
    (401, ErrorCode.INVALID_CREDENTIALS), (403, ErrorCode.NOT_AUTHORIZED),
    (400, ErrorCode.INVALID_RESPONSE), (302, ErrorCode.INVALID_RESPONSE),
    (500, ErrorCode.UNAVAILABLE),
])
def test_status_codes_are_errors_not_empty_results(code, expected):
    with pytest.raises(ProviderError) as info:
        check(Http(status(code)))
    assert info.value.code == expected


def test_rate_limit_is_retried_after_the_requested_wait(monkeypatch):
    http = Http(status(429, {"retry-after": "2"}), ok([ADOBE]))
    waits = []
    ctx = CheckContext(mode=MODE_DIRECT, api_key=KEY, http=http)
    monkeypatch.setattr(ctx.cancel, "wait", lambda t=None: waits.append(t) or False)
    assert len(HibpProvider().check(EMAIL, ctx)) == 1
    assert waits == [2.5]


def test_rate_limit_gives_up_after_limited_retries(monkeypatch):
    http = Http(*[status(429, {"retry-after": "1"})] * 3)
    ctx = CheckContext(mode=MODE_DIRECT, api_key=KEY, http=http)
    monkeypatch.setattr(ctx.cancel, "wait", lambda t=None: False)
    with pytest.raises(ProviderError) as info:
        HibpProvider().check(EMAIL, ctx)
    assert info.value.code == ErrorCode.RATE_LIMITED and len(http.requests) == 3


def test_excessive_retry_after_is_not_honoured():
    http = Http(status(429, {"retry-after": "86400"}))
    with pytest.raises(ProviderError) as info:
        check(http)
    assert info.value.code == ErrorCode.RATE_LIMITED and len(http.requests) == 1


def test_cancel_during_rate_limit_wait(monkeypatch):
    ctx = CheckContext(mode=MODE_DIRECT, api_key=KEY, http=Http(status(429, {"retry-after": "1"})))
    monkeypatch.setattr(ctx.cancel, "wait", lambda t=None: True)
    with pytest.raises(ScanCancelled):
        HibpProvider().check(EMAIL, ctx)


def test_cancel_before_request():
    http = Http()
    with pytest.raises(ScanCancelled):
        check(http, cancel=True)
    assert not http.requests


@pytest.mark.parametrize("body", [b"not json", b'{"a":1}', b"[1]", b'[{"Name":5}]',
                                  b'[{"Name":"<bad>"}]', b'[{"Name":"A","DataClasses":"x"}]',
                                  b'[{"Name":"A","Title":7}]'])
def test_malformed_responses_are_errors(body):
    with pytest.raises(ProviderError) as info:
        check(Http(HttpResponse(200, {}, body)))
    assert info.value.code == ErrorCode.INVALID_RESPONSE


def test_descriptions_become_plain_text():
    assert plain_text(ADOBE["Description"]) == "In 2013 accounts were breached & sold."


def test_markup_in_fields_is_not_interpreted():
    text = plain_text("<script>alert(1)</script><b>ok</b>")
    assert "<" not in text


def test_non_https_disclosure_links_are_dropped():
    event = normalize_breach({**ADOBE, "DisclosureUrl": "javascript:alert(1)"})
    assert event.source_url is None
    event = normalize_breach({**ADOBE, "DisclosureUrl": "https://adobe.com/notice"})
    assert event.source_url == "https://adobe.com/notice"


def test_bad_domains_and_dates_are_dropped():
    event = normalize_breach({**ADOBE, "Domain": "<x>", "BreachDate": "yesterday"})
    assert event.domain is None and event.event_date is None


@pytest.mark.parametrize("field,expected", [
    ({"IsVerified": False}, Verification.UNVERIFIED),
    ({"IsFabricated": True}, Verification.FABRICATED),
])
def test_reliability_is_preserved(field, expected):
    assert normalize_breach({**ADOBE, **field}).verification == expected


def _digest(email):
    return hashlib.sha1(email.encode()).hexdigest().upper()


def test_k_anonymity_matches_the_documented_example():
    assert _digest("multiple-breaches@hibp-integration-tests.com").startswith("6B5917")


def test_k_anonymity_sends_only_the_prefix_and_ignores_other_addresses():
    digest = _digest(EMAIL)
    http = Http(ok([{"hashSuffix": "F" * 34, "websites": ["OtherPerson"]},
                    {"hashSuffix": digest[6:].lower(), "websites": ["Adobe"]}]), ok(ADOBE))
    events = check(http, mode=MODE_KANON)
    assert [event.source_event_id for event in events] == ["Adobe"]
    assert http.requests[0][0].endswith(f"/breachedaccount/range/{digest[:6]}")
    assert all(EMAIL not in url and "someone" not in url for url, _h in http.requests)
    assert http.requests[1][0].endswith("/breach/Adobe")
    assert "hibp-api-key" not in http.requests[1][1]
    assert len(http.requests) == 2  # OtherPerson was never looked up


def test_k_anonymity_absent_suffix_means_no_known_exposure():
    http = Http(ok([{"hashSuffix": "F" * 34, "websites": ["OtherPerson"]}]))
    assert check(http, mode=MODE_KANON) == []
    assert len(http.requests) == 1


def test_provider_declares_what_consent_needs():
    info = HibpProvider.info
    assert info.requires_api_key and info.attribution and info.destination
    assert all(mode.transmits for mode in info.modes)
    assert info.min_request_interval > 6
