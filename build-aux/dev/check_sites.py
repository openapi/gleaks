"""Maintainer tool: check every entry of the profile index against the live sites.

A site stays useful only if a known name is found and a made-up one is not.
Sends one or two requests per site, using only public example names:

    python3 build-aux/dev/check_sites.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gleaks.providers.base import ProviderError, https_get  # noqa: E402
from gleaks.providers.profiles import SITES, TIMEOUT, USER_AGENT, Verdict  # noqa: E402

GHOST = "zzqxv-gleaks-8417"


def verdict(site, name) -> str:
    try:
        response = https_get(site.probe_url(name), {"user-agent": USER_AGENT, "accept": "*/*"}, TIMEOUT)
    except ProviderError:
        return "network error"
    return site.classify(response).value


def main() -> int:
    broken = 0
    for site in SITES:
        ghost = verdict(site, f"{GHOST}@example.invalid" if site.accepts == "email" else GHOST)
        time.sleep(0.5)
        known = verdict(site, site.example) if site.example else Verdict.FOUND.value
        ok = ghost == Verdict.ABSENT.value and known == Verdict.FOUND.value
        broken += not ok
        print(f"{'ok    ' if ok else 'BROKEN'} {site.id:16} made-up: {ghost:14} known: {known}")
        time.sleep(0.5)
    print(f"{len(SITES) - broken} of {len(SITES)} sites behave as the index expects")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
