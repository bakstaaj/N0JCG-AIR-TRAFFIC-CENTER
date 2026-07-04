#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

fail=0
for pattern in \
  'RTP_WEATHER_RADAR_PHASE1_V2' \
  'weatherRadarControls' \
  'nexrad-n0q' \
  'weatherRadarPane'; do
  if ! grep -q "$pattern" web/app.js; then
    echo "ERROR: Missing JavaScript pattern: $pattern" >&2
    fail=1
  fi
done

if ! grep -q 'Phase 1 weather radar map overlay controls V2' web/app.css; then
  echo "ERROR: Missing CSS weather radar block" >&2
  fail=1
fi

if command -v node >/dev/null 2>&1; then
  node --check web/app.js
else
  echo "WARNING: node not found; skipped JavaScript syntax check" >&2
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "PASS: Weather radar Phase 1 V2 patch is present."
