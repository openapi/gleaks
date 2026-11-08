"""Keyless web search: looks for pages that publicly mention an identifier.

Sends one exact-phrase query per identifier to two engines. Marginalia has an
official public API but a small index. DuckDuckGo covers far more, but its HTML
endpoint is not an API, so the page is parsed defensively: anything that is not
recognizably a results page is an error, never "nothing found". When DuckDuckGo
asks for a human check GLeaks stops using it and says so. It never tries to get
past the check.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, unquote, urldefrag, urlparse

from .. import __version__
from ..core.models import (
    ErrorCode,
    EventKind,
    IdentifierType,
    NormalizedEvent,
    Verification,
    describe_error,
    detect_identifier,
)
from ..i18n import _
from .base import (
    CheckContext,
    ExposureProvider,
    HttpResponse,
    ProviderError,
    ProviderInfo,
    ProviderMode,
    ScanCancelled,
)

SEARCH_URL = "https://html.duckduckgo.com/html/?q="
MARGINALIA_URL = "https://api.marginalia.nu/public/search/"
USER_AGENT = f"GLeaks/{__version__} (+https://github.com/openapi/gleaks)"
TIMEOUT = 20.0
MAX_RESULTS = 10


def browser_search_url(value: str) -> str:
    """The same search, for the user to run in their own browser."""
    return f"https://duckduckgo.com/?q={quote(_query(value), safe='')}"


def _query(value: str) -> str:
    return f'"{value}"'


class _ResultsPage(HTMLParser):
    """Collects results, and whether this really is a results page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.is_results_page = False
        self.is_challenge = False
        self.results: list[dict] = []
        self._capture: str | None = None
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "form" and values.get("id") == "challenge-form":
            self.is_challenge = True
        if tag == "div" and values.get("id") == "links" and "results" in classes:
            self.is_results_page = True
        if tag != "a" or self._capture:
            return
        if "result__a" in classes:
            self.results.append({"href": values.get("href") or "", "title": "", "snippet": ""})
            self._capture = "title"
        elif "result__snippet" in classes and self.results:
            self._capture = "snippet"

    def handle_endtag(self, tag):
        if tag == "a":
            self._capture = None

    def handle_data(self, data):
        if self._capture and self.results:
            self.results[-1][self._capture] += data


def _target_url(href: str) -> str | None:
    """Unwrap DuckDuckGo's redirect, dropping ads and anything not http(s)."""
    if href.startswith("//"):
        href = f"https:{href}"
    parsed = urlparse(href)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if not target:
            return None
        href = target
        parsed = urlparse(href)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    if parsed.hostname.endswith("duckduckgo.com"):
        return None
    return urldefrag(href)[0][:2048]


