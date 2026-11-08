"""Domain types shared by the storage, scanning and interface layers.

GLeaks keeps three concepts apart: an *event* (a breach at a service), the
*evidence* linking one identifier to that event, and the *actions* the user can
take. A completed action never erases the evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from ..i18n import _


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class IdentifierType(StrEnum):
    EMAIL = "email"
    USERNAME = "username"
    TEXT = "text"


class ActionStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"


class ActionType(StrEnum):
    CHANGE_PASSWORD = "change_password"
    ENABLE_MFA = "enable_mfa"
    REVOKE_SESSIONS = "revoke_sessions"
    REVIEW_RECOVERY = "review_recovery"
    CHECK_SIGNINS = "check_signins"
    REQUEST_REMOVAL = "request_removal"
    REVIEW_PROFILE = "review_profile"


class EventKind(StrEnum):
    BREACH = "breach"
    WEB_MENTION = "web_mention"
    PROFILE_PAGE = "profile_page"


class ScanStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Verification(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FABRICATED = "fabricated"


class ErrorCode(StrEnum):
    """Why a check produced no answer. None of these means "no exposures"."""

    UNSUPPORTED_IDENTIFIER = "unsupported_identifier"
    MISSING_CREDENTIALS = "missing_credentials"
    INVALID_CREDENTIALS = "invalid_credentials"
    NOT_AUTHORIZED = "not_authorized"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"
    NETWORK = "network"
    INTERNAL = "internal"


def describe_error(code: str) -> str:
    return {
        ErrorCode.UNSUPPORTED_IDENTIFIER: _("This source cannot check this kind of identifier."),
        ErrorCode.MISSING_CREDENTIALS: _("No API key is configured for this source."),
        ErrorCode.INVALID_CREDENTIALS: _("The source rejected the API key."),
        ErrorCode.NOT_AUTHORIZED: _("Your plan does not allow this kind of search."),
        ErrorCode.RATE_LIMITED: _("The source's request limit was reached. Try again later."),
        ErrorCode.BLOCKED: _("The search engine asked for a human check. See Activity."),
        ErrorCode.UNAVAILABLE: _("The source is temporarily unavailable."),
        ErrorCode.INVALID_RESPONSE: _("The source sent a response GLeaks could not understand."),
        ErrorCode.NETWORK: _("The source could not be reached. Check your connection."),
    }.get(code, _("The check failed because of an internal error."))


_EMAIL_RE = re.compile(r"^[^@\s\x00-\x1f\x7f]+@[^@\s\x00-\x1f\x7f]+\.[^@\s\x00-\x1f\x7f.]+$")


def normalize_email(value: str) -> str:
    """Return the canonical form of an address, or raise ``ValueError``."""
    email = value.strip().lower()
    if len(email) > 254 or not _EMAIL_RE.match(email) or ".." in email.rpartition("@")[2]:
        raise ValueError(_("This is not a valid email address."))
    return email


_USERNAME_RE = re.compile(r"^[\w.-]{2,64}$")


def detect_identifier(value: str) -> tuple[IdentifierType, str]:
    """Classify free text as an email, a nickname or a phrase, and canonicalize it."""
    text = " ".join(value.split())
    if "@" in text[1:]:
        return IdentifierType.EMAIL, normalize_email(text)
    name = text.removeprefix("@").lower()
    if _USERNAME_RE.match(name):
        return IdentifierType.USERNAME, name
    if 2 <= len(text) <= 128 and text.isprintable():
        return IdentifierType.TEXT, text
    raise ValueError(_("Enter an email address, a nickname or a name."))


def describe_identifier_type(kind: str) -> str:
    return {
        IdentifierType.EMAIL: _("Email address"),
        IdentifierType.USERNAME: _("Nickname"),
        IdentifierType.TEXT: _("Name or phrase"),
    }.get(kind, kind)


@dataclass(frozen=True)
class NormalizedEvent:
    """A provider's answer, reduced to the fields GLeaks chooses to keep."""

    source: str
    source_event_id: str
    title: str
    domain: str | None = None
    description: str = ""
    event_date: str | None = None
    published_at: str | None = None
    data_classes: tuple[str, ...] = ()
    verification: Verification = Verification.VERIFIED
    flags: tuple[str, ...] = ()
    source_url: str | None = None
    kind: EventKind = EventKind.BREACH


