#!/usr/bin/env bash
set -u

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

pass() {
  echo "PASS: $*"
}

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || fail "Run from inside the RTL-Windows-ADS-B-Tracker repository"

[ -f web/app.js ] || fail "web/app.js not found"

if [ -x tools/validate_active_trail_cleanup_v1.sh ]; then
  ./tools/validate_active_trail_cleanup_v1.sh || fail "validation failed"
else
  fail "tools/validate_active_trail_cleanup_v1.sh not found or not executable"
fi

OUT="/c/Users/jim/Downloads/RTL-Windows-ADS-B-Tracker-active-trail-cleanup-v1-web-assets.zip"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

mkdir -p "$TMPDIR/web"
cp web/app.js "$TMPDIR/web/app.js"

(
  cd "$TMPDIR" || exit 1
  zip -qr "$OUT" web/app.js
) || fail "zip failed"

[ -f "$OUT" ] || fail "asset zip was not created"
pass "Wrote $OUT"
