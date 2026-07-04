#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f web/app.js ]]; then
  echo "FAIL: web/app.js not found. Run from the repository root." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATOR="$SCRIPT_DIR/validate_active_trail_cleanup_v2.sh"
if [[ ! -x "$VALIDATOR" ]]; then
  VALIDATOR="tools/validate_active_trail_cleanup_v2.sh"
fi

"$VALIDATOR"

OUT_WIN="C:\\Users\\jim\\Downloads\\RTL-Windows-ADS-B-Tracker-active-trail-cleanup-v2-web-assets.zip"
if command -v cygpath >/dev/null 2>&1; then
  OUT="$(cygpath -u "$OUT_WIN")"
else
  OUT="/c/Users/jim/Downloads/RTL-Windows-ADS-B-Tracker-active-trail-cleanup-v2-web-assets.zip"
fi

mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
cp web/app.js "$TMPDIR/app.js"
printf 'active-trail-cleanup-v2\ncreated=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$TMPDIR/manifest.txt"
(
  cd "$TMPDIR"
  zip -q "$OUT" app.js manifest.txt
)

echo "PASS: wrote $OUT_WIN"
