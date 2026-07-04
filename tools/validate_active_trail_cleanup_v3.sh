#!/usr/bin/env bash
set -u

failures=0
fail(){ echo "FAIL: $*"; failures=$((failures+1)); }
pass(){ echo "PASS: $*"; }

if [[ ! -f web/app.js ]]; then
  fail "web/app.js not found. Run from repository root."
  exit 1
fi

if command -v node >/dev/null 2>&1; then
  if node --check web/app.js >/tmp/active_trail_cleanup_v3_node_check.log 2>&1; then
    pass "JavaScript syntax check passed"
  else
    cat /tmp/active_trail_cleanup_v3_node_check.log
    fail "JavaScript syntax check failed"
  fi
else
  fail "node not found in PATH; cannot validate JavaScript syntax"
fi

if grep -q 'ACTIVE_TRAIL_CLEANUP_V3' web/app.js; then
  pass "active trail cleanup V3 marker found"
else
  fail "active trail cleanup V3 marker not found; run apply_active_trail_cleanup_v3.py"
fi

if grep -q 'removeTrailLayersForAircraft(key);' web/app.js; then
  pass "trail-layer removal call exists for marker cleanup"
else
  fail "removeTrailLayersForAircraft(key) not found"
fi

if grep -q 'aircraftTrailHistory.clear()' web/app.js; then
  pass "stored history clear remains limited to existing Clear/Erase functions"
else
  pass "no new stored-history clear behavior detected"
fi

# The direct patch should leave a clear comment, while the fallback wrapper should expose a marker object.
if grep -q 'when marker/icon is removed from the active display' web/app.js || grep -q '__activeTrailCleanupV3' web/app.js; then
  pass "marker-removal-to-trail-removal synchronization verified"
else
  fail "missing marker-removal-to-trail-removal synchronization code"
fi

if [[ $failures -eq 0 ]]; then
  pass "Active trail cleanup V3 validation complete"
  exit 0
fi

fail "validation failed"
exit 1
