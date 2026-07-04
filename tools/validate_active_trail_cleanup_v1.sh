#!/usr/bin/env bash
set -u

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

pass() {
  echo "PASS: $*"
}

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || fail "Run from inside the RTL-Windows-ADS-B-Tracker repository"

[ -f web/app.js ] || fail "web/app.js not found"

if command -v node >/dev/null 2>&1; then
  node --check web/app.js >/tmp/active_trail_node_check.txt 2>&1 || {
    cat /tmp/active_trail_node_check.txt >&2
    fail "node --check web/app.js failed"
  }
  pass "JavaScript syntax check passed"
else
  echo "WARN: node is not installed; skipping JavaScript syntax check"
fi

python3 - <<'PY'
from pathlib import Path
import sys

text = Path("web/app.js").read_text(encoding="utf-8")
required = {
    "ACTIVE_AIRCRAFT_STALE_SECONDS": "stale threshold constant",
    "function aircraftAgeSeconds": "aircraft age helper",
    "function isAircraftRecordActive": "active aircraft helper",
    "function isAircraftMapPositionActive": "active map position helper",
    ".filter(isAircraftMapPositionActive)": "map stale-position filter",
    "const activeAircraft = aircraft.filter(isAircraftRecordActive);": "active table aircraft filter",
    "updateAircraftMap(activeAircraft);": "active-only map update",
    "const visibleAircraft = activeAircraft.slice(0, 20);": "active-only table rows",
}
missing = [label for needle, label in required.items() if needle not in text]
if missing:
    print("FAIL: missing expected active trail cleanup markers:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

for forbidden in [
    "updateAircraftMap(aircraft);\n    const visibleAircraft = aircraft.slice(0, 20);",
]:
    if forbidden in text:
        print("FAIL: stale pre-patch aircraft update block is still present")
        sys.exit(1)

print("PASS: active trail cleanup markers verified")
PY
[ $? -eq 0 ] || exit 1

pass "Active aircraft map/trail cleanup validation complete"
