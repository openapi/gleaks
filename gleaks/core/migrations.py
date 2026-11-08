"""Versioned schema of the profile database, tracked in ``PRAGMA user_version``."""

from __future__ import annotations

import sqlite3

APPLICATION_ID = 0x474C4B53  # "GLKS"

MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE profile_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

    CREATE TABLE identifiers (
        id INTEGER PRIMARY KEY,
        type TEXT NOT NULL,
        value TEXT NOT NULL,
        label TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        UNIQUE (type, value)
    );

    CREATE TABLE providers (
        id TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 1,
        mode TEXT NOT NULL
    );

    CREATE TABLE scans (
        id INTEGER PRIMARY KEY,
        provider_id TEXT NOT NULL,
        identifier_id INTEGER NOT NULL REFERENCES identifiers(id) ON DELETE CASCADE,
        mode TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        status TEXT NOT NULL,
        error_code TEXT,
        found INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX idx_scans_identifier ON scans(identifier_id, id);

    CREATE TABLE breaches (
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        source_event_id TEXT NOT NULL,
        title TEXT NOT NULL,
        domain TEXT,
        description TEXT NOT NULL DEFAULT '',
        event_date TEXT,
        published_at TEXT,
        data_classes TEXT NOT NULL DEFAULT '[]',
        verification TEXT NOT NULL,
        flags TEXT NOT NULL DEFAULT '[]',
        source_url TEXT,
        UNIQUE (source, source_event_id)
    );

    CREATE TABLE exposures (
        id INTEGER PRIMARY KEY,
        identifier_id INTEGER NOT NULL REFERENCES identifiers(id) ON DELETE CASCADE,
        breach_id INTEGER NOT NULL REFERENCES breaches(id) ON DELETE CASCADE,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        reviewed_at TEXT,
        UNIQUE (identifier_id, breach_id)
    );
    CREATE INDEX idx_exposures_breach ON exposures(breach_id);

    CREATE TABLE actions (
        id INTEGER PRIMARY KEY,
        exposure_id INTEGER NOT NULL REFERENCES exposures(id) ON DELETE CASCADE,
        type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        created_at TEXT NOT NULL,
        completed_at TEXT,
        UNIQUE (exposure_id, type)
    );
    CREATE INDEX idx_actions_status ON actions(status);

    CREATE TABLE provider_observations (
        id INTEGER PRIMARY KEY,
        exposure_id INTEGER NOT NULL REFERENCES exposures(id) ON DELETE CASCADE,
        scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
        provider_id TEXT NOT NULL,
        observed_at TEXT NOT NULL
    );
    CREATE INDEX idx_observations_exposure ON provider_observations(exposure_id);
    """,
    """
    ALTER TABLE breaches ADD COLUMN kind TEXT NOT NULL DEFAULT 'breach';

    CREATE TABLE search_log (
        id INTEGER PRIMARY KEY,
        at TEXT NOT NULL,
        provider_id TEXT NOT NULL,
        level TEXT NOT NULL,
        message TEXT NOT NULL
    );
    CREATE INDEX idx_search_log_provider ON search_log(provider_id, id);
    """,
    """
    CREATE TABLE jobs (
        id INTEGER PRIMARY KEY,
        provider_id TEXT NOT NULL,
        mode TEXT NOT NULL,
        identifier_id INTEGER NOT NULL REFERENCES identifiers(id) ON DELETE CASCADE,
        scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        background INTEGER NOT NULL DEFAULT 0,
        found INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        last_step_at TEXT,
        completed_at TEXT
    );
    CREATE INDEX idx_jobs_status ON jobs(status);

    CREATE TABLE job_steps (
        id INTEGER PRIMARY KEY,
        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        step TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        not_before TEXT,
        error_code TEXT,
        completed_at TEXT,
        UNIQUE (job_id, step)
    );
    CREATE INDEX idx_job_steps_pending ON job_steps(status, job_id);
    """,
)

SCHEMA_VERSION = len(MIGRATIONS)


class NewerSchemaError(Exception):
    """The profile was written by a newer version of GLeaks."""


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> None:
    """Bring ``conn`` up to date, one transaction per step."""
    current = schema_version(conn)
    if current > SCHEMA_VERSION:
        raise NewerSchemaError
    for version in range(current, SCHEMA_VERSION):
        # executescript() would commit first, so run the step inside BEGIN/COMMIT.
        script = f"BEGIN;\n{MIGRATIONS[version]}\nPRAGMA user_version = {version + 1};\nCOMMIT;"
        try:
            conn.executescript(script)
        except sqlite3.Error:
            if conn.in_transaction:
                conn.rollback()
            raise