@dataclass(frozen=True)
class Identifier:
    id: int
    type: str
    value: str
    label: str
    created_at: str
    enabled: bool


@dataclass(frozen=True)
class Action:
    id: int
    exposure_id: int
    type: ActionType
    status: ActionStatus
    created_at: str
    completed_at: str | None
    breach_title: str = ""
    identifier_value: str = ""


@dataclass(frozen=True)
class Exposure:
    id: int
    breach_id: int
    identifier_id: int
    identifier_value: str
    source: str
    title: str
    domain: str | None
    description: str
    event_date: str | None
    published_at: str | None
    data_classes: tuple[str, ...]
    verification: Verification
    flags: tuple[str, ...]
    source_url: str | None
    first_seen_at: str
    last_seen_at: str
    is_new: bool
    open_actions: int = 0
    actions: tuple[Action, ...] = field(default=())
    kind: EventKind = EventKind.BREACH


@dataclass(frozen=True)
class LogEntry:
    id: int
    at: str
    provider_id: str
    level: str
    message: str


@dataclass(frozen=True)
class Stats:
    identifiers: int
    events: int
    new_evidence: int
    open_actions: int


@dataclass(frozen=True)
class LastCheck:
    identifier_id: int
    identifier_value: str
    provider_id: str | None
    completed_at: str | None
    status: str | None
    error_code: str | None
    found: int


_PASSWORD_CLASSES = {"passwords", "password hints", "historical passwords"}
_RECOVERY_CLASSES = {"security questions and answers"}
_SESSION_CLASSES = {"auth tokens", "session tokens", "browser cookies"}


def recommended_actions(data_classes: tuple[str, ...],
                        kind: EventKind = EventKind.BREACH) -> tuple[ActionType, ...]:
    """Map exposed data to suggestions, without claiming an account is compromised."""
    if kind == EventKind.WEB_MENTION:
        return (ActionType.REQUEST_REMOVAL,)
    if kind == EventKind.PROFILE_PAGE:
        return (ActionType.REVIEW_PROFILE,)
    classes = {item.casefold() for item in data_classes}
    actions: list[ActionType] = []
    if classes & _PASSWORD_CLASSES:
        actions += [ActionType.CHANGE_PASSWORD, ActionType.ENABLE_MFA]
    if classes & _SESSION_CLASSES:
        actions.append(ActionType.REVOKE_SESSIONS)
    if classes & _RECOVERY_CLASSES:
        actions.append(ActionType.REVIEW_RECOVERY)
    actions.append(ActionType.CHECK_SIGNINS)
    return tuple(actions)


def describe_action(action: ActionType) -> str:
    return {
        ActionType.CHANGE_PASSWORD: _("Change the password if you still use it"),
        ActionType.ENABLE_MFA: _("Turn on two-factor authentication"),
        ActionType.REVOKE_SESSIONS: _("Sign out of active sessions"),
        ActionType.REVIEW_RECOVERY: _("Review the account's recovery options"),
        ActionType.CHECK_SIGNINS: _("Look for sign-ins you don't recognize"),
        ActionType.REQUEST_REMOVAL: _("Ask the site to remove this information"),
        ActionType.REVIEW_PROFILE: _("Check whether this profile is yours"),
    }[action]


def describe_status(status: ActionStatus) -> str:
    return {
        ActionStatus.OPEN: _("To do"),
        ActionStatus.IN_PROGRESS: _("In progress"),
        ActionStatus.COMPLETED: _("Done"),
        ActionStatus.DISMISSED: _("Dismissed"),
    }[status]
