"""Runs checks against a provider. Holds no GTK and no database access.

:func:`run_scan` blocks, so the interface calls it from a worker thread and
stores each outcome back on the main thread.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..providers.base import CheckContext, ExposureProvider, ProviderError, ScanCancelled
from ..i18n import _
from .models import ErrorCode, NormalizedEvent, ScanStatus, describe_error, utcnow

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanRequest:
    identifier_id: int
    value: str
    kind: str = "email"


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
        interval = provider.info.min_request_interval
        if index and interval:
            ctx.log(_("Waiting {seconds:g} s before the next request").format(seconds=interval))
        if index and ctx.cancel.wait(interval):
            ctx.log(_("Cancelled"), "warning")
            return
        if ctx.cancel.is_set():
            ctx.log(_("Cancelled"), "warning")
            return
        ctx.log(_("Checking {value}").format(value=request.value))
        outcome = _check_one(provider, request, ctx)
        _log_outcome(ctx, outcome)
        on_outcome(outcome)


def _log_outcome(ctx: CheckContext, outcome: ScanOutcome) -> None:
    if outcome.status == ScanStatus.COMPLETED:
        ctx.log(_("Finished: {count} found").format(count=len(outcome.events)))
    elif outcome.status == ScanStatus.CANCELLED:
        ctx.log(_("Cancelled"), "warning")
    else:
        ctx.log(_("Failed, so this says nothing about the address: {reason}").format(
            reason=describe_error(outcome.error_code or "")), "error")


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
