#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-v1.3.1}"
COMMIT_MSG="Keep stale aircraft off active map display"
RELEASE_TITLE="$VERSION Active aircraft display cleanup"
RELEASE_NOTES="Release $VERSION keeps stale ADS-B aircraft records off the active aircraft table and active map display. Active markers and live trail segments clear when aircraft become inactive, while stored trail history remains restorable through Restore History."

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

[[ -f web/app.js ]] || fail "web/app.js not found. Run from the repository root."
[[ -x tools/validate_active_trail_cleanup_v2.sh ]] || fail "tools/validate_active_trail_cleanup_v2.sh is missing or not executable."

tools/validate_active_trail_cleanup_v2.sh

git add web/app.js
if git diff --cached --quiet; then
  pass "no staged web/app.js changes to commit"
else
  git diff --cached --stat
  git commit -m "$COMMIT_MSG"
fi

git push

if git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
  pass "tag $VERSION already exists locally"
else
  git tag -a "$VERSION" -m "Release $VERSION active aircraft display cleanup"
  pass "created local tag $VERSION"
fi

git push origin "$VERSION"

[[ -x tools/build_windows_service_release.sh ]] || fail "tools/build_windows_service_release.sh is missing or not executable."
tools/build_windows_service_release.sh "$VERSION"

ZIP="/c/Users/jim/Downloads/RTL-ADS-B-Tracker-Windows-Service-${VERSION}.zip"
[[ -f "$ZIP" ]] || fail "release ZIP not found: $ZIP"

if ! command -v gh >/dev/null 2>&1; then
  fail "gh is not installed or not in PATH; release ZIP built but not uploaded: $ZIP"
fi

if gh release view "$VERSION" >/dev/null 2>&1; then
  gh release upload "$VERSION" "$ZIP" --clobber
  pass "uploaded release asset to existing GitHub release $VERSION"
else
  gh release create "$VERSION" "$ZIP" --title "$RELEASE_TITLE" --notes "$RELEASE_NOTES"
  pass "created GitHub release $VERSION and uploaded ZIP"
fi

pass "release workflow complete for $VERSION"
