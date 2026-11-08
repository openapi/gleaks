"""Have I Been Pwned connector (https://haveibeenpwned.com/API/v3).

Responses are untrusted: each field is type-checked and bounded, descriptions
are reduced to plain text, and only the fields GLeaks displays are kept.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from html.parser import HTMLParser
from urllib.parse import quote

from .. import __version__
from ..core.models import ErrorCode, IdentifierType, NormalizedEvent, Verification, normalize_email
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

BASE_URL = "https://haveibeenpwned.com/api/v3"
USER_AGENT = f"GLeaks/{__version__} (+https://github.com/openapi/gleaks)"
TIMEOUT = 20.0
MAX_RETRIES = 2
MAX_RETRY_WAIT = 90.0

MODE_DIRECT = "direct"
MODE_KANON = "k-anonymity"

_NAME_RE = re.compile(r"^[\w .'&+-]{1,128}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9.-]{1,253}$")
_FLAGS = {"IsSensitive": "sensitive", "IsSpamList": "spam-list", "IsMalware": "malware",
          "IsStealerLog": "stealer-log"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(markup: str, limit: int = 8000) -> str:
    """Drop all markup from a provider's HTML description."""
    extractor = _TextExtractor()
    extractor.feed(markup)
    extractor.close()
    return re.sub(r"\s+", " ", "".join(extractor.parts)).strip()[:limit]


def _invalid() -> ProviderError:
    return ProviderError(ErrorCode.INVALID_RESPONSE)


def _optional_str(raw: dict, key: str, limit: int) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise _invalid()
    return value[:limit]


