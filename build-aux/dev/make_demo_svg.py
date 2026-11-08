"""Generate docs/gleaks-demo.svg: an animated (SMIL) walkthrough of GLeaks.

What is shown comes from the real code: the connectors parse canned responses,
the scan engine runs, and the log lines, events and actions are read back from
an encrypted profile. Only the HTTP responses are simulated, so no real address
or search is involved. Regenerate with:

    python3 build-aux/dev/make_demo_svg.py [output.svg]

Set FRAME=<seconds> for a static frame, to check the layout.
"""
from __future__ import annotations

import html
import json
import os
import sys
import tempfile
import textwrap
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gleaks.core import crypto  # noqa: E402
from gleaks.core.models import describe_action, describe_status, detect_identifier  # noqa: E402
from gleaks.core.profile import Profile  # noqa: E402
from gleaks.core.scanning import ScanRequest, run_scan  # noqa: E402
from gleaks.providers import PROVIDERS  # noqa: E402
from gleaks.providers.base import CheckContext, HttpResponse  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "gleaks-demo.svg"
FRAME = float(os.environ["FRAME"]) if os.environ.get("FRAME") else None
EMAIL = "mario.rossi@example.com"
NICKNAME = "mario-rossi-demo"
FOUND_HOSTS = {"github.com", "gitlab.com", "codeberg.org"}
T = 22.0  # loop length in seconds
W, H = 880, 560

# Adwaita dark.
WINDOW, HEADER, CARD, DIALOG = "#242424", "#303030", "#383838", "#383838"
TEXT, DIM, ACCENT, GREEN, ORANGE, BORDER = "#ffffff", "#a0a0a0", "#3584e4", "#8ff0a4", "#ffa348", "#1c1c1c"
FONT = "Cantarell, 'Noto Sans', 'Ubuntu', 'DejaVu Sans', sans-serif"
MONO = "'Ubuntu Mono', 'DejaVu Sans Mono', monospace"

# -- run the real engine on canned responses --------------------------------
BREACHES = [
    {"Name": "Adobe", "Title": "Adobe", "Domain": "adobe.com", "BreachDate": "2013-10-04",
     "AddedDate": "2013-12-04T00:00:00Z", "DataClasses": ["Email addresses", "Password hints", "Passwords", "Usernames"],
     "Description": "In October 2013, 153 million Adobe accounts were breached, each containing "
                    "an internal ID, username, email and encrypted password.", "IsVerified": True},
    {"Name": "Stratfor", "Title": "Stratfor", "Domain": "stratfor.com", "BreachDate": "2011-12-24",
     "AddedDate": "2013-12-04T00:00:00Z", "DataClasses": ["Email addresses", "Names", "Passwords"],
     "Description": "In December 2011, Stratfor was breached.", "IsVerified": True},
]


def result(url: str, title: str, snippet: str) -> str:
    href = f"//duckduckgo.com/l/?uddg={quote(url, safe='')}"
    return (f'<a class="result__a" href="{href}">{title}</a>'
            f'<a class="result__snippet" href="{href}">{snippet}</a>')


SEARCH_PAGE = '<div id="links" class="results">' + "".join([
    result("https://forum.example.org/members/mrossi", "Member list - Example Forum",
           f"Contact: {EMAIL} joined in 2014"),
    result("https://example.net/a", "An unrelated page", "no address here"),
    result("https://example.net/b", "Another unrelated page", "no address here"),
]) + "</div>"


def fake_http(url, _headers, _timeout):
    if "duckduckgo" in url:
        return HttpResponse(200, {}, SEARCH_PAGE.encode())
    if "marginalia" in url:
        return HttpResponse(200, {}, b'{"results": []}')
    if "haveibeenpwned" not in url:
        found = any(host in url for host in FOUND_HOSTS) and NICKNAME in url
        absent = 400 if "bsky" in url else 404
        return HttpResponse(200 if found else absent, {}, b'[{"id":1}]' if found else b"")
    return HttpResponse(200, {}, json.dumps(BREACHES).encode())


def collect():
    lines = {}
    with tempfile.TemporaryDirectory() as folder:
        profile = Profile.create(Path(folder) / "demo.gleaks", "demo-password", "Personal",
                                 params=crypto.KdfParams(log2n=10))
        added = [profile.add_identifier(value) for value in (EMAIL, NICKNAME)]
        for provider_id, provider in PROVIDERS.items():
            collected = lines.setdefault(provider_id, [])
            info = provider.info
            ctx = CheckContext(mode=info.modes[0].id, api_key="demo", http=fake_http,
                               log=lambda m, level="info", c=collected: c.append((level, m)))
            ctx.cancel.wait = lambda timeout=None: False  # No need to pace canned responses.
            requests = [ScanRequest(i.id, i.value, i.type) for i in added
                        if detect_identifier(i.value)[0] in info.supported_identifiers]
            # One identifier each keeps the preview readable.
            if provider_id == "web":
                requests = requests[:1]
            elif provider_id == "index":
                requests = requests[-1:]
            run_scan(provider, requests, ctx, profile.record_outcome)
        exposures = profile.exposures()
        adobe = profile.exposure(next(e.id for e in exposures if e.title == "Adobe"))
        stats = profile.stats()
        profile.close()
    return lines, exposures, adobe, stats


