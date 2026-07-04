#!/usr/bin/env python3
"""Rollback the append-only Phase 1 V2 weather radar patch."""
from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
APP_JS = ROOT / "web" / "app.js"
APP_CSS = ROOT / "web" / "app.css"
JS_BEGIN = "\n/* RTP_WEATHER_RADAR_PHASE1_V2:"
CSS_BEGIN = "\n/* Phase 1 weather radar map overlay controls V2 */"


def trim_from_marker(path: Path, marker: str) -> None:
    text = path.read_text(encoding="utf-8")
    idx = text.find(marker)
    if idx < 0:
      print(f"No V2 weather radar block found in {path}")
      return
    path.write_text(text[:idx].rstrip() + "\n", encoding="utf-8", newline="\n")
    print(f"Removed V2 weather radar block from {path}")


def main() -> None:
    trim_from_marker(APP_JS, JS_BEGIN)
    trim_from_marker(APP_CSS, CSS_BEGIN)


if __name__ == "__main__":
    main()
