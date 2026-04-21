#!/usr/bin/env python3
"""
changelog.py — generate or update CHANGELOG.md from git log.

Usage:
    python skills/changelog/scripts/changelog.py

Behaviour:
  - No CHANGELOG.md  → reads full git log, creates the file.
  - CHANGELOG.md exists → finds the most recent date in the file,
    appends only commits strictly newer than that date (no duplicates).
"""
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")

_HEADER_RE = re.compile(r"^#\s+changelog", re.IGNORECASE)


def git_log(after_date: str | None = None) -> list[tuple[str, str]]:
    """Return [(date, subject), ...] newest-first.

    after_date must be YYYY-MM-DD. Commits ON that date are excluded by
    appending ' 23:59:59' — git --after is inclusive of the given timestamp.
    """
    cmd = ["git", "log", "--format=%ad\t%s", "--date=short"]
    if after_date:
        # Exclude commits from the latest recorded day to avoid duplicates
        # when the script is run twice on the same day with new commits.
        cmd += [f"--after={after_date} 23:59:59"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if "\t" not in line:
            continue
        day, subject = line.split("\t", 1)
        subject = subject.strip()
        if subject:
            entries.append((day, subject))
    return entries


def latest_date_in_changelog() -> str | None:
    """Return the most recent ## YYYY-MM-DD date found in the file, or None."""
    if not CHANGELOG.exists():
        return None
    pattern = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
    for line in CHANGELOG.read_text().splitlines():
        m = pattern.match(line)
        if m:
            return m.group(1)
    return None


def group_by_date(entries: list[tuple[str, str]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for day, subject in entries:
        grouped[day].append(subject)
    return grouped


def render_sections(grouped: dict[str, list[str]]) -> str:
    sections = []
    for day in sorted(grouped, reverse=True):
        lines = [f"## {day}"]
        for subject in grouped[day]:
            lines.append(f"- {subject}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def main() -> None:
    latest = latest_date_in_changelog()

    if latest is None:
        # Full log — create file from scratch
        entries = git_log()
        if not entries:
            print("No commits found.")
            sys.exit(0)

        grouped = group_by_date(entries)
        body = render_sections(grouped)
        CHANGELOG.write_text(f"# Changelog\n\n{body}\n")
        print(f"Created {CHANGELOG} ({len(entries)} commits, {len(grouped)} days)")

    else:
        # Incremental — only commits strictly after latest date
        entries = git_log(after_date=latest)
        if not entries:
            print(f"No new commits after {latest}. {CHANGELOG} unchanged.")
            sys.exit(0)

        grouped = group_by_date(entries)
        new_sections = render_sections(grouped)

        existing = CHANGELOG.read_text()

        # Find the end of the header line robustly — match any casing/spacing
        header_pos = None
        for i, line in enumerate(existing.splitlines(keepends=True)):
            if _HEADER_RE.match(line.strip()):
                header_pos = sum(len(l) for l in existing.splitlines(keepends=True)[:i+1])
                break

        if header_pos is None:
            # Fallback: prepend before everything
            CHANGELOG.write_text(f"# Changelog\n\n{new_sections}\n\n{existing}")
        else:
            updated = (
                existing[:header_pos]
                + "\n"
                + new_sections
                + "\n\n"
                + existing[header_pos:].lstrip("\n")
            )
            CHANGELOG.write_text(updated)

        print(f"Updated {CHANGELOG} (+{len(entries)} commits, {len(grouped)} new days)")


if __name__ == "__main__":
    main()
