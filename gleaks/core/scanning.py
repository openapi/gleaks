"""Runs checks against a provider. Holds no GTK and no database access.

:func:`run_scan` blocks, so the interface calls it from a worker thread and
stores each outcome back on the main thread.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..providers.base import CheckContext, ExposureProvider, ProviderError, ScanCancelled
from .models import ErrorCode, NormalizedEvent, ScanStatus, utcnow

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanRequest:
    identifier_id: int
    value: str


@dataclass(frozen=True)
class ScanOutcome:
    provider_id: str
    identifier_id: int
    mode: str
    started_at: str
    completed_at: str
    status: ScanStatus
    error_code: str | None = None
    events: tuple[NormalizedEvent, ...] = ()


def run_scan(provider: ExposureProvider, requests: Sequence[ScanRequest], ctx: CheckContext,
             on_outcome: Callable[[ScanOutcome], None]) -> None:
    """Check each request in order, pacing them to respect the source's limits."""
    for index, request in enumerate(requests):
        if index and ctx.cancel.wait(provider.info.min_request_interval):
            return
        if ctx.cancel.is_set():
            return
        on_outcome(_check_one(provider, request, ctx))


def _check_one(provider: ExposureProvider, request: ScanRequest, ctx: CheckContext) -> ScanOutcome:
    started = utcnow()
    status, error, events = ScanStatus.COMPLETED, None, ()
    try:
        events = tuple(provider.check(request.value, ctx))
    except ScanCancelled:
        status = ScanStatus.CANCELLED
    except ProviderError as exc:
        status, error = ScanStatus.FAILED, exc.code
    except Exception as exc:  # A faulty connector must not take the scan down.
        # Only the type: messages may quote the identifier or the request.
        log.error("connector %s failed with %s", provider.info.id, type(exc).__name__)
        status, error = ScanStatus.FAILED, ErrorCode.INTERNAL
    return ScanOutcome(provider.info.id, request.identifier_id, ctx.mode, started, utcnow(),
                       status, error, events)
