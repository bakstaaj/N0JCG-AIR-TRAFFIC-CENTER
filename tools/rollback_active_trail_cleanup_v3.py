#!/usr/bin/env python3
"""Rollback Active Trail Cleanup V3 from web/app.js."""
from __future__ import annotations
import pathlib
import re
import sys

APP_JS = pathlib.Path.cwd() / "web" / "app.js"
MARKER = "ACTIVE_TRAIL_CLEANUP_V3"
WRAPPER_RE = re.compile(r"\n?/\* ACTIVE_TRAIL_CLEANUP_V3_START.*?/\* ACTIVE_TRAIL_CLEANUP_V3_END \*/\n?", re.S)
DIRECT_RE = re.compile(
    r"(?P<indent>[ \t]*)// ACTIVE_TRAIL_CLEANUP_V3: when marker/icon is removed from the active display,\n"
    r"(?P=indent)// remove that aircraft's displayed trail layers too\. Stored history remains intact\.\n"
    r"(?P=indent)removeTrailLayersForAircraft\(key\);"
)

if not APP_JS.exists():
    print(f"FAIL: Missing {APP_JS}. Run from repository root.")
    sys.exit(1)

text = APP_JS.read_text(encoding="utf-8")
new_text = WRAPPER_RE.sub("\n", text)
new_text = DIRECT_RE.sub("\\g<indent>if (aircraftTrailDisplayMode === 'active') removeTrailLayersForAircraft(key);", new_text)

if new_text == text:
    print("PASS: No active trail cleanup V3 patch found to roll back.")
else:
    APP_JS.write_text(new_text, encoding="utf-8", newline="\n")
    print("PASS: Rolled back active trail cleanup V3 from web/app.js")
