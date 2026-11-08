"""A profile: an in-memory SQLite database persisted as one encrypted file.

The database never touches the disk in clear. There is no journal, WAL or
temporary file to protect, the profile stays a single portable file, and it
works on the Flatpak document portal, which exposes only the chosen file.

After opening, use a Profile from one thread only (the GTK main thread).
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path

from . import crypto
from .migrations import APPLICATION_ID, SCHEMA_VERSION, migrate, schema_version
from .models import (
    Action,
    ActionStatus,
    ActionType,
    Exposure,
    Identifier,
    IdentifierType,
    LastCheck,
    NormalizedEvent,
    ScanStatus,
    Stats,
    Verification,
    normalize_email,
    recommended_actions,
    utcnow,
)
from .scanning import ScanOutcome

MAX_PROFILE_BYTES = 256 * 1024 * 1024


class DamagedProfileError(Exception):
    """The file decrypted, but does not hold a usable profile."""


class DuplicateIdentifierError(ValueError):
    pass


def _connect() -> sqlite3.Connection:
    # Opened in a worker thread (key derivation is slow), then used on the main one.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _configure(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA foreign_keys = ON")


class Profile:
    def __init__(self, path: Path, conn: sqlite3.Connection, key: bytes, salt: bytes,
                 params: crypto.KdfParams):
        self.path = path
        self._conn = conn
        self._key = key
        self._salt = salt
        self._params = params
        self.dirty = False

    # -- lifecycle -----------------------------------------------------------
    @classmethod
    def create(cls, path: str | Path, password: str, name: str,
               params: crypto.KdfParams | None = None) -> "Profile":
        params = params or crypto.KdfParams()
        salt = crypto.new_salt()
        key = crypto.derive_key(password, salt, params)
        conn = _connect()
        _configure(conn)
        conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        migrate(conn)
        with conn:
            conn.executemany("INSERT INTO profile_meta (key, value) VALUES (?, ?)",
                             [("name", name), ("created_at", utcnow())])
        profile = cls(Path(path), conn, key, salt, params)
        profile.save()
        return profile

    @classmethod
    def open(cls, path: str | Path, password: str) -> "Profile":
        path = Path(path)
        if path.stat().st_size > MAX_PROFILE_BYTES:
            raise crypto.ContainerError("profile too large")
        blob = path.read_bytes()
        params, salt = crypto.read_header(blob)
        key = crypto.derive_key(password, salt, params)
        plaintext = crypto.open_sealed(key, blob)
        conn = _connect()
        try:
            conn.deserialize(plaintext)
            _configure(conn)
            if (conn.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                    or conn.execute("PRAGMA quick_check").fetchone()[0] != "ok"):
                raise DamagedProfileError
            needs_migration = schema_version(conn) < SCHEMA_VERSION
            if needs_migration:
                try:
                    shutil.copyfile(path, path.with_name(path.name + ".bak"))
                except OSError:
                    pass  # The document portal only exposes the chosen file.
            migrate(conn)
        except sqlite3.DatabaseError as exc:
            conn.close()
            raise DamagedProfileError from exc
        except Exception:
            conn.close()
            raise
        profile = cls(path, conn, key, salt, params)
        if needs_migration:
            profile.save()
        return profile

    def save(self) -> None:
        """Replace the file atomically; only ciphertext is ever written."""
        self.dirty = True
        blob = crypto.seal(self._key, self._salt, self._params, self._conn.serialize())
        tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(blob)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        self.dirty = False

    def close(self) -> None:
        """Flush anything a failed save left behind, then release the database."""
        if self.dirty:
            self.save()
        self._conn.close()

    def prepare_password(self, password: str) -> tuple[bytes, bytes]:
        """Derive a new key. Slow, and the only method safe to call off the main thread."""
        salt = crypto.new_salt()
        return crypto.derive_key(password, salt, self._params), salt

    def change_password(self, password: str) -> None:
        self.apply_password(self.prepare_password(password))

    def apply_password(self, prepared: tuple[bytes, bytes]) -> None:
        old = (self._key, self._salt)
        self._key, self._salt = prepared
        try:
            self.save()
        except OSError:
            self._key, self._salt = old
            self.dirty = False
            raise

    @property
    def name(self) -> str:
        row = self._conn.execute("SELECT value FROM profile_meta WHERE key = 'name'").fetchone()
        return row[0] if row else self.path.stem

    # -- identifiers ---------------------------------------------------------
    def add_email(self, value: str, label: str = "") -> Identifier:
        email = normalize_email(value)
        try:
            with self._conn:
                cursor = self._conn.execute(
                    "INSERT INTO identifiers (type, value, label, created_at) VALUES (?, ?, ?, ?)",
                    (IdentifierType.EMAIL, email, label, utcnow()))
        except sqlite3.IntegrityError as exc:
            raise DuplicateIdentifierError(email) from exc
        self.save()
        return self.identifier(cursor.lastrowid)

    @staticmethod
    def _to_identifier(row: sqlite3.Row) -> Identifier:
        return Identifier(row["id"], row["type"], row["value"], row["label"], row["created_at"],
                          bool(row["enabled"]))

    def identifier(self, identifier_id: int) -> Identifier:
        row = self._conn.execute("SELECT * FROM identifiers WHERE id = ?",
                                 (identifier_id,)).fetchone()
        return self._to_identifier(row)

    def identifiers(self, enabled_only: bool = False) -> list[Identifier]:
        where = "WHERE enabled = 1" if enabled_only else ""
        rows = self._conn.execute(f"SELECT * FROM identifiers {where} ORDER BY value")
        return [self._to_identifier(row) for row in rows]

    def set_identifier_enabled(self, identifier_id: int, enabled: bool) -> None:
        with self._conn:
            self._conn.execute("UPDATE identifiers SET enabled = ? WHERE id = ?",
                               (int(enabled), identifier_id))
        self.save()

    def remove_identifier(self, identifier_id: int) -> None:
        """Delete an identifier, its evidence, and any event no longer referenced."""
        with self._conn:
            self._conn.execute("DELETE FROM identifiers WHERE id = ?", (identifier_id,))
            self._conn.execute(
                "DELETE FROM breaches WHERE id NOT IN (SELECT breach_id FROM exposures)")
        self.save()

    # -- provider settings ---------------------------------------------------
    def provider_mode(self, provider_id: str, default: str) -> str:
        row = self._conn.execute("SELECT mode FROM providers WHERE id = ?",
                                 (provider_id,)).fetchone()
        return row[0] if row else default

    def set_provider_mode(self, provider_id: str, mode: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO providers (id, mode) VALUES (?, ?) "
                "ON CONFLICT (id) DO UPDATE SET mode = excluded.mode", (provider_id, mode))
        self.save()

    # -- scans ---------------------------------------------------------------
    def record_outcome(self, outcome: ScanOutcome) -> int:
        """Store one check and return how many exposures are new.

        A failed or cancelled check is logged but leaves the evidence untouched:
        an error is never read as "no exposures".
        """
        events = outcome.events if outcome.status == ScanStatus.COMPLETED else ()
        new_exposures = 0
        with self._conn:
            scan_id = self._conn.execute(
                "INSERT INTO scans (provider_id, identifier_id, mode, started_at, completed_at,"
                " status, error_code, found) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (outcome.provider_id, outcome.identifier_id, outcome.mode, outcome.started_at,
                 outcome.completed_at, outcome.status, outcome.error_code, len(events))).lastrowid
            for event in events:
                new_exposures += self._store_evidence(scan_id, outcome, event)
        self.save()
        return new_exposures

    def _store_evidence(self, scan_id: int, outcome: ScanOutcome, event: NormalizedEvent) -> int:
        now = outcome.completed_at
        breach_id = self._conn.execute(
            "INSERT INTO breaches (source, source_event_id, title, domain, description,"
            " event_date, published_at, data_classes, verification, flags, source_url)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (source, source_event_id) DO UPDATE SET"
            " title = excluded.title, domain = excluded.domain,"
            " description = excluded.description, event_date = excluded.event_date,"
            " published_at = excluded.published_at, data_classes = excluded.data_classes,"
            " verification = excluded.verification, flags = excluded.flags,"
            " source_url = excluded.source_url RETURNING id",
            (event.source, event.source_event_id, event.title, event.domain, event.description,
             event.event_date, event.published_at, json.dumps(list(event.data_classes)),
             event.verification, json.dumps(list(event.flags)), event.source_url),
        ).fetchone()[0]
        row = self._conn.execute(
            "SELECT id FROM exposures WHERE identifier_id = ? AND breach_id = ?",
            (outcome.identifier_id, breach_id)).fetchone()
        is_new = row is None
        if is_new:
            exposure_id = self._conn.execute(
                "INSERT INTO exposures (identifier_id, breach_id, first_seen_at, last_seen_at)"
                " VALUES (?, ?, ?, ?)", (outcome.identifier_id, breach_id, now, now)).lastrowid
        else:
            exposure_id = row[0]
            self._conn.execute("UPDATE exposures SET last_seen_at = ? WHERE id = ?",
                               (now, exposure_id))
        self._conn.execute(
            "INSERT INTO provider_observations (exposure_id, scan_id, provider_id, observed_at)"
            " VALUES (?, ?, ?, ?)", (exposure_id, scan_id, outcome.provider_id, now))
        self._conn.executemany(
            "INSERT OR IGNORE INTO actions (exposure_id, type, created_at) VALUES (?, ?, ?)",
            [(exposure_id, action, now) for action in recommended_actions(event.data_classes)])
        return int(is_new)

    def last_checks(self) -> list[LastCheck]:
        rows = self._conn.execute(
            "SELECT i.id, i.value, s.provider_id, s.completed_at, s.status, s.error_code, s.found"
            " FROM identifiers i LEFT JOIN scans s ON s.id ="
            " (SELECT MAX(id) FROM scans WHERE identifier_id = i.id) ORDER BY i.value")
        return [LastCheck(r[0], r[1], r[2], r[3], r[4], r[5], r[6] or 0) for r in rows]

    # -- evidence ------------------------------------------------------------
    def stats(self) -> Stats:
        one = lambda sql: self._conn.execute(sql).fetchone()[0]  # noqa: E731
        return Stats(
            identifiers=one("SELECT COUNT(*) FROM identifiers"),
            events=one("SELECT COUNT(*) FROM breaches"),
            new_evidence=one("SELECT COUNT(*) FROM exposures WHERE reviewed_at IS NULL"),
            open_actions=one("SELECT COUNT(*) FROM actions WHERE status IN"
                             " ('OPEN', 'IN_PROGRESS')"),
        )

    _EXPOSURE_SELECT = (
        "SELECT e.id, e.breach_id, e.identifier_id, i.value AS identifier_value, b.source,"
        " b.title, b.domain, b.description, b.event_date, b.published_at, b.data_classes,"
        " b.verification, b.flags, b.source_url, e.first_seen_at, e.last_seen_at, e.reviewed_at,"
        " (SELECT COUNT(*) FROM actions a WHERE a.exposure_id = e.id"
        "  AND a.status IN ('OPEN', 'IN_PROGRESS')) AS open_actions"
        " FROM exposures e JOIN breaches b ON b.id = e.breach_id"
        " JOIN identifiers i ON i.id = e.identifier_id"
    )

    @staticmethod
    def _to_exposure(row: sqlite3.Row, actions: tuple[Action, ...] = ()) -> Exposure:
        return Exposure(
            id=row["id"], breach_id=row["breach_id"], identifier_id=row["identifier_id"],
            identifier_value=row["identifier_value"], source=row["source"], title=row["title"],
            domain=row["domain"], description=row["description"], event_date=row["event_date"],
            published_at=row["published_at"], data_classes=tuple(json.loads(row["data_classes"])),
            verification=Verification(row["verification"]), flags=tuple(json.loads(row["flags"])),
            source_url=row["source_url"], first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"], is_new=row["reviewed_at"] is None,
            open_actions=row["open_actions"], actions=actions)

    def exposures(self, identifier_id: int | None = None, query: str = "") -> list[Exposure]:
        clauses, params = [], []
        if identifier_id is not None:
            clauses.append("e.identifier_id = ?")
            params.append(identifier_id)
        if query:
            clauses.append("(b.title LIKE ? ESCAPE '\\' OR b.domain LIKE ? ESCAPE '\\')")
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params += [f"%{escaped}%"] * 2
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (self._EXPOSURE_SELECT + where
               + " ORDER BY e.reviewed_at IS NOT NULL, b.event_date DESC, b.title")
        return [self._to_exposure(row) for row in self._conn.execute(sql, params)]

    def exposure(self, exposure_id: int) -> Exposure:
        row = self._conn.execute(self._EXPOSURE_SELECT + " WHERE e.id = ?",
                                 (exposure_id,)).fetchone()
        return self._to_exposure(row, tuple(self.actions(exposure_id=exposure_id)))

    def identifiers_for_breach(self, breach_id: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT i.value FROM exposures e JOIN identifiers i ON i.id = e.identifier_id"
            " WHERE e.breach_id = ? ORDER BY i.value", (breach_id,))
        return [row[0] for row in rows]

    def mark_reviewed(self, exposure_id: int) -> None:
        with self._conn:
            changed = self._conn.execute(
                "UPDATE exposures SET reviewed_at = ? WHERE id = ? AND reviewed_at IS NULL",
                (utcnow(), exposure_id)).rowcount
        if changed:
            self.save()

    # -- actions -------------------------------------------------------------
    def actions(self, exposure_id: int | None = None,
                statuses: tuple[ActionStatus, ...] | None = None) -> list[Action]:
        clauses, params = [], []
        if exposure_id is not None:
            clauses.append("a.exposure_id = ?")
            params.append(exposure_id)
        if statuses:
            clauses.append(f"a.status IN ({', '.join('?' * len(statuses))})")
            params += list(statuses)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            "SELECT a.*, b.title AS breach_title, i.value AS identifier_value FROM actions a"
            " JOIN exposures e ON e.id = a.exposure_id JOIN breaches b ON b.id = e.breach_id"
            " JOIN identifiers i ON i.id = e.identifier_id"
            + where + " ORDER BY b.title, i.value, a.id", params)
        return [Action(r["id"], r["exposure_id"], ActionType(r["type"]), ActionStatus(r["status"]),
                       r["created_at"], r["completed_at"], r["breach_title"], r["identifier_value"])
                for r in rows]

    def set_action_status(self, action_id: int, status: ActionStatus) -> None:
        completed = utcnow() if status == ActionStatus.COMPLETED else None
        with self._conn:
            self._conn.execute("UPDATE actions SET status = ?, completed_at = ? WHERE id = ?",
                               (status, completed, action_id))
        self.save()
