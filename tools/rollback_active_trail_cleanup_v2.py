#!/usr/bin/env python3
"""Remove the active trail cleanup V2 append block from web/app.js."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

PATCH_ID = "active-trail-cleanup-v2-rollback"
APP_JS = Path("web/app.js")
START = "/* ACTIVE_TRAIL_CLEANUP_V2_START */"
END = "/* ACTIVE_TRAIL_CLEANUP_V2_END */"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak_{PATCH_ID}_{stamp}")
    shutil.copy2(path, backup)
    return backup


def main() -> int:
    if not APP_JS.exists():
        fail(f"{APP_JS} not found. Run this from the repository root.")
    text = APP_JS.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\s*", re.DOTALL)
    updated, count = pattern.subn("", text)
    if count == 0:
        print("PASS: active trail cleanup V2 block was not present; nothing to roll back.")
        return 0
    backup = backup_file(APP_JS)
    APP_JS.write_text(updated.rstrip() + "\n", encoding="utf-8")
    print(f"PASS: removed active trail cleanup V2 block from {APP_JS}")
    print(f"Backup before rollback: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
