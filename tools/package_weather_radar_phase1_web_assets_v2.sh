#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="/c/Users/jim/Downloads/RTL-Windows-ADS-B-Tracker-weather-radar-phase1-v2-web-assets.zip"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
mkdir -p "${TMP}/web"
cp "${ROOT}/web/app.js" "${TMP}/web/app.js"
cp "${ROOT}/web/app.css" "${TMP}/web/app.css"
(cd "${TMP}" && zip -q -r "${OUT}" web)
echo "Wrote: ${OUT}"