def _clean(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _mentions(value: str) -> re.Pattern:
    # It must stand alone: "spike.me@x.com" is not a mention of "me@x.com".
    return re.compile(rf"(?<![\w.+-]){re.escape(value)}(?![\w-]|\.\w)", re.IGNORECASE)


class WebSearchProvider(ExposureProvider):
    info = ProviderInfo(
        id="web",
        name=_("Web search"),
        version="1",
        license="Public search engine; connector MIT",
        homepage="https://marginalia-search.com",
        destination="api.marginalia.nu, html.duckduckgo.com",
        supported_identifiers=(IdentifierType.EMAIL, IdentifierType.USERNAME, IdentifierType.TEXT),
        modes=(ProviderMode("exact", _("Exact search"),
                            _("The full identifier, as a search query"),
                            _("No key or account")),),
        requires_api_key=False,
        api_key_url="",
        costs=_("Free, no key needed. Finds public pages, not breaches."),
        rate_limits=_("One query per identifier and engine. If DuckDuckGo asks for a "
                      "human check, GLeaks stops using it."),
        returns=_("Public pages that mention the exact identifier."),
        attribution=_("Found with Marginalia Search or DuckDuckGo."),
        capabilities=("web-mentions",),
        min_request_interval=20.0,
        category="gleaks",
    )

    def check(self, value: str, ctx: CheckContext) -> Sequence[NormalizedEvent]:
        try:
            _kind, canonical = detect_identifier(value)
        except ValueError as exc:
            raise ProviderError(ErrorCode.UNSUPPORTED_IDENTIFIER) from exc
        results: list[dict] = []
        answered, failure = 0, None
        for engine in (self._ask_marginalia, self._ask_duckduckgo):
            if ctx.cancel.is_set():
                raise ScanCancelled
            try:
                results += engine(canonical, ctx)
                answered += 1
            except ProviderError as exc:
                failure = exc
                if exc.code != ErrorCode.BLOCKED:
                    ctx.log(_("This search engine failed: {reason}").format(
                        reason=describe_error(exc.code)), "warning")
        if not answered:
            raise failure
        events = self._mentions_of(canonical, results)
        ctx.log(_("{total} results in all, {kept} mention the exact identifier").format(
            total=len(results), kept=len(events)))
        return events

    @staticmethod
    def _send(url: str, host: str, query: str, ctx: CheckContext) -> HttpResponse:
        ctx.log(_("Sending query to {host}: {query}").format(host=host, query=query))
        response = ctx.http(url, {"user-agent": USER_AGENT, "accept": "*/*"}, TIMEOUT)
        ctx.log(_("{host} answered HTTP {status}, {size} bytes").format(
            host=host, status=response.status, size=len(response.body)))
        return response

    def _ask_marginalia(self, value: str, ctx: CheckContext) -> list[dict]:
        query = _query(value)
        response = self._send(f"{MARGINALIA_URL}{quote(query, safe='')}?count=20",
                              "api.marginalia.nu", query, ctx)
        if response.status == 429:
            raise ProviderError(ErrorCode.RATE_LIMITED)
        if response.status != 200:
            raise ProviderError(ErrorCode.UNAVAILABLE if response.status >= 500
                                else ErrorCode.INVALID_RESPONSE)
        try:
            items = json.loads(response.body)["results"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(ErrorCode.INVALID_RESPONSE) from exc
        if not isinstance(items, list):
            raise ProviderError(ErrorCode.INVALID_RESPONSE)
        found = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                raise ProviderError(ErrorCode.INVALID_RESPONSE)
            found.append({"href": item["url"], "title": str(item.get("title") or ""),
                          "snippet": str(item.get("description") or "")})
        return found

    def _ask_duckduckgo(self, value: str, ctx: CheckContext) -> list[dict]:
        if ctx.state.get("duckduckgo_blocked"):
            ctx.log(_("Skipping DuckDuckGo: it asked for a human check earlier in this scan."),
                    "warning")
            raise ProviderError(ErrorCode.BLOCKED)
        query = _query(value)
        response = self._send(SEARCH_URL + quote(query, safe=""), "html.duckduckgo.com", query, ctx)
        page = self._parse(response.body)
        if page.is_challenge or response.status in (202, 403):
            # Respect the check: no retry, and no more queries during this scan.
            ctx.state["duckduckgo_blocked"] = True
            ctx.log(_("DuckDuckGo asked for a human check, so GLeaks stopped using it. "
                      "You can run the search yourself: {url}").format(
                url=browser_search_url(value)), "warning")
            raise ProviderError(ErrorCode.BLOCKED)
        if response.status == 429:
            raise ProviderError(ErrorCode.RATE_LIMITED)
        if response.status != 200 or not page.is_results_page:
            raise ProviderError(ErrorCode.UNAVAILABLE if response.status >= 500
                                else ErrorCode.INVALID_RESPONSE)
        return page.results

    @staticmethod
    def _parse(body: bytes) -> _ResultsPage:
        page = _ResultsPage()
        page.feed(body.decode("utf-8", "replace"))
        page.close()
        return page

    def _mentions_of(self, value: str, results: list[dict]) -> list[NormalizedEvent]:
        pattern = _mentions(value)
        events: dict[str, NormalizedEvent] = {}
        for result in results:
            url = _target_url(result["href"])
            title = _clean(result["title"], 200)
            snippet = _clean(result["snippet"], 1000)
            if url is None or url in events:
                continue
            if not pattern.search(f"{title}\n{snippet}\n{unquote(url)}"):
                continue
            host = urlparse(url).hostname
            events[url] = NormalizedEvent(
                source=self.info.id,
                source_event_id=hashlib.sha256(url.encode("utf-8")).hexdigest()[:32],
                title=title or host,
                domain=host,
                description=snippet,
                verification=Verification.UNVERIFIED,
                source_url=url,
                kind=EventKind.WEB_MENTION,
            )
            if len(events) == MAX_RESULTS:
                break
        return list(events.values())
