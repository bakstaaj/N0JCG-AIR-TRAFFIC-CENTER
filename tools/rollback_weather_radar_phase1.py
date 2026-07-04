#!/usr/bin/env python3
"""Remove Phase 1 weather radar overlay blocks from app.js and app.css.

Run from the repository root:
  python3 tools/rollback_weather_radar_phase1.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

ROOT = Path.cwd()
APP_JS = ROOT / "web" / "app.js"
APP_CSS = ROOT / "web" / "app.css"

MARKERS = [
    (APP_JS, "/* BEGIN Phase 1 weather radar overlay */", "/* END Phase 1 weather radar overlay */"),
    (APP_CSS, "/* BEGIN Phase 1 weather radar overlay controls */", "/* END Phase 1 weather radar overlay controls */"),
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def backup(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(path.name + f".bak_before_weather_radar_rollback_{stamp}")
    target.write_bytes(path.read_bytes())
    print(f"Backup: {target}")


def remove_block(text: str, begin: str, end: str) -> tuple[str, bool]:
    start = text.find(begin)
    if start < 0:
        return text, False
    stop = text.find(end, start)
    if stop < 0:
        fail(f"Found {begin!r} without matching {end!r}")
    stop += len(end)
    return text[:start].rstrip() + "\n" + text[stop:].lstrip("\n"), True


def main() -> int:
    changed_any = False
    for path, begin, end in MARKERS:
        if not path.exists():
            fail(f"Missing file: {path}")
        text = path.read_text(encoding="utf-8")
        updated, changed = remove_block(text, begin, end)
        if changed:
            backup(path)
            path.write_text(updated, encoding="utf-8", newline="\n")
            print(f"Removed weather radar block from {path}")
            changed_any = True
        else:
            print(f"No weather radar block found in {path}")
    if not changed_any:
        print("Nothing to roll back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
