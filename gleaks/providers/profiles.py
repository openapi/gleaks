"""GLeaks' own profile index: is there a public page for this name on known sites?

The sites live in ``sites.json``, so adding one needs no code. Each site answers
one of three ways, and only an explicit rule can say "no profile": anything
unexpected (a login wall, a challenge, a timeout) is *inconclusive* and is
reported as such. A name match proves only that a page exists, not who owns it.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import quote

from .. import __version__
from ..core.models import (
    ErrorCode,
    EventKind,
    IdentifierType,
    NormalizedEvent,
    Verification,
    detect_identifier,
)
from ..i18n import _, ngettext
from .base import (
    CheckContext,
    ExposureProvider,
    HttpResponse,
    ProviderError,
    ProviderInfo,
    ProviderMode,
    ScanCancelled,
)

USER_AGENT = f"GLeaks/{__version__} (+https://github.com/openapi/gleaks)"
TIMEOUT = 10.0
REQUEST_DELAY = 0.25
_DEFAULT_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,38}$"


class Verdict(Enum):
    FOUND = "found"
    ABSENT = "absent"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    host: str
    profile: str
    probe: str
    example: str
    accepts: str = IdentifierType.USERNAME
    pattern: str = _DEFAULT_PATTERN
    found_status: tuple[int, ...] = (200,)
    absent_status: tuple[int, ...] = (404,)
    absent_body: str | None = None
    absent_exact: str | None = None
    found_body: str | None = None
    hash: str | None = None

    def applies_to(self, kind: str, name: str) -> bool:
        if self.accepts != kind:
            return False
        return kind == IdentifierType.EMAIL or re.match(self.pattern, name) is not None

    def _fill(self, template: str, name: str) -> str:
        value = hashlib.sha256(name.encode()).hexdigest() if self.hash == "sha256" else name
        return template.replace("{name}", quote(value, safe=""))

    def probe_url(self, name: str) -> str:
        return self._fill(self.probe, name)

    def profile_url(self, name: str) -> str:
        return self._fill(self.profile, name)

    def classify(self, response: HttpResponse) -> Verdict:
        text = response.body.decode("utf-8", "replace")
        if response.status in self.absent_status:
            return Verdict.ABSENT
        if response.status not in self.found_status:
            return Verdict.INCONCLUSIVE
        if self.absent_exact is not None and text.strip() == self.absent_exact:
            return Verdict.ABSENT
        if self.absent_body and self.absent_body in text:
            return Verdict.ABSENT
        if self.found_body and self.found_body not in text:
            return Verdict.INCONCLUSIVE
        return Verdict.FOUND


def load_sites(path: Path | None = None) -> tuple[Site, ...]:
    raw = json.loads((path or Path(__file__).with_name("sites.json")).read_text(encoding="utf-8"))
    sites = []
    for entry in raw:
        for key in ("found_status", "absent_status"):
            if key in entry:
                entry[key] = tuple(entry[key])
        sites.append(Site(**entry))
    return tuple(sites)


SITES = load_sites()


class ProfileIndexProvider(ExposureProvider):
    info = ProviderInfo(
        id="index",
        name=_("Profile index"),
        version="1",
        license="MIT",
        homepage="https://github.com/openapi/gleaks",
        destination=_("{count} public sites, listed in Preferences").format(count=len(SITES)),
        supported_identifiers=(IdentifierType.USERNAME, IdentifierType.EMAIL),
        modes=(ProviderMode("exact", _("Check each site"),
                            _("The name, to each site. For an email, only its hash, to Gravatar"),
                            _("No key or account")),),
        requires_api_key=False,
        api_key_url="",
        costs=_("Free, no key needed. A GLeaks tool: it checks which sites have a page "
                "with your name."),
        rate_limits=_("One request per site, one site at a time."),
        returns=_("Which sites have a public page with this name. A page may belong "
                  "to someone else."),
        attribution=_("Found by the GLeaks profile index."),
        capabilities=("profile-pages",),
        min_request_interval=2.0,
        category="gleaks",
        destinations=tuple(f"{site.name} ({site.host})" for site in SITES),
    )

    def __init__(self, sites: Sequence[Site] | None = None):
        self.sites = tuple(SITES if sites is None else sites)

    def check(self, value: str, ctx: CheckContext) -> Sequence[NormalizedEvent]:
        try:
            kind, name = detect_identifier(value)
        except ValueError as exc:
            raise ProviderError(ErrorCode.UNSUPPORTED_IDENTIFIER) from exc
        sites = [site for site in self.sites if site.applies_to(kind, name)]
        if not sites:
            ctx.log(_("No site in the index accepts this name"), "warning")
            raise ProviderError(ErrorCode.UNSUPPORTED_IDENTIFIER)
        ctx.log(ngettext("Checking {count} site", "Checking {count} sites, one at a time",
                         len(sites)).format(count=len(sites)))
        events, inconclusive = [], 0
        for index, site in enumerate(sites):
            if ctx.cancel.is_set() or (index and ctx.cancel.wait(REQUEST_DELAY)):
                raise ScanCancelled
            verdict, detail = self._probe(site, name, ctx)
            if verdict == Verdict.FOUND:
                ctx.log(_("{host}: page found").format(host=site.host))
                events.append(self._event(site, name))
            elif verdict == Verdict.ABSENT:
                ctx.log(_("{host}: no page").format(host=site.host))
            else:
                inconclusive += 1
                ctx.log(_("{host}: could not tell ({detail})").format(host=site.host, detail=detail),
                        "warning")
        ctx.log(_("{found} found, {absent} without a page, {unknown} could not be checked").format(
            found=len(events), absent=len(sites) - len(events) - inconclusive, unknown=inconclusive))
        if inconclusive == len(sites):
            raise ProviderError(ErrorCode.NETWORK)
        return events

    @staticmethod
    def _probe(site: Site, name: str, ctx: CheckContext) -> tuple[Verdict, str]:
        try:
            response = ctx.http(site.probe_url(name),
                                {"user-agent": USER_AGENT, "accept": "*/*"}, TIMEOUT)
        except ProviderError:
            return Verdict.INCONCLUSIVE, _("network error")
        return site.classify(response), f"HTTP {response.status}"

    def _event(self, site: Site, name: str) -> NormalizedEvent:
        return NormalizedEvent(
            source=self.info.id,
            source_event_id=f"{site.id}:{hashlib.sha256(name.encode()).hexdigest()[:24]}",
            title=_("{site} profile").format(site=site.name),
            domain=site.host,
            data_classes=("Usernames",),
            verification=Verification.UNVERIFIED,
            source_url=site.profile_url(name),
            kind=EventKind.PROFILE_PAGE,
        )
