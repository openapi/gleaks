"""The web search connector against pages shaped like DuckDuckGo's HTML results."""

import json
from urllib.parse import quote

import pytest

from gleaks.core.models import ErrorCode, EventKind, Verification
from gleaks.providers.base import CheckContext, HttpResponse, ProviderError, ScanCancelled
from gleaks.providers.web import WebSearchProvider, browser_search_url

DOWN = HttpResponse(503, {}, b"")

EMAIL = "someone@example.com"


def result(url, title, snippet):
    href = f"//duckduckgo.com/l/?uddg={quote(url, safe='')}&amp;rut=abc"
    return (f'<div class="result"><h2><a rel="nofollow" class="result__a" href="{href}">{title}</a></h2>'
            f'<a class="result__snippet" href="{href}">{snippet}</a></div>')


def page(*results):
    return f'<html><div class="serp__results"><div id="links" class="results">{"".join(results)}</div></div></html>'


CHALLENGE = ('<form id="challenge-form" action="//duckduckgo.com/anomaly.js"></form>'
             '<div class="anomaly-modal__mask">Please complete the following challenge</div>')


class Http:
    """DuckDuckGo answers status/body; Marginalia is down unless given a response."""

    def __init__(self, status, body, marginalia=DOWN):
        self.status, self.body, self.marginalia = status, body, marginalia
        self.requests = []
        self.marginalia_requests = []

    def __call__(self, url, headers, timeout):
        if "marginalia" in url:
            self.marginalia_requests.append(url)
            return self.marginalia
        self.requests.append((url, dict(headers)))
        return HttpResponse(self.status, {}, self.body.encode())


def check(http, lines=None):
    ctx = CheckContext(mode="exact", http=http)
    if lines is not None:
        ctx.log = lambda message, level="info": lines.append((level, message))
    return WebSearchProvider().check(EMAIL, ctx)


def test_needs_no_key_and_sends_one_exact_query():
    http = Http(200, page())
    assert check(http) == []
    assert len(http.requests) == 1
    url, headers = http.requests[0]
    assert url == "https://html.duckduckgo.com/html/?q=%22someone%40example.com%22"
    assert headers["user-agent"].startswith("GLeaks/")
    assert "hibp-api-key" not in headers
    assert WebSearchProvider.info.requires_api_key is False


def test_a_mention_becomes_an_unconfirmed_event():
    http = Http(200, page(result("https://forum.test/post#c1", "A &amp; B", f"contact <b>{EMAIL}</b> now")))
    event = check(http)[0]
    assert event.kind == EventKind.WEB_MENTION
    assert event.verification == Verification.UNVERIFIED
    assert (event.title, event.domain) == ("A & B", "forum.test")
    assert event.source_url == "https://forum.test/post"
    assert event.description == f"contact {EMAIL} now"


def test_address_in_the_url_counts():
    url = f"https://lists.test/{quote(EMAIL)}"
    assert len(check(Http(200, page(result(url, "List", "nothing here"))))) == 1


@pytest.mark.parametrize("text", ["spike.someone@example.com", "someone@example.com.evil.test",
                                  "no-someone@example.com", "nothing relevant"])
def test_near_matches_are_discarded(text):
    assert check(Http(200, page(result("https://a.test/", "T", text)))) == []


def test_address_at_the_end_of_a_sentence_counts():
    assert len(check(Http(200, page(result("https://a.test/", "T", f"Write to {EMAIL}."))))) == 1


def test_case_is_ignored():
    assert len(check(Http(200, page(result("https://a.test/", "T", EMAIL.upper()))))) == 1


def test_duplicates_ads_and_bad_schemes_are_dropped():
    body = page(
        result("https://a.test/#x", "T", EMAIL),
        result("https://a.test/#y", "T", EMAIL),
        result("javascript:alert(1)", "T", EMAIL),
        f'<a class="result__a" href="https://duckduckgo.com/y.js?ad_domain=x">{EMAIL}</a>',
    )
    assert [e.source_url for e in check(Http(200, body))] == ["https://a.test/"]


def test_results_are_capped():
    body = page(*[result(f"https://a.test/{n}", "T", EMAIL) for n in range(30)])
    assert len(check(Http(200, body))) == 10


