#!/usr/bin/env bash
set -euo pipefail

OUT_WIN="C:\\Users\\jim\\Downloads\\RTL-Windows-ADS-B-Tracker-map-popout-kiosk-defaults-v2-web-assets.zip"
OUT_POSIX="/c/Users/jim/Downloads/RTL-Windows-ADS-B-Tracker-map-popout-kiosk-defaults-v2-web-assets.zip"

if [[ ! -f web/app.js || ! -f web/app.css ]]; then
  echo 'FAIL: run from repo root; web/app.js or web/app.css missing' >&2
  exit 1
fi

./tools/validate_map_popout_kiosk_defaults_v2.sh

rm -f "$OUT_POSIX"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
mkdir -p "$TMPDIR/web"
cp web/app.js "$TMPDIR/web/app.js"
cp web/app.css "$TMPDIR/web/app.css"
cat > "$TMPDIR/README_MAP_POPOUT_KIOSK_DEFAULTS_V2_WEB_ASSETS.txt" <<'TXT'
RTL-Windows-ADS-B-Tracker Map Pop-out Kiosk Defaults V2 Web Assets

Manual install:
1. Back up the tracker files:
   C:\RTL-ADS-B-Tracker-Windows-Service-v1.3.0\web\app.js
   C:\RTL-ADS-B-Tracker-Windows-Service-v1.3.0\web\app.css
2. Copy this ZIP's web\app.js and web\app.css into the active tracker install web folder.
3. Browser hard-refresh with Ctrl+F5.

No service restart is required for this frontend-only change.

Pop-out kiosk URL defaults:
- http://TRACKER:8090/?map_popout=1
  Receiver-centered 100-mile map view.

URL switches:
- ?map_popout=1&map_fit=planes
  Auto-fit active planes/receiver as aircraft updates arrive.
- ?map_popout=1&fit=planes
  Alias for map_fit=planes.
- ?map_popout=1&autofit=planes
  Alias for map_fit=planes.
- ?map_popout=1&map_radius_miles=150
  Receiver radius override.
- ?map_popout=1&radius_miles=150
  Alias for map_radius_miles.
- ?map_popout=1&radius=150
  Alias for map_radius_miles.
TXT
(
  cd "$TMPDIR"
  zip -qr "$OUT_POSIX" web README_MAP_POPOUT_KIOSK_DEFAULTS_V2_WEB_ASSETS.txt
)

echo "PASS: wrote $OUT_WIN"
