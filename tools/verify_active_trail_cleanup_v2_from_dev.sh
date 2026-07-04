#!/usr/bin/env bash
# Verify Active Trail Cleanup V2 on tracker from the dev workstation.
# MSYS2-only workflow. No PowerShell and no tracker-side dev tools required.

set -u

TRACKER_HOST="${TRACKER_HOST:-192.168.68.135}"
TRACKER_PORT="${TRACKER_PORT:-8090}"
SERVICE_NAME="${SERVICE_NAME:-RTLADSBTracker}"
PRIMARY_MARKER="ACTIVE_TRAIL_CLEANUP_V2_START"
SECONDARY_MARKER="activeTrailCleanupFilterAircraftPayload"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }
info() { echo "INFO: $*"; }

service_state() {
  sc.exe "\\\\${TRACKER_HOST}" query "$SERVICE_NAME" 2>/dev/null | tr -d '\r' | awk '/STATE/ {print $4; exit}'
}

base="http://${TRACKER_HOST}:${TRACKER_PORT}"

state="$(service_state || true)"
[[ "$state" == "RUNNING" ]] || fail "${SERVICE_NAME} is not RUNNING on ${TRACKER_HOST}; state=${state:-unknown}"
pass "${SERVICE_NAME} is RUNNING on ${TRACKER_HOST}"

tmp_status="$(mktemp)"
if curl -fsS --max-time 15 "${base}/api/status" >"$tmp_status"; then
  pass "Tracker API reachable at ${base}/api/status"
else
  cat "$tmp_status" 2>/dev/null || true
  rm -f "$tmp_status"
  fail "Tracker API is not reachable at ${base}/api/status"
fi

if grep -Eq '"aircraft_count"[[:space:]]*:[[:space:]]*[1-9]' "$tmp_status"; then
  pass "API reports one or more aircraft"
else
  info "API did not report aircraft_count > 0 at this instant; this may be normal if no aircraft are currently visible"
fi
rm -f "$tmp_status"

tmp_js="$(mktemp)"
if curl -fsS --max-time 15 "${base}/app.js?activeTrailCleanupV2Verify=$(date +%s)" >"$tmp_js"; then
  pass "Served app.js downloaded"
else
  rm -f "$tmp_js"
  fail "Could not download served app.js from ${base}/app.js"
fi

grep -Fq "$PRIMARY_MARKER" "$tmp_js" || fail "Served app.js is missing ${PRIMARY_MARKER}"
grep -Fq "$SECONDARY_MARKER" "$tmp_js" || fail "Served app.js is missing ${SECONDARY_MARKER}"
grep -Fq "function activeTrailCleanupIsAircraftRecordActive" "$tmp_js" || fail "Served app.js missing active aircraft record helper"
grep -Fq "function activeTrailCleanupIsAircraftMapPositionActive" "$tmp_js" || fail "Served app.js missing active map position helper"
grep -Fq "function activeTrailCleanupInstallJsonFilter" "$tmp_js" || fail "Served app.js missing aircraft.json filter wrapper"
grep -Fq "function activeTrailCleanupInstallMapFilter" "$tmp_js" || fail "Served app.js missing updateAircraftMap filter wrapper"
pass "Served app.js contains Active Trail Cleanup V2 runtime wrapper"
rm -f "$tmp_js"

if command -v tasklist.exe >/dev/null 2>&1; then
  echo
  info "Remote process snapshot from tasklist.exe"
  tasklist.exe /S "$TRACKER_HOST" /FI "IMAGENAME eq RTLADSBTrackerService.exe" 2>/dev/null | tr -d '\r' || true
  tasklist.exe /S "$TRACKER_HOST" /FI "IMAGENAME eq RTLADSBTrackerBackend.exe" 2>/dev/null | tr -d '\r' || true
  tasklist.exe /S "$TRACKER_HOST" /FI "IMAGENAME eq dump1090.exe" 2>/dev/null | tr -d '\r' || true
fi

echo
pass "Active Trail Cleanup V2 production verification completed from dev"
echo "INFO: Browser validation: Ctrl+F5, confirm active trails clear when aircraft go stale, then Restore History still works."