@pytest.mark.parametrize("status,body", [(202, CHALLENGE), (200, CHALLENGE), (403, "denied")])
def test_a_human_check_is_an_error_and_is_explained(status, body):
    lines = []
    with pytest.raises(ProviderError) as info:
        check(Http(status, body), lines)
    assert info.value.code == ErrorCode.BLOCKED
    assert any(level == "warning" and browser_search_url(EMAIL) in text for level, text in lines)


@pytest.mark.parametrize("status,body,code", [
    (200, "<html>something else entirely</html>", ErrorCode.INVALID_RESPONSE),
    (429, "", ErrorCode.RATE_LIMITED),
    (500, "", ErrorCode.UNAVAILABLE),
    (302, "", ErrorCode.INVALID_RESPONSE),
])
def test_anything_but_a_results_page_is_an_error_not_an_empty_result(status, body, code):
    with pytest.raises(ProviderError) as info:
        check(Http(status, body))
    assert info.value.code == code


def test_the_log_shows_exactly_what_was_sent():
    lines = []
    check(Http(200, page(result("https://a.test/", "T", EMAIL), result("https://b.test/", "T", "x"))), lines)
    text = "\n".join(message for _level, message in lines)
    assert f'"{EMAIL}"' in text and "html.duckduckgo.com" in text
    assert "2 results in all, 1 mention the exact identifier" in text


def test_cancel_before_sending():
    http = Http(200, page())
    ctx = CheckContext(mode="exact", http=http)
    ctx.cancel.set()
    with pytest.raises(ScanCancelled):
        WebSearchProvider().check(EMAIL, ctx)
    assert not http.requests


def test_invalid_identifier():
    ctx = CheckContext(mode="exact", http=Http(200, page()))
    with pytest.raises(ProviderError) as info:
        WebSearchProvider().check("x", ctx)
    assert info.value.code == ErrorCode.UNSUPPORTED_IDENTIFIER


def test_nicknames_and_phrases_are_searched_exactly():
    http = Http(200, page(result("https://a.test/", "T", "by Mario Rossi here")))
    ctx = CheckContext(mode="exact", http=http)
    assert len(WebSearchProvider().check("Mario Rossi", ctx)) == 1
    assert http.requests[0][0].endswith("%22Mario%20Rossi%22")


def marginalia(*items):
    return HttpResponse(200, {}, json.dumps({"results": list(items)}).encode())


def test_marginalia_is_queried_with_the_exact_phrase():
    http = Http(200, page(), marginalia({"url": "https://m.test/", "title": "T", "description": EMAIL}))
    events = check(http)
    assert http.marginalia_requests == [
        "https://api.marginalia.nu/public/search/%22someone%40example.com%22?count=20"]
    assert [e.source_url for e in events] == ["https://m.test/"]


def test_results_from_both_engines_are_merged_without_duplicates():
    item = {"url": "https://same.test/", "title": "T", "description": EMAIL}
    other = result("https://ddg.test/", "T", EMAIL)
    body = page(result("https://same.test/", "T", EMAIL), other)
    assert sorted(e.source_url for e in check(Http(200, body, marginalia(item)))) == [
        "https://ddg.test/", "https://same.test/"]


def test_a_blocked_engine_does_not_cost_the_other_ones_answer():
    lines = []
    item = {"url": "https://m.test/", "title": "T", "description": EMAIL}
    events = check(Http(202, CHALLENGE, marginalia(item)), lines)
    assert len(events) == 1
    assert any(level == "warning" and "human check" in text for level, text in lines)


def test_duckduckgo_is_not_asked_again_after_a_challenge():
    http = Http(202, CHALLENGE, marginalia())
    ctx = CheckContext(mode="exact", http=http)
    provider = WebSearchProvider()
    provider.check(EMAIL, ctx)
    provider.check("other@example.com", ctx)
    assert len(http.requests) == 1
    assert len(http.marginalia_requests) == 2


@pytest.mark.parametrize("body", [b"not json", b"{}", b'{"results":5}', b'{"results":[1]}'])
def test_malformed_marginalia_answers_are_failures_not_empty_results(body):
    lines = []
    with pytest.raises(ProviderError):
        check(Http(500, "", HttpResponse(200, {}, body)), lines)
