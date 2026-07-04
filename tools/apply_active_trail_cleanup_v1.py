#!/usr/bin/env python3
"""
Apply active aircraft map/trail cleanup for RTL-Windows-ADS-B-Tracker.

Behavior:
- Treat aircraft records with stale readsb `seen` values as inactive.
- Treat map positions with stale readsb `seen_pos` values as inactive.
- Remove inactive aircraft markers and active trail display segments.
- Keep browser/server trail history intact so Restore History still works.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
from datetime import datetime


MARKER = "ACTIVE_AIRCRAFT_STALE_SECONDS"
PATCH_ID = "active-trail-cleanup-v1"
APP_JS = Path("web/app.js")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak_{PATCH_ID}_{stamp}")
    shutil.copy2(path, backup)
    return backup


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Expected exactly one {label} anchor, found {count}.")
    return text.replace(old, new, 1)


def main() -> int:
    if not APP_JS.exists():
        fail(f"{APP_JS} not found. Run this from the repository root.")

    original = APP_JS.read_text(encoding="utf-8")
    text = original

    if MARKER in text and "function isAircraftMapPositionActive" in text and "const activeAircraft = aircraft.filter(isAircraftRecordActive);" in text:
        print("PASS: active trail cleanup patch is already present.")
        return 0

    backup = backup_file(APP_JS)

    # 1. Add the stale threshold constant beside the existing trail state.
    if MARKER not in text:
        anchor = "let aircraftTrailClearedAt = Number(localStorage.getItem(TRAIL_CLEARED_AT_KEY) || '0');\n"
        insert = anchor + (
            "\n"
            "/* Active display cleanup: keep history, but remove stale aircraft from the live map. */\n"
            "const ACTIVE_AIRCRAFT_STALE_SECONDS = 60;\n"
        )
        text = replace_once(text, anchor, insert, "trail state")

    # 2. Add helper functions after altitudeFeet().
    if "function isAircraftMapPositionActive" not in text:
        anchor = """function altitudeFeet(aircraft) {
  const value = aircraft.alt_baro != null ? aircraft.alt_baro : (aircraft.altitude != null ? aircraft.altitude : aircraft.alt_geom);
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
"""
        insert = anchor + r"""
function aircraftAgeSeconds(aircraft, fieldName) {
  if (!aircraft || typeof aircraft !== 'object') return null;
  const value = Number(aircraft[fieldName]);
  return Number.isFinite(value) ? value : null;
}
function isAircraftRecordActive(aircraft) {
  const seen = aircraftAgeSeconds(aircraft, 'seen');
  return seen == null || seen <= ACTIVE_AIRCRAFT_STALE_SECONDS;
}
function isAircraftMapPositionActive(aircraft) {
  const seenPosition = aircraftAgeSeconds(aircraft, 'seen_pos');
  if (seenPosition != null) return seenPosition <= ACTIVE_AIRCRAFT_STALE_SECONDS;
  return isAircraftRecordActive(aircraft);
}
"""
        text = replace_once(text, anchor, insert, "altitudeFeet helper")

    # 3. Defensively filter stale map positions inside updateAircraftMap().
    old = """function updateAircraftMap(aircraftRecords) {
  if (!aircraftMap) return;
  const positioned = aircraftRecords.filter(item => Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lon)));
"""
    new = """function updateAircraftMap(aircraftRecords) {
  if (!aircraftMap) return;
  const positioned = aircraftRecords
    .filter(isAircraftMapPositionActive)
    .filter(item => Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lon)));
"""
    if old in text:
        text = replace_once(text, old, new, "updateAircraftMap positioned filter")
    elif ".filter(isAircraftMapPositionActive)" not in text:
        fail("Could not find updateAircraftMap positioned filter anchor.")

    # 4. Use only active aircraft for the active table and map update.
    old = """    const aircraft = Array.isArray(data.aircraft) ? data.aircraft : [];
    updateAircraftMap(aircraft);
    const visibleAircraft = aircraft.slice(0, 20);
"""
    new = """    const aircraft = Array.isArray(data.aircraft) ? data.aircraft : [];
    const activeAircraft = aircraft.filter(isAircraftRecordActive);
    updateAircraftMap(activeAircraft);
    const visibleAircraft = activeAircraft.slice(0, 20);
"""
    if old in text:
        text = replace_once(text, old, new, "updateAircraft active aircraft block")
    elif "const activeAircraft = aircraft.filter(isAircraftRecordActive);" not in text:
        fail("Could not find updateAircraft aircraft list anchor.")

    # 5. Make the map status text explicit.
    old = """    positioned.length ? `Displaying ${positioned.length} aircraft with positions. Click an aircraft for details.` : 'No positioned aircraft currently reported by readsb.',
"""
    new = """    positioned.length ? `Displaying ${positioned.length} active aircraft with current positions. Click an aircraft for details.` : 'No active positioned aircraft currently reported by readsb.',
"""
    if old in text:
        text = text.replace(old, new, 1)

    if text == original:
        print("PASS: no changes needed; active trail cleanup already appears applied.")
        return 0

    APP_JS.write_text(text, encoding="utf-8")
    print(f"PASS: patched {APP_JS}")
    print(f"Backup: {backup}")
    print("Next: run ./tools/validate_active_trail_cleanup_v1.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
