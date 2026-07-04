#!/usr/bin/env python3
"""
Apply Active Trail Cleanup V3 for RTL-Windows-ADS-B-Tracker.

Goal:
  When the active aircraft marker/icon is removed from the live Leaflet map,
  remove that aircraft's active trail layers from the display at the same time.

Important:
  This does NOT clear aircraftTrailHistory, localStorage, or server trail history.
  Restore History / Erase History behavior remains separate.
"""
from __future__ import annotations

import datetime as _dt
import pathlib
import re
import sys

ROOT = pathlib.Path.cwd()
APP_JS = ROOT / "web" / "app.js"
MARKER = "ACTIVE_TRAIL_CLEANUP_V3"

DIRECT_PATTERNS = [
    re.compile(r"(?P<indent>[ \t]*)if\s*\(\s*aircraftTrailDisplayMode\s*===\s*['\"]active['\"]\s*\)\s*removeTrailLayersForAircraft\(key\);"),
    re.compile(r"(?P<indent>[ \t]*)if\s*\(\s*aircraftTrailDisplayMode\s*==\s*['\"]active['\"]\s*\)\s*removeTrailLayersForAircraft\(key\);"),
]

WRAPPER = r'''

/* ACTIVE_TRAIL_CLEANUP_V3_START
 * Keep active trail display synchronized with active marker/icon cleanup.
 * If updateAircraftMap removes an aircraft marker because it is no longer active,
 * remove the matching displayed trail layers as well. This does not erase stored
 * browser/server history; Restore History and Erase History remain separate.
 */
(function(){
  'use strict';
  if (typeof updateAircraftMap !== 'function') return;
  if (updateAircraftMap.__activeTrailCleanupV3Installed) return;

  const __activeTrailCleanupV3BaseUpdateAircraftMap = updateAircraftMap;

  function __activeTrailCleanupV3MarkerKeys() {
    const keys = new Set();
    try {
      if (typeof aircraftMapMarkers === 'undefined' || !aircraftMapMarkers) return keys;
      for (const entry of aircraftMapMarkers.entries()) {
        const key = String(entry[0]);
        const marker = entry[1];
        let visible = true;
        try {
          if (typeof aircraftMap !== 'undefined' && aircraftMap && marker && typeof aircraftMap.hasLayer === 'function') {
            visible = aircraftMap.hasLayer(marker);
          }
        } catch (_e) {}
        if (visible) keys.add(key);
      }
    } catch (_e) {}
    return keys;
  }

  function __activeTrailCleanupV3RemoveDisplayedTrail(key) {
    try {
      if (typeof removeTrailLayersForAircraft === 'function') {
        removeTrailLayersForAircraft(key);
      }
    } catch (_e) {}
    try {
      if (typeof aircraftLastPositions !== 'undefined' && aircraftLastPositions) {
        aircraftLastPositions.delete(key);
      }
    } catch (_e) {}
  }

  updateAircraftMap = function activeTrailCleanupV3UpdateAircraftMapWrapper(aircraftRecords) {
    const beforeMarkerKeys = __activeTrailCleanupV3MarkerKeys();
    const result = __activeTrailCleanupV3BaseUpdateAircraftMap.apply(this, arguments);
    const afterMarkerKeys = __activeTrailCleanupV3MarkerKeys();

    for (const key of beforeMarkerKeys) {
      if (!afterMarkerKeys.has(key)) {
        __activeTrailCleanupV3RemoveDisplayedTrail(key);
      }
    }

    return result;
  };

  updateAircraftMap.__activeTrailCleanupV3Installed = true;
  window.__activeTrailCleanupV3 = {
    installed: true,
    mode: 'wrap-marker-removal',
    marker: 'ACTIVE_TRAIL_CLEANUP_V3',
    installedUtc: new Date().toISOString()
  };
})();
/* ACTIVE_TRAIL_CLEANUP_V3_END */
'''


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    if not APP_JS.exists():
        fail(f"Missing {APP_JS}. Run from the repository root.")

    text = APP_JS.read_text(encoding="utf-8")
    if MARKER in text:
        print("PASS: Active trail cleanup V3 is already present in web/app.js")
        return

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = APP_JS.with_suffix(APP_JS.suffix + f".bak_active_trail_cleanup_v3_{stamp}")
    backup.write_text(text, encoding="utf-8")

    patched = text
    direct_applied = False
    for pattern in DIRECT_PATTERNS:
        match = pattern.search(patched)
        if match:
            indent = match.group("indent")
            replacement = (
                f"{indent}// {MARKER}: when marker/icon is removed from the active display,\n"
                f"{indent}// remove that aircraft's displayed trail layers too. Stored history remains intact.\n"
                f"{indent}removeTrailLayersForAircraft(key);"
            )
            patched = patched[:match.start()] + replacement + patched[match.end():]
            direct_applied = True
            break

    if not direct_applied:
        # Fallback for current/future app.js variants: wrap updateAircraftMap and
        # remove trail layers for keys whose markers disappeared during the update.
        patched = patched.rstrip() + WRAPPER + "\n"

    APP_JS.write_text(patched, encoding="utf-8", newline="\n")

    mode = "direct marker-cleanup patch" if direct_applied else "append-only marker-removal wrapper"
    print(f"PASS: Applied active trail cleanup V3 using {mode}")
    print(f"PASS: Backup written to {backup}")


if __name__ == "__main__":
    main()
