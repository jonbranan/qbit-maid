#!/usr/bin/env python3
"""Render notification layouts as a phone-width PNG mockup.

Pushover renders the body in a proportional font, so space-padded columns do
not line up on a phone. These mockups use a proportional font on purpose so
the preview matches what the user actually sees.

By default the cards are rendered from the real ``build_summary()`` output, so
the preview is ground truth rather than a hand-written approximation. Pass
``--mock`` to render the built-in candidate sketches instead.

Usage: python3 docs/notify-preview.py [--mock] [out.png]
"""
import datetime
import html
import os
import subprocess
import sys
import tempfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STATS = {
    "total": 42,
    "removed": 7,
    "orphaned": 4,
    "ignored": 5,
    "premature": 3,
    "protected": 10,
    "non_protected": 20,
    "runtime": "12s",
}

EMOJI = {
    "removed": "\U0001F5D1\uFE0F",
    "orphaned": "\U0001F47B",
    "ignored": "\u23ED\uFE0F",
    "premature": "\U0001F423",
    "protected": "\U0001F6E1\uFE0F",
    "non_protected": "\U0001F310",
}


def b(text):
    return f"<b>{text}</b>"


# --- candidate layouts -----------------------------------------------------
# Each returns (title, body_html). Body uses Pushover's HTML subset.

def current_table(s):
    """Today's layout: space-padded columns."""
    rows = [
        ("Removed", s["removed"]),
        ("Orphaned", s["orphaned"]),
        ("Ignored", s["ignored"]),
        ("Premature", s["premature"]),
    ]
    tail = [("Protected", s["protected"]), ("Non-protected", s["non_protected"])]
    out = [f"Scanned {s['total']} torrents in {s['runtime']}", ""]
    out += [f"{b(lbl)}{' ' * max(14 - len(lbl), 1)}{val:>4}" for lbl, val in rows]
    out.append("")
    out += [f"{b(lbl)}{' ' * max(14 - len(lbl), 1)}{val:>4}" for lbl, val in tail]
    return "qbit-maid: 7 torrents removed", "\n".join(out)


def compact_inline(s):
    """One line per group, middle-dot separated."""
    out = [
        f"Scanned {s['total']} torrents in {s['runtime']}",
        "",
        f"{b('Removed')} {s['removed']}  \u00b7  {b('Orphaned')} {s['orphaned']}",
        f"{b('Ignored')} {s['ignored']}  \u00b7  {b('Premature')} {s['premature']}",
        "",
        f"{b('Protected')} {s['protected']}  \u00b7  {b('Non-protected')} {s['non_protected']}",
    ]
    return "qbit-maid: 7 torrents removed", "\n".join(out)


def emoji_rows(s):
    """Emoji-led rows, no padding."""
    out = [f"Scanned {s['total']} torrents in {s['runtime']}", ""]
    for key, label in (("removed", "Removed"), ("orphaned", "Orphaned"),
                       ("ignored", "Ignored"), ("premature", "Premature")):
        out.append(f"{EMOJI[key]} {b(label)} {s[key]}")
    out.append("")
    for key, label in (("protected", "Protected"), ("non_protected", "Non-protected")):
        out.append(f"{EMOJI[key]} {b(label)} {s[key]}")
    return "qbit-maid: 7 torrents removed", "\n".join(out)


def hero_line(s):
    """Actionable numbers up front, everything else compact below."""
    out = [
        f"{b(str(s['removed']))} removed  \u00b7  {b(str(s['orphaned']))} orphaned",
        f"{s['total']} torrents scanned in {s['runtime']}",
        "",
        f"Ignored {s['ignored']}  \u00b7  Premature {s['premature']}",
        f"Protected {s['protected']}  \u00b7  Non-protected {s['non_protected']}",
    ]
    return "qbit-maid: 7 torrents removed", "\n".join(out)


