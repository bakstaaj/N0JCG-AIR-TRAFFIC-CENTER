#!/usr/bin/env python3
"""
Patch web/app.js so active aircraft markers/trails/table rows clear when an
aircraft is stale or no longer present, while retained trail history remains
available through Restore History.

Run from the repository root:
  python3 tools/patch_active_trail_cleanup.py
"""
from pathlib import Path

path = Path("web/app.js")
if not path.exists():
    raise SystemExit("ERROR: web/app.js not found. Run this from the repository root.")

text = path.read_text(encoding="utf-8")
original = text

constant_anchor = "let aircraftTrailClearedAt = Number(localStorage.getItem(TRAIL_CLEARED_AT_KEY) || '0');\n"
constant_insert = constant_anchor + "const ACTIVE_AIRCRAFT_STALE_SECONDS = 60;\n"
if "ACTIVE_AIRCRAFT_STALE_SECONDS" not in text:
    if constant_anchor not in text:
        raise SystemExit("ERROR: Could not find trail-cleared timestamp anchor for stale-aircraft constant.")
    text = text.replace(constant_anchor, constant_insert, 1)

altitude_block = """function altitudeFeet(aircraft) {
  const value = aircraft.alt_baro != null ? aircraft.alt_baro : (aircraft.altitude != null ? aircraft.altitude : aircraft.alt_geom);
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
"""
active_helpers = altitude_block + """function aircraftSeenSeconds(aircraft) {
  const seen = Number(aircraft && aircraft.seen);
  if (Number.isFinite(seen)) return seen;
  const seenPos = Number(aircraft && aircraft.seen_pos);
  if (Number.isFinite(seenPos)) return seenPos;
  return null;
}
function isAircraftRecordActive(aircraft) {
  const seenSeconds = aircraftSeenSeconds(aircraft);
  return seenSeconds == null || seenSeconds <= ACTIVE_AIRCRAFT_STALE_SECONDS;
}
"""
if "function isAircraftRecordActive" not in text:
    if altitude_block not in text:
        raise SystemExit("ERROR: Could not find altitudeFeet block for active-aircraft helper insertion.")
    text = text.replace(altitude_block, active_helpers, 1)

old_positioned = "const positioned = aircraftRecords.filter(item => Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lon)));"
new_positioned = "const positioned = aircraftRecords.filter(item => isAircraftRecordActive(item) && Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lon)));"
if old_positioned in text:
    text = text.replace(old_positioned, new_positioned, 1)
elif new_positioned not in text:
    raise SystemExit("ERROR: Could not patch positioned aircraft filter in updateAircraftMap.")

old_update = """    const aircraft = Array.isArray(data.aircraft) ? data.aircraft : [];
    updateAircraftMap(aircraft);
    const visibleAircraft = aircraft.slice(0, 20);
"""
new_update = """    const aircraft = Array.isArray(data.aircraft) ? data.aircraft : [];
    const activeAircraft = aircraft.filter(isAircraftRecordActive);
    updateAircraftMap(activeAircraft);
    const visibleAircraft = activeAircraft.slice(0, 20);
"""
if old_update in text:
    text = text.replace(old_update, new_update, 1)
elif new_update not in text:
    raise SystemExit("ERROR: Could not patch active aircraft list filtering in updateAircraft.")

if text == original:
    print("No changes needed; active trail cleanup patch already appears to be applied.")
else:
    path.write_text(text, encoding="utf-8")
    print("Patched web/app.js: stale aircraft are filtered from active map/table display; trail history is preserved.")
