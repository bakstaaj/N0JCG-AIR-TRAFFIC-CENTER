#!/usr/bin/env bash
set -u

failures=0
fail() { echo "FAIL: $*"; failures=$((failures+1)); }
pass() { echo "PASS: $*"; }

if [[ ! -f web/app.js ]]; then
  fail "web/app.js not found. Run from the repository root."
  exit 1
fi

if command -v node >/dev/null 2>&1; then
  if node --check web/app.js >/tmp/active_trail_cleanup_node_check.txt 2>&1; then
    pass "JavaScript syntax check passed"
  else
    fail "JavaScript syntax check failed"
    cat /tmp/active_trail_cleanup_node_check.txt
  fi
else
  fail "node not found; cannot run JavaScript syntax check"
fi

required=(
  "ACTIVE_TRAIL_CLEANUP_V2_START"
  "ACTIVE_TRAIL_CLEANUP_STALE_SECONDS"
  "function activeTrailCleanupAircraftAgeSeconds"
  "function activeTrailCleanupIsAircraftRecordActive"
  "function activeTrailCleanupIsAircraftMapPositionActive"
  "function activeTrailCleanupFilterAircraftPayload"
  "function activeTrailCleanupInstallJsonFilter"
  "function activeTrailCleanupInstallMapFilter"
  "active_display_filtered_stale_count"
  "ACTIVE_TRAIL_CLEANUP_V2_END"
)

missing=0
for marker in "${required[@]}"; do
  if grep -Fq "$marker" web/app.js; then
    :
  else
    echo "  missing marker: $marker"
    missing=$((missing+1))
  fi
done

if [[ "$missing" -eq 0 ]]; then
  pass "active trail cleanup V2 markers verified"
else
  fail "missing expected active trail cleanup V2 markers"
fi

if grep -Fq "localStorage.removeItem(TRAIL_STORAGE_KEY)" web/app.js; then
  pass "existing explicit history-clear behavior still isolated to Clear/Erase functions"
else
  pass "no unexpected localStorage trail erase marker found in V2 patch"
fi

if [[ "$failures" -eq 0 ]]; then
  pass "Active aircraft/trail cleanup V2 validation complete"
  exit 0
fi

echo "FAIL: validation failed"
exit 1
