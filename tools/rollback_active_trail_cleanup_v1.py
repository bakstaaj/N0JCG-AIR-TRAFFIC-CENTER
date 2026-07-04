#!/usr/bin/env python3
"""
Rollback active aircraft map/trail cleanup patch.

This reverts only the specific text inserted by apply_active_trail_cleanup_v1.py.
It does not touch browser/server trail history.
"""

from __future__ import annotations

from pathlib import Path
import sys

APP_JS = Path("web/app.js")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    if not APP_JS.exists():
        fail(f"{APP_JS} not found. Run this from the repository root.")

    text = APP_JS.read_text(encoding="utf-8")
    original = text

    text = text.replace(
        """
/* Active display cleanup: keep history, but remove stale aircraft from the live map. */
const ACTIVE_AIRCRAFT_STALE_SECONDS = 60;
""",
        "",
    )

    text = text.replace(
        r"""
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
""",
        "",
    )

    text = text.replace(
        """function updateAircraftMap(aircraftRecords) {
  if (!aircraftMap) return;
  const positioned = aircraftRecords
    .filter(isAircraftMapPositionActive)
    .filter(item => Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lon)));
""",
        """function updateAircraftMap(aircraftRecords) {
  if (!aircraftMap) return;
  const positioned = aircraftRecords.filter(item => Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lon)));
""",
    )

    text = text.replace(
        """    const aircraft = Array.isArray(data.aircraft) ? data.aircraft : [];
    const activeAircraft = aircraft.filter(isAircraftRecordActive);
    updateAircraftMap(activeAircraft);
    const visibleAircraft = activeAircraft.slice(0, 20);
""",
        """    const aircraft = Array.isArray(data.aircraft) ? data.aircraft : [];
    updateAircraftMap(aircraft);
    const visibleAircraft = aircraft.slice(0, 20);
""",
    )

    text = text.replace(
        """    positioned.length ? `Displaying ${positioned.length} active aircraft with current positions. Click an aircraft for details.` : 'No active positioned aircraft currently reported by readsb.',
""",
        """    positioned.length ? `Displaying ${positioned.length} aircraft with positions. Click an aircraft for details.` : 'No positioned aircraft currently reported by readsb.',
""",
    )

    if text == original:
        print("PASS: no active trail cleanup patch text found; nothing changed.")
        return 0

    APP_JS.write_text(text, encoding="utf-8")
    print(f"PASS: rolled back active trail cleanup changes in {APP_JS}")
    print("Next: run node --check web/app.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
