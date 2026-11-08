"""Slow searches: long jobs made of small steps, stored in the profile.

A job is one source checking one identifier. Each step is a single web request.
Steps are spread out over time, at most one every ``pace`` seconds across all
jobs, and their state is saved after each one, so a job can be paused, survive
the application closing, and carry on from where it stopped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import ErrorCode, NormalizedEvent, ScanStatus, utcnow

DEFAULT_PACE = 30
MAX_ATTEMPTS = 3
_RETRY_SHORT = 15 * 60
_RETRY_LONG = 60 * 60
_DAY = 24 * 60 * 60


class JobStatus:
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus:
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


_ACTIVE = (JobStatus.RUNNING, JobStatus.PAUSED)


def shift(moment: str, seconds: float) -> str:
    parsed = datetime.fromisoformat(moment.replace("Z", "+00:00")).astimezone(timezone.utc)
    return (parsed + timedelta(seconds=seconds)).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z")


def retry_delay(code: str, attempts: int) -> int:
    """Back off hard when a site says it wants fewer requests."""
    base = _RETRY_LONG if code in (ErrorCode.RATE_LIMITED, ErrorCode.BLOCKED) else _RETRY_SHORT
    return base * 4 ** (attempts - 1)


@dataclass(frozen=True)
class Ticket:
    """One step to perform."""

    job_id: int
    step_id: int
    provider_id: str
    mode: str
    identifier_id: int
    value: str
    step: str
    attempts: int


@dataclass(frozen=True)
class Job:
    id: int
    provider_id: str
    identifier_id: int
    identifier_value: str
    status: str
    background: bool
    created_at: str
    total: int
    finished: int
    failed: int
    found: int
    next_retry_at: str | None

    @property
    def active(self) -> bool:
        return self.status in _ACTIVE


class JobsMixin:
    """The part of a Profile that manages jobs."""

    # -- settings ------------------------------------------------------------
    def _meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM profile_meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def _write_meta(self, key: str, value: str | None) -> None:
        if value is None:
            self._conn.execute("DELETE FROM profile_meta WHERE key = ?", (key,))
        else:
            self._conn.execute(
                "INSERT INTO profile_meta (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (key, value))

    def pace(self) -> int:
        return int(self._meta("pace_seconds") or DEFAULT_PACE)

    def set_pace(self, seconds: int) -> None:
        with self._conn:
            self._write_meta("pace_seconds", str(seconds))
        self.save()

    def background_by_default(self) -> bool:
        return self._meta("background_default") == "1"

    def set_background_by_default(self, enabled: bool) -> None:
        with self._conn:
            self._write_meta("background_default", "1" if enabled else "0")
        self.save()

    def repeat_days(self) -> int:
        return int(self._meta("repeat_days") or 0)

    def set_repeat_days(self, days: int, now: str | None = None) -> None:
        with self._conn:
            self._write_meta("repeat_days", str(days))
            self._write_meta("next_repeat_at",
                             shift(now or utcnow(), days * _DAY) if days else None)
        self.save()

    def repeat_due(self, now: str | None = None) -> bool:
        due = self._meta("next_repeat_at")
        return due is not None and due <= (now or utcnow())

    def mark_repeat_started(self, now: str | None = None) -> None:
        with self._conn:
            self._write_meta("next_repeat_at", shift(now or utcnow(), self.repeat_days() * _DAY))
        self.save()

    # -- creating and listing ------------------------------------------------
    def create_job(self, provider_id: str, mode: str, identifier_id: int, steps: list[str],
                   background: bool = False, now: str | None = None) -> int | None:
        """Queue a search. Returns None if an identical one is still under way."""
        now = now or utcnow()
        if not steps or self._conn.execute(
                "SELECT 1 FROM jobs WHERE provider_id = ? AND identifier_id = ? AND status IN (?, ?)",
                (provider_id, identifier_id, *_ACTIVE)).fetchone():
            return None
        with self._conn:
            scan_id = self._conn.execute(
                "INSERT INTO scans (provider_id, identifier_id, mode, started_at, completed_at,"
                " status) VALUES (?, ?, ?, ?, ?, ?)",
                (provider_id, identifier_id, mode, now, now, ScanStatus.RUNNING)).lastrowid
            job_id = self._conn.execute(
                "INSERT INTO jobs (provider_id, mode, identifier_id, scan_id, status, background,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (provider_id, mode, identifier_id, scan_id, JobStatus.RUNNING, int(background),
                 now)).lastrowid
            self._conn.executemany("INSERT INTO job_steps (job_id, step) VALUES (?, ?)",
                                   [(job_id, step) for step in steps])
        self.save()
        return job_id

    def jobs(self, active_only: bool = True) -> list[Job]:
        where = f" WHERE j.status IN ('{_ACTIVE[0]}', '{_ACTIVE[1]}')" if active_only else ""
        rows = self._conn.execute(
            "SELECT j.id, j.provider_id, j.identifier_id, i.value, j.status, j.background,"
            " j.created_at, COUNT(s.id), SUM(s.status != 'pending'), SUM(s.status = 'failed'),"
            " j.found, MIN(s.not_before) FROM jobs j JOIN identifiers i ON i.id = j.identifier_id"
            " JOIN job_steps s ON s.job_id = j.id" + where + " GROUP BY j.id ORDER BY j.id").fetchall()
        return [Job(r[0], r[1], r[2], r[3], r[4], bool(r[5]), r[6], r[7], r[8], r[9], r[10], r[11])
                for r in rows]

    def has_active_background_jobs(self) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM jobs WHERE status = ? AND background = 1",
            (JobStatus.RUNNING,)).fetchone() is not None

    # -- user controls -------------------------------------------------------
    def _set_status(self, job_id: int, status: str, allowed: tuple[str, ...]) -> None:
        with self._conn:
            self._conn.execute(
                f"UPDATE jobs SET status = ? WHERE id = ? AND status IN "
                f"({', '.join('?' * len(allowed))})", (status, job_id, *allowed))
        self.save()

    def pause_job(self, job_id: int) -> None:
        self._set_status(job_id, JobStatus.PAUSED, (JobStatus.RUNNING,))

    def resume_job(self, job_id: int) -> None:
        self._set_status(job_id, JobStatus.RUNNING, (JobStatus.PAUSED,))

    def set_all_paused(self, paused: bool) -> None:
        old, new = _ACTIVE if paused else _ACTIVE[::-1]
        with self._conn:
            self._conn.execute("UPDATE jobs SET status = ? WHERE status = ?", (new, old))
        self.save()

    def set_job_background(self, job_id: int, background: bool) -> None:
        with self._conn:
            self._conn.execute("UPDATE jobs SET background = ? WHERE id = ?",
                               (int(background), job_id))
        self.save()

    def cancel_job(self, job_id: int, now: str | None = None) -> None:
        now = now or utcnow()
        with self._conn:
            changed = self._conn.execute(
                "UPDATE jobs SET status = ?, completed_at = ? WHERE id = ? AND status IN (?, ?)",
                (JobStatus.CANCELLED, now, job_id, *_ACTIVE)).rowcount
            if changed:
                self._close_scan(job_id, ScanStatus.CANCELLED, None, now)
        self.save()

    def _close_scan(self, job_id: int, status: str, error: str | None, now: str) -> None:
        self._conn.execute(
            "UPDATE scans SET status = ?, error_code = ?, completed_at = ?,"
            " found = (SELECT found FROM jobs WHERE id = ?)"
            " WHERE id = (SELECT scan_id FROM jobs WHERE id = ?)",
            (status, error, now, job_id, job_id))

    # -- running -------------------------------------------------------------
    def next_ticket(self, background_only: bool = False, now: str | None = None) -> Ticket | None:
        """The next step that may run now, taking turns between jobs.

        Returns None until the pace since the previous request has passed. That
        time is stored, so reopening the application cannot shorten the wait.
        """
        now = now or utcnow()
        last = self._meta("last_step_at")
        if last and now < shift(last, self.pace()):
            return None
        row = self._conn.execute(
            "SELECT j.id, s.id, j.provider_id, j.mode, j.identifier_id, i.value, s.step, s.attempts"
            " FROM job_steps s JOIN jobs j ON j.id = s.job_id"
            " JOIN identifiers i ON i.id = j.identifier_id"
            " WHERE j.status = 'running' AND s.status = 'pending'"
            " AND (s.not_before IS NULL OR s.not_before <= ?)"
            + (" AND j.background = 1" if background_only else "") +
            " ORDER BY j.last_step_at IS NOT NULL, j.last_step_at, j.id, s.id LIMIT 1",
            (now,)).fetchone()
        return Ticket(*row) if row else None

    def _step_is_live(self, ticket: Ticket) -> bool:
        """False if the job was cancelled or removed while its request was out."""
        return self._conn.execute(
            "SELECT 1 FROM job_steps s JOIN jobs j ON j.id = s.job_id WHERE s.id = ?"
            " AND s.status = 'pending' AND j.status IN (?, ?)",
            (ticket.step_id, *_ACTIVE)).fetchone() is not None

    def _touch(self, ticket: Ticket, now: str) -> None:
        self._write_meta("last_step_at", now)
        self._conn.execute("UPDATE jobs SET last_step_at = ? WHERE id = ?", (now, ticket.job_id))

    def complete_step(self, ticket: Ticket, events: tuple[NormalizedEvent, ...],
                      now: str | None = None) -> int:
        """Store a step's findings and return how many exposures are new."""
        from .scanning import ScanOutcome

        now = now or utcnow()
        if not self._step_is_live(ticket):
            return 0
        scan_id = self._conn.execute("SELECT scan_id FROM jobs WHERE id = ?",
                                     (ticket.job_id,)).fetchone()[0]
        outcome = ScanOutcome(ticket.provider_id, ticket.identifier_id, ticket.mode, now, now,
                              ScanStatus.COMPLETED)
        new = 0
        with self._conn:
            for event in events:
                new += self._store_evidence(scan_id, outcome, event)
            self._conn.execute("UPDATE job_steps SET status = ?, completed_at = ? WHERE id = ?",
                               (StepStatus.DONE, now, ticket.step_id))
            self._conn.execute("UPDATE jobs SET found = found + ? WHERE id = ?",
                               (len(events), ticket.job_id))
            self._touch(ticket, now)
            self._finish_if_done(ticket.job_id, None, now)
        self.save()
        return new

    def fail_step(self, ticket: Ticket, code: str, now: str | None = None) -> str | None:
        """Record a failure. Returns when the step will be retried, or None if it won't."""
        now = now or utcnow()
        if not self._step_is_live(ticket):
            return None
        attempts = ticket.attempts + 1
        retry_at = shift(now, retry_delay(code, attempts)) if attempts < MAX_ATTEMPTS else None
        with self._conn:
            self._conn.execute(
                "UPDATE job_steps SET attempts = ?, not_before = ?, status = ?, error_code = ?,"
                " completed_at = ? WHERE id = ?",
                (attempts, retry_at, StepStatus.PENDING if retry_at else StepStatus.FAILED, code,
                 None if retry_at else now, ticket.step_id))
            self._touch(ticket, now)
            self._finish_if_done(ticket.job_id, code, now)
        self.save()
        return retry_at

    def _finish_if_done(self, job_id: int, error: str | None, now: str) -> None:
        total, failed, pending = self._conn.execute(
            "SELECT COUNT(*), SUM(status = 'failed'), SUM(status = 'pending') FROM job_steps"
            " WHERE job_id = ?", (job_id,)).fetchone()
        if pending:
            return
        # A job where nothing could be checked must not read as "nothing found".
        all_failed = failed == total
        self._conn.execute("UPDATE jobs SET status = ?, completed_at = ? WHERE id = ?",
                           (JobStatus.FAILED if all_failed else JobStatus.COMPLETED, now, job_id))
        self._close_scan(job_id, ScanStatus.FAILED if all_failed else ScanStatus.COMPLETED,
                         (error or ErrorCode.UNAVAILABLE) if all_failed else None, now)
