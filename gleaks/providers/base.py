"""The contract between the scanning engine and a connector."""

from __future__ import annotations

import http.client
import socket
import threading
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from ..core.models import ErrorCode, NormalizedEvent

MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class ProviderError(Exception):
    def __init__(self, code: ErrorCode):
        super().__init__(code)
        self.code = code


class ScanCancelled(Exception):
    pass


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


HttpGet = Callable[[str, Mapping[str, str], float], HttpResponse]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # A redirect would carry the API key to another URL.


_opener = urllib.request.build_opener(_NoRedirect)


def https_get(url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse:
    """GET over verified TLS. HTTP error statuses are returned, not raised."""
    if not url.startswith("https://"):
        raise ProviderError(ErrorCode.INTERNAL)
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        try:
            response = _opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ProviderError(ErrorCode.INVALID_RESPONSE)
            return HttpResponse(response.status, response.headers, body)
    except (OSError, socket.timeout, http.client.HTTPException) as exc:  # URLError is an OSError
        raise ProviderError(ErrorCode.NETWORK) from exc


@dataclass(frozen=True)
class ProviderMode:
    """One way of querying a source, described for the consent dialog."""

    id: str
    label: str
    transmits: str
    requirement: str = ""


@dataclass(frozen=True)
class ProviderInfo:
    """What a connector must declare before it may receive any data."""

    id: str
    name: str
    version: str
    license: str
    homepage: str
    destination: str
    supported_identifiers: tuple[str, ...]
    modes: tuple[ProviderMode, ...]
    requires_api_key: bool
    api_key_url: str
    costs: str
    rate_limits: str
    returns: str
    attribution: str
    capabilities: tuple[str, ...] = ()
    min_request_interval: float = 0.0
    category: str = "third-party"  # or "gleaks", for tools GLeaks provides itself
    destinations: tuple[str, ...] = ()

    def mode(self, mode_id: str) -> ProviderMode:
        return next((m for m in self.modes if m.id == mode_id), self.modes[0])


@dataclass
class CheckContext:
    mode: str
    api_key: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    http: HttpGet = https_get
    log: Callable[..., None] = lambda message, level="info": None
    state: dict = field(default_factory=dict)  # Shared by the checks of one scan.


class ExposureProvider(ABC):
    info: ProviderInfo

    @abstractmethod
    def check(self, value: str, ctx: CheckContext) -> Sequence[NormalizedEvent]:
        """Return what the source knows about ``value``; empty means no known exposure.

        Blocking. Must raise :class:`ProviderError` for every failure and
        :class:`ScanCancelled` once ``ctx.cancel`` is set, so that an error can
        never be mistaken for an empty result.
        """


class StepwiseProvider(ExposureProvider):
    """A connector whose work splits into single requests, run slowly over time."""

    @abstractmethod
    def plan(self, value: str) -> list[str]:
        """The steps needed for ``value``. Raises ProviderError if there are none."""

    @abstractmethod
    def run_step(self, value: str, step: str, ctx: CheckContext) -> Sequence[NormalizedEvent]:
        """Make the single request of ``step``. Raises ProviderError if it gives no answer."""
