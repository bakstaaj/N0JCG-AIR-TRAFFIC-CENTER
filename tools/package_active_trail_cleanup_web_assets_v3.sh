#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f web/app.js ]]; then
  echo "FAIL: web/app.js not found. Run from repository root." >&2
  exit 1
fi

if ! grep -q 'ACTIVE_TRAIL_CLEANUP_V3' web/app.js; then
  echo "FAIL: web/app.js does not contain ACTIVE_TRAIL_CLEANUP_V3. Apply and validate first." >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "FAIL: zip command not found in PATH." >&2
  exit 1
fi

./tools/validate_active_trail_cleanup_v3.sh

OUT_WIN='C:\Users\jim\Downloads\RTL-Windows-ADS-B-Tracker-active-trail-cleanup-v3-web-assets.zip'
if command -v cygpath >/dev/null 2>&1; then
  OUT="$(cygpath -u "$OUT_WIN")"
else
  OUT='/c/Users/jim/Downloads/RTL-Windows-ADS-B-Tracker-active-trail-cleanup-v3-web-assets.zip'
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
mkdir -p "$TMPDIR/web"
cp web/app.js "$TMPDIR/web/app.js"
# Include CSS if present so the asset ZIP can be used consistently with earlier manual-upload workflows.
if [[ -f web/app.css ]]; then cp web/app.css "$TMPDIR/web/app.css"; fi

mkdir -p "$(dirname "$OUT")"
(
  cd "$TMPDIR"
  zip -qr "$OUT" web
)

echo "PASS: wrote $OUT_WIN"
