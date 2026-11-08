"""Per-user application settings: only the list of recently opened profile paths."""

from __future__ import annotations

import json
import os
from pathlib import Path

_MAX_RECENT = 8


def _path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "gleaks" / "recent.json"


def recent_profiles() -> list[str]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, str) and os.path.exists(item)]


def _write(paths: list[str]) -> None:
    target = _path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(paths[:_MAX_RECENT]), encoding="utf-8")


def remember_profile(path: str) -> None:
    _write([path] + [item for item in recent_profiles() if item != path])


def forget_profile(path: str) -> None:
    _write([item for item in recent_profiles() if item != path])
