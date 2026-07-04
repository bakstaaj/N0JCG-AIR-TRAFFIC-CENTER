#!/usr/bin/env bash
# Package updated web assets for production tracker-host validation.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOWNLOADS='/c/Users/jim/Downloads'
OUT="${DOWNLOADS}/RTL-Windows-ADS-B-Tracker-weather-radar-phase1-web-assets.zip"
cd "${ROOT}"
[[ -f web/app.js && -f web/app.css ]] || { echo 'ERROR: web assets not found.' >&2; exit 1; }
if command -v node >/dev/null 2>&1; then
  node --check web/app.js
else
  echo 'WARNING: node is not available; skipping JavaScript syntax check.' >&2
fi
if ! grep -q 'WEATHER_RADAR_ENABLED_KEY' web/app.js; then
  echo 'ERROR: Weather radar JavaScript patch was not found in web/app.js' >&2
  exit 1
fi
if ! grep -q 'Phase 1 weather radar map overlay controls' web/app.css; then
  echo 'ERROR: Weather radar CSS patch was not found in web/app.css' >&2
  exit 1
fi
rm -f "${OUT}"
mkdir -p "${DOWNLOADS}"
zip -j "${OUT}" web/app.js web/app.css >/dev/null
printf 'Created production web asset package:\n  %s\n' "${OUT}"