def emoji_inline(s):
    """Compact inline, emoji instead of bold labels."""
    out = [
        f"Scanned {s['total']} torrents in {s['runtime']}",
        "",
        f"{EMOJI['removed']} {s['removed']} removed  \u00b7  {EMOJI['orphaned']} {s['orphaned']} orphaned",
        f"{EMOJI['ignored']} {s['ignored']} ignored  \u00b7  {EMOJI['premature']} {s['premature']} premature",
        "",
        f"{EMOJI['protected']} {s['protected']} protected  \u00b7  {EMOJI['non_protected']} {s['non_protected']} public",
    ]
    return "qbit-maid: 7 torrents removed", "\n".join(out)


MOCK_CANDIDATES = [
    ("A \u2014 current (padded table)", current_table),
    ("B \u2014 compact inline", compact_inline),
    ("C \u2014 emoji rows", emoji_rows),
    ("D \u2014 hero line", hero_line),
    ("E \u2014 emoji inline", emoji_inline),
]


class Sample:
    """Minimal stand-in for the Qbt object, holding only what notifiers read."""

    def __init__(self, **overrides):
        self.config = {"pushover": {}}
        self.total_torrents = STATS["total"]
        self.torrent_hash_delete_list = ["a"] * STATS["removed"]
        self.up_tor_counter = STATS["orphaned"]
        self.ignored_counter = STATS["ignored"]
        self.preme_tor_counter = STATS["premature"]
        self.tracker_protected_tag = "ipt"
        self.tracker_non_protected_tag = "public"
        self.c = Counter({"ipt": STATS["protected"],
                          "public": STATS["non_protected"]})
        self.delete_torrents = True
        self.st = datetime.datetime(2026, 10, 27, 9, 54, 0)
        self.et = datetime.datetime(2026, 10, 27, 9, 54, 12)
        for key, value in overrides.items():
            setattr(self, key, value)


def real_candidates():
    """Render the actual build_summary() output for each supported style."""
    from qlogging import build_summary

    out = []
    for style in ("plain", "html"):
        for emoji in (False, True):
            title, body = build_summary(
                Sample(), style=style, use_emoji=emoji, include_hostname=False
            )
            label = f"{style}" + (" + emoji" if emoji else "")
            out.append((label, title, body))
    return out


def card(name, title, body):
    body_html = "<br>".join(body.split("\n"))
    return f"""
    <div class="card">
      <div class="app">PUSHOVER \u00b7 {html.escape(name)}</div>
      <div class="title">{html.escape(title)}</div>
      <div class="body">{body_html}</div>
    </div>
    """


def build_html(mock=False):
    if mock:
        cards = "\n".join(card(n, *fn(STATS)) for n, fn in MOCK_CANDIDATES)
    else:
        cards = "\n".join(card(n, t, b) for n, t, b in real_candidates())
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; padding:18px; background:#1b1d21;
          font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .card {{ background:#2b2f36; border-radius:14px; padding:14px 16px;
           box-shadow:0 2px 10px rgba(0,0,0,.45); }}
  .app {{ font-size:10px; letter-spacing:.14em; color:#8b929c; margin-bottom:6px; }}
  .title {{ font-size:15px; font-weight:600; color:#f2f4f7; margin-bottom:8px; }}
  .body {{ font-size:14px; line-height:1.45; color:#d7dbe0; white-space:normal; }}
  .body b {{ color:#ffffff; }}
</style></head><body><div class="grid">{cards}</div></body></html>
"""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mock = "--mock" in sys.argv[1:]
    out = args[0] if args else "/tmp/notify-preview.png"
    workdir = tempfile.mkdtemp(prefix="notify-preview-")
    page = os.path.join(workdir, "preview.html")
    with open(page, "w", encoding="utf-8") as fh:
        fh.write(build_html(mock=mock))
    subprocess.run([
        "docker", "run", "--rm", "-v", f"{workdir}:/w", "-w", "/w",
        "--entrypoint", "google-chrome", "dgtlmoon/sockpuppetbrowser:latest",
        "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
        "--hide-scrollbars", "--window-size=880,760",
        "--screenshot=/w/preview.png", "file:///w/preview.html",
    ], check=True, capture_output=True)
    subprocess.run(["cp", os.path.join(workdir, "preview.png"), out], check=True)
    print(out)


if __name__ == "__main__":
    main()
