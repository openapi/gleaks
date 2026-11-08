"""Drives slow searches from the GLib main loop, one request at a time."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from gi.repository import GLib

from ..core.jobs import Ticket
from ..core.models import ErrorCode, describe_error
from ..core.profile import Profile
from ..i18n import _
from ..providers.base import CheckContext, ProviderError, ScanCancelled, StepwiseProvider
from .common import format_time

log = logging.getLogger(__name__)


class JobScheduler:
    def __init__(self, profile: Profile, providers: dict[str, StepwiseProvider],
                 on_log: Callable[[str, str, str], None], on_progress: Callable[[int], None],
                 background_only: Callable[[], bool], on_tick: Callable[[], None]):
        self._profile = profile
        self._providers = providers
        self._on_log = on_log
        self._on_progress = on_progress
        self._background_only = background_only
        self._on_tick = on_tick
        self._cancel = threading.Event()
        self._busy = False
        self._source = GLib.timeout_add_seconds(1, self._tick)

    def stop(self) -> None:
        """Stop for good. A request already out is ignored; its step stays pending."""
        self._cancel.set()
        if self._source:
            GLib.source_remove(self._source)
            self._source = 0

    def _tick(self):
        self._on_tick()
        if self._cancel.is_set():
            self._source = 0
            return GLib.SOURCE_REMOVE
        if not self._busy:
            ticket = self._profile.next_ticket(self._background_only())
            if ticket is not None:
                self._start(ticket)
        return GLib.SOURCE_CONTINUE

    def _start(self, ticket: Ticket) -> None:
        provider = self._providers.get(ticket.provider_id)
        if provider is None:  # A source removed in a newer or older version.
            self._profile.fail_step(ticket, ErrorCode.INTERNAL)
            return
        self._busy = True
        threading.Thread(target=self._work, args=(provider, ticket), daemon=True).start()

    def _work(self, provider: StepwiseProvider, ticket: Ticket) -> None:
        def emit(message, level="info"):
            GLib.idle_add(self._emit_log, ticket.provider_id, level, message)

        ctx = CheckContext(mode=ticket.mode, cancel=self._cancel, log=emit)
        events, code = (), None
        try:
            events = tuple(provider.run_step(ticket.value, ticket.step, ctx))
        except ScanCancelled:
            return
        except ProviderError as exc:
            code = exc.code
        except Exception as exc:  # A faulty connector must not stop the queue.
            log.error("connector %s failed with %s", ticket.provider_id, type(exc).__name__)
            code = ErrorCode.INTERNAL
        GLib.idle_add(self._finish, ticket, events, code)

    def _emit_log(self, provider_id, level, message):
        if not self._cancel.is_set():
            self._on_log(provider_id, level, message)
        return GLib.SOURCE_REMOVE

    def _finish(self, ticket: Ticket, events, code):
        if self._cancel.is_set():
            return GLib.SOURCE_REMOVE
        self._busy = False
        new = 0
        try:
            if code is None:
                new = self._profile.complete_step(ticket, events)
            else:
                retry_at = self._profile.fail_step(ticket, code)
                reason = describe_error(code)
                self._on_log(ticket.provider_id, "warning", (
                    _("{step}: {reason} Trying again at {time}.").format(
                        step=ticket.step, reason=reason, time=format_time(retry_at))
                    if retry_at else
                    _("{step}: {reason} Giving up on this step.").format(
                        step=ticket.step, reason=reason)))
        except OSError:
            self._on_log(ticket.provider_id, "error", _("The profile could not be saved."))
        self._on_progress(new)
        return GLib.SOURCE_REMOVE
