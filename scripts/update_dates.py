#!/usr/bin/env python3
"""Sync report-card "Updated M/D/YYYY" pills with each report repo's last commit date.

For every card that has an "Updated ..." pill and links to a *.github.io page,
fetch the linked repo's latest commit (shallow, no API needed) and, if that
commit is NEWER than the date shown, replace the pill date. Dates only move
forward. Cards with Current / Live pills are left alone.

Usage: python3 scripts/update_dates.py [path/to/index.html]
Prints one line per changed card; prints "No changes" if nothing moved.
"""
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tempfile

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "index.html")
html = open(path, encoding="utf-8").read()

CARD = re.compile(r'<article class="report-card".*?</article>', re.S)
PILL = re.compile(r"Updated (\d{1,2})/(\d{1,2})/(\d{4})")
LINK = re.compile(r'href="https://([A-Za-z0-9-]+)\.github\.io/([^/"]+)')


def last_commit(owner, repo):
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "-C", d, "init", "-q"], check=True)
        r = subprocess.run(
            ["git", "-C", d, "fetch", "-q", "--depth", "1", f"https://github.com/{owner}/{repo}", "HEAD"],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0:
            return None, r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "fetch failed"
        out = subprocess.run(
            ["git", "-C", d, "log", "-1", "--format=%cd", "--date=format-local:%Y-%m-%d", "FETCH_HEAD"],
            capture_output=True, text=True, env={**os.environ, "TZ": "America/Chicago"},
        ).stdout.strip()
        return dt.date.fromisoformat(out), None
    finally:
        shutil.rmtree(d, ignore_errors=True)


changes, errors = [], []


def fix(m):
    card = m.group(0)
    pill, link = PILL.search(card), LINK.search(card)
    if not pill or not link:
        return card
    shown = dt.date(int(pill.group(3)), int(pill.group(1)), int(pill.group(2)))
    pushed, err = last_commit(*link.groups())
    title = re.search(r"<h3>(.*?)</h3>", card).group(1).replace("&amp;", "&")
    if err:
        errors.append(f"{title}: {err}")
        return card
    if pushed > shown:
        new = f"Updated {pushed.month}/{pushed.day}/{pushed.year}"
        changes.append(f"{title}: {shown.month}/{shown.day} -> {pushed.month}/{pushed.day}")
        return card[: pill.start()] + new + card[pill.end():]
    return card


html = CARD.sub(fix, html)
open(path, "w", encoding="utf-8").write(html)

print("\n".join(changes) if changes else "No changes")
for e in errors:
    print("ERROR", e)