def normalize_breach(raw: object) -> NormalizedEvent:
    if not isinstance(raw, dict):
        raise _invalid()
    name = raw.get("Name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise _invalid()
    classes = raw.get("DataClasses", [])
    if not isinstance(classes, list) or not all(isinstance(item, str) for item in classes):
        raise _invalid()
    date = _optional_str(raw, "BreachDate", 32)
    added = _optional_str(raw, "AddedDate", 32)
    domain = _optional_str(raw, "Domain", 253)
    url = _optional_str(raw, "DisclosureUrl", 2048)
    if raw.get("IsFabricated") is True:
        verification = Verification.FABRICATED
    elif raw.get("IsVerified") is False:
        verification = Verification.UNVERIFIED
    else:
        verification = Verification.VERIFIED
    return NormalizedEvent(
        source=HibpProvider.info.id,
        source_event_id=name,
        title=(_optional_str(raw, "Title", 200) or name).strip() or name,
        domain=domain if domain and _DOMAIN_RE.match(domain) else None,
        description=plain_text(_optional_str(raw, "Description", 64 * 1024) or ""),
        event_date=date[:10] if date and _DATE_RE.match(date) else None,
        published_at=added if added and _DATE_RE.match(added) else None,
        data_classes=tuple(sorted({item.strip()[:100] for item in classes[:200] if item.strip()})),
        verification=verification,
        flags=tuple(flag for key, flag in _FLAGS.items() if raw.get(key) is True),
        source_url=url if url and url.startswith("https://") else None,
    )


def _json(response: HttpResponse) -> object:
    try:
        return json.loads(response.body)
    except ValueError as exc:
        raise _invalid() from exc


class HibpProvider(ExposureProvider):
    info = ProviderInfo(
        id="hibp",
        name="Have I Been Pwned",
        version="1",
        license="Proprietary service; connector MIT",
        homepage="https://haveibeenpwned.com",
        destination="haveibeenpwned.com",
        supported_identifiers=(IdentifierType.EMAIL,),
        modes=(
            ProviderMode(MODE_DIRECT, _("Direct search"),
                         _("The full email address"), _("Any API subscription")),
            ProviderMode(MODE_KANON, _("Private search (k-anonymity)"),
                         _("Only the first 6 characters of a SHA-1 hash of the address"),
                         _("A Pro or High RPM subscription")),
        ),
        requires_api_key=True,
        api_key_url="https://haveibeenpwned.com/API/Key",
        costs=_("Requires your own paid Have I Been Pwned subscription."),
        rate_limits=_("Set by your plan. GLeaks waits between requests."),
        returns=_("Names and details of known breaches that include the address."),
        attribution=_("Breach data provided by Have I Been Pwned."),
        capabilities=("breaches",),
        # The smallest plan allows 10 requests a minute; HIBP advises a margin.
        min_request_interval=6.5,
    )

    def check(self, value: str, ctx: CheckContext) -> Sequence[NormalizedEvent]:
        try:
            email = normalize_email(value)
        except ValueError as exc:
            raise ProviderError(ErrorCode.UNSUPPORTED_IDENTIFIER) from exc
        if not ctx.api_key:
            raise ProviderError(ErrorCode.MISSING_CREDENTIALS)
        if ctx.mode == MODE_KANON:
            return self._check_kanon(email, ctx)
        return self._check_direct(email, ctx)

    def _check_direct(self, email: str, ctx: CheckContext) -> list[NormalizedEvent]:
        url = f"{BASE_URL}/breachedaccount/{quote(email, safe='')}?truncateResponse=false"
        ctx.log(_("Sending the full address to {host}").format(host=self.info.destination))
        response = self._get(url, ctx, authenticated=True)
        if response.status == 404:
            return []
        breaches = _json(response)
        if not isinstance(breaches, list):
            raise _invalid()
        return [normalize_breach(item) for item in breaches]

    def _check_kanon(self, email: str, ctx: CheckContext) -> list[NormalizedEvent]:
        digest = hashlib.sha1(email.encode("utf-8")).hexdigest().upper()  # noqa: S324
        ctx.log(_("Sending only the hash prefix {prefix}").format(prefix=digest[:6]))
        response = self._get(f"{BASE_URL}/breachedaccount/range/{digest[:6]}", ctx,
                             authenticated=True)
        if response.status == 404:
            return []
        entries = _json(response)
        if not isinstance(entries, list):
            raise _invalid()
        # HIBP's terms: discard every entry that is not this address, immediately.
        names = self._names_for_suffix(entries, digest[6:])
        return [self._catalogue_entry(name, ctx) for name in names]

    @staticmethod
    def _names_for_suffix(entries: list, suffix: str) -> list[str]:
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hashSuffix"), str):
                raise _invalid()
            if entry["hashSuffix"].upper() != suffix:
                continue
            names = entry.get("websites")
            if not isinstance(names, list) or not all(
                    isinstance(name, str) and _NAME_RE.match(name) for name in names):
                raise _invalid()
            return names
        return []

    def _catalogue_entry(self, name: str, ctx: CheckContext) -> NormalizedEvent:
        """Look up a breach by name; the catalogue is public and needs no key."""
        response = self._get(f"{BASE_URL}/breach/{quote(name, safe='')}", ctx, authenticated=False)
        if response.status == 404:
            return NormalizedEvent(source=self.info.id, source_event_id=name, title=name,
                                   verification=Verification.UNVERIFIED)
        return normalize_breach(_json(response))

    def _get(self, url: str, ctx: CheckContext, authenticated: bool) -> HttpResponse:
        headers = {"user-agent": USER_AGENT, "accept": "application/json"}
        if authenticated:
            headers["hibp-api-key"] = ctx.api_key
        for attempt in range(MAX_RETRIES + 1):
            if ctx.cancel.is_set():
                raise ScanCancelled
            response = ctx.http(url, headers, TIMEOUT)
            ctx.log(_("Received HTTP {status}").format(status=response.status))
            if response.status in (200, 404):
                return response
            if response.status in (429, 503) and attempt < MAX_RETRIES:
                wait = self._retry_wait(response)
                if wait is not None:
                    ctx.log(_("Asked to slow down, retrying in {seconds:g} s").format(seconds=wait),
                            "warning")
                    if ctx.cancel.wait(wait):
                        raise ScanCancelled
                    continue
            raise ProviderError(self._error_for(response.status))
        raise AssertionError("unreachable")

    @staticmethod
    def _retry_wait(response: HttpResponse) -> float | None:
        if response.status == 503:
            return 5.0
        try:
            seconds = float(response.headers.get("retry-after", ""))
        except ValueError:
            return None
        return seconds + 0.5 if 0 <= seconds <= MAX_RETRY_WAIT else None

    @staticmethod
    def _error_for(status: int) -> ErrorCode:
        return {401: ErrorCode.INVALID_CREDENTIALS, 403: ErrorCode.NOT_AUTHORIZED,
                429: ErrorCode.RATE_LIMITED}.get(
            status, ErrorCode.UNAVAILABLE if status >= 500 else ErrorCode.INVALID_RESPONSE)
