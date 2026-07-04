#!/usr/bin/env bash
set -euo pipefail

OUT_WIN="C:\\Users\\jim\\Downloads\\RTL-Windows-ADS-B-Tracker-map-popout-fullscreen-v1-web-assets.zip"
OUT_POSIX="/c/Users/jim/Downloads/RTL-Windows-ADS-B-Tracker-map-popout-fullscreen-v1-web-assets.zip"

if [[ ! -f web/app.js || ! -f web/app.css ]]; then
  echo 'FAIL: run from repo root; web/app.js or web/app.css missing' >&2
  exit 1
fi

./tools/validate_map_popout_fullscreen_v1.sh

rm -f "$OUT_POSIX"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
mkdir -p "$TMPDIR/web"
cp web/app.js "$TMPDIR/web/app.js"
cp web/app.css "$TMPDIR/web/app.css"
cat > "$TMPDIR/README_MAP_POPOUT_FULLSCREEN_V1_WEB_ASSETS.txt" <<'TXT'
RTL-Windows-ADS-B-Tracker Map Pop-out / Full Screen V1 Web Assets

Manual install:
1. Back up the tracker files:
   C:\RTL-ADS-B-Tracker-Windows-Service-v1.3.0\web\app.js
   C:\RTL-ADS-B-Tracker-Windows-Service-v1.3.0\web\app.css
2. Copy this ZIP's web\app.js and web\app.css into the tracker install web folder.
3. Browser hard-refresh with Ctrl+F5.

No service restart is required for this frontend-only change.
TXT
(
  cd "$TMPDIR"
  zip -qr "$OUT_POSIX" web README_MAP_POPOUT_FULLSCREEN_V1_WEB_ASSETS.txt
)

echo "PASS: wrote $OUT_WIN"