LINES, EXPOSURES, ADOBE, STATS = collect()


# -- drawing -----------------------------------------------------------------
def esc(value: str) -> str:
    return html.escape(value, quote=True)


def short(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


def text(x, y, value, size=13, fill=TEXT, weight=400, anchor="start", family=FONT):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>')


def rect(x, y, w, h, fill, r=10, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" {extra}/>'


def visibility(windows: list[tuple[float, float]]) -> str:
    """SMIL for an element visible during the given (start, end) windows."""
    if FRAME is not None:
        return ""
    fade = 0.3
    points = [(0.0, 0.0)]
    for start, end in windows:
        points += [(start, 0.0), (min(start + fade, end), 1.0), (max(end - fade, start), 1.0), (end, 0.0)]
    points.append((T, 0.0))
    points = sorted(set(points))
    times = ";".join(f"{t / T:.4f}" for t, _ in points)
    values = ";".join(f"{v:g}" for _, v in points)
    return (f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" '
            f'keyTimes="{times}" values="{values}"/>')


def group(windows: list[tuple[float, float]], *content: str) -> str:
    if FRAME is not None:
        shown = any(start <= FRAME < end for start, end in windows)
        return f'<g opacity="{1 if shown else 0}">{"".join(content)}</g>'
    return f'<g opacity="0">{visibility(windows)}{"".join(content)}</g>'


TABS = ["Overview", "Identifiers", "Exposures", "Actions", "Activity"]
CONSENT, ACTIVITY, LIST, DETAIL = (0.0, 5.0), (5.0, 13.0), (13.0, 17.5), (17.5, T)


def chrome() -> str:
    parts = [rect(0.5, 0.5, W - 1, H - 1, WINDOW, 14, f'stroke="{BORDER}"'),
             f'<path d="M1 14 a13 13 0 0 1 13 -13 H{W - 14} a13 13 0 0 1 13 13 V47 H1 Z" fill="{HEADER}"/>',
             rect(10, 9, 58, 30, ACCENT, 8), text(39, 29, "Scan", 13, TEXT, 700, "middle")]
    x, width = 205, 94
    active = {"Overview": [CONSENT], "Exposures": [LIST, DETAIL], "Activity": [ACTIVITY]}
    for index, tab in enumerate(TABS):
        tab_x = x + index * width
        if tab in active:
            parts.append(group(active[tab], rect(tab_x, 9, width - 6, 30, "#4a4a4a", 8)))
        parts.append(text(tab_x + (width - 6) / 2, 29, tab, 13, TEXT, 600, "middle"))
    for offset, glyph in ((W - 72, "–"), (W - 46, "□"), (W - 20, "×")):
        parts.append(f'<circle cx="{offset}" cy="24" r="11" fill="#444"/>')
        parts.append(text(offset, 29, glyph, 13, TEXT, 700, "middle"))
    return "".join(parts)


def overview() -> str:
    labels = (("Identifiers", 2), ("Known events", STATS.events),
              ("New evidence", STATS.new_evidence), ("Open actions", STATS.open_actions))
    parts = []
    for index, (label, _value) in enumerate(labels):
        x = 100 + index * 174
        parts += [rect(x, 72, 160, 92, CARD), text(x + 80, 118, "0" if index else "2", 30, TEXT, 700, "middle"),
                  text(x + 80, 146, label, 13, DIM, 400, "middle")]
    return "".join(parts)


def consent() -> str:
    x, y, w, h = 170, 58, 540, 486
    info = {pid: p.info for pid, p in PROVIDERS.items()}
    parts = [rect(0, 48, W, H - 48, "#000000", 0, 'opacity=".45"'), rect(x, y, w, h, DIALOG, 14),
             text(x + w / 2, y + 42, "Check These Identifiers?", 20, TEXT, 700, "middle"),
             text(x + w / 2, y + 74, "Only check identifiers that belong to you.", 13, TEXT, 400, "middle"),
             text(x + w / 2, y + 100, f"{EMAIL}   ·   {NICKNAME}", 13, TEXT, 700, "middle")]
    line = y + 134
    for provider_id, source in info.items():
        provider = PROVIDERS[provider_id].info
        parts.append(text(x + w / 2, line, f"{source.name} ({source.destination})", 13, TEXT, 700, "middle"))
        parts.append(text(x + w / 2, line + 20, short(f"Sent: {provider.modes[0].transmits}.", 76), 13, TEXT, 400, "middle"))
        parts.append(text(x + w / 2, line + 40, short(f"Returned: {provider.returns}", 76), 13, DIM, 400, "middle"))
        line += 78
    parts += [f'<path d="M{x} {y + h - 54} H{x + w} M{x + w / 2} {y + h - 54} V{y + h}" stroke="#555"/>',
              text(x + w / 4, y + h - 21, "Cancel", 14, TEXT, 700, "middle"),
              text(x + 3 * w / 4, y + h - 21, "Send and Check", 14, "#78aeed", 700, "middle")]
    return "".join(parts)


def activity() -> str:
    parts = [text(40, 80, "Each source runs on its own. This log stays inside your encrypted profile.", 12, DIM)]
    start, end = ACTIVITY
    columns = (("index", 28, 0.2), ("web", 310, 1.2), ("hibp", 592, 0.6))
    for provider_id, x, delay in columns:
        # The app logs every site; the preview keeps the ones that found something.
        lines = [line for line in LINES[provider_id] if not line[1].endswith(": no page")]
        width = 260
        step = (end - start - 3.0 - delay) / len(lines)
        finished = start + delay + step * len(lines)
        parts.append(text(x, 112, PROVIDERS[provider_id].info.name, 15, TEXT, 700))
        parts.append(group([(start, finished)], text(x + width, 112, "Running…", 13, ORANGE, 400, "end")))
        parts.append(group([(finished, end)], text(x + width, 112, "Finished", 13, GREEN, 400, "end")))
        wrapped = [(index, part) for index, (_level, message) in enumerate(lines)
                   for part in [textwrap.wrap(f"10:32:{index * 3 + (0 if x == 28 else 1):02d} {message}", 34)]]
        rows = sum(len(part) for _, part in wrapped)
        parts.append(rect(x, 126, width, 24 + rows * 18, CARD))
        y = 148
        for index, part in reversed(wrapped):
            appear = start + delay + step * index
            parts.append(group([(appear, end)], *[
                text(x + 12, y + number * 18, row, 12, TEXT, 400, "start", MONO)
                for number, row in enumerate(part)]))
            y += 18 * len(part)
    return "".join(parts)


def exposures() -> str:
    parts = [rect(100, 68, 500, 34, CARD, 8), text(134, 90, "Search events", 13, DIM),
             rect(612, 68, 168, 34, CARD, 8), text(696, 90, "All identifiers", 13, TEXT, 600, "middle")]
    y = 118
    parts.append(rect(100, y, 680, 58 * len(EXPOSURES), CARD))
    for exposure in EXPOSURES:
        detail = {"web_mention": "Public web page", "profile_page": "Page with this name"}.get(
            exposure.kind, exposure.event_date)
        parts += [text(116, y + 26, short(exposure.title, 60), 14, TEXT, 500),
                  text(116, y + 45, f"{exposure.identifier_value} · {detail}", 12, DIM),
                  text(738, y + 34, "New", 12, "#78aeed", 700, "end"), text(760, y + 35, "›", 18, DIM, 400, "end")]
        y += 58
    return "".join(parts)


def detail() -> str:
    x, y, w, h = 170, 62, 540, 470
    parts = [rect(0, 48, W, H - 48, "#000000", 0, 'opacity=".45"'), rect(x, y, w, h, DIALOG, 14),
             text(x + w / 2, y + 30, ADOBE.title, 15, TEXT, 700, "middle"),
             text(x + 22, y + 66, "Details", 14, TEXT, 700)]
    rows = [("Service", ADOBE.domain), ("Date of the event", ADOBE.event_date),
            ("Data involved", ", ".join(ADOBE.data_classes)),
            ("Source", PROVIDERS["hibp"].info.attribution)]
    row_y = y + 78
    parts.append(rect(x + 22, row_y, w - 44, 48 * len(rows), "#454545"))
    for label, value in rows:
        parts += [text(x + 36, row_y + 19, label, 11, DIM), text(x + 36, row_y + 38, short(value, 66), 13.5, TEXT)]
        row_y += 48
    parts.append(text(x + 22, row_y + 34, "Suggested actions", 14, TEXT, 700))
    row_y += 46
    actions = ADOBE.actions[:3]
    parts.append(rect(x + 22, row_y, w - 44, 42 * len(actions), "#454545"))
    for index, action in enumerate(actions):
        parts += [text(x + 36, row_y + 26, describe_action(action.type), 13.5, TEXT)]
        parts.append(rect(x + w - 118, row_y + 7, 84, 28, "#555555", 6))
        parts.append(text(x + w - 76, row_y + 26, describe_status(action.status), 12, TEXT, 600, "middle"))
        row_y += 42
    return "".join(parts)


def build() -> str:
    return "".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">',
        "<title>GLeaks: consent, independent searches with a live log, results and actions</title>",
        chrome(),
        group([CONSENT], overview(), consent()),
        group([ACTIVITY], activity()),
        group([LIST, DETAIL], exposures()),
        group([DETAIL], detail()),
        "</svg>",
    ])


OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(build(), encoding="utf-8")
print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
