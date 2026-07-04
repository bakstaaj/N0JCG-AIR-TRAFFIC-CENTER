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

TAG="${1:-v1.3.1}"
TITLE="${TAG} Active aircraft map cleanup"
COMMIT_MESSAGE="Clear inactive aircraft trails from active map"

case "$TAG" in
  v*) ;;
  *) fail "Release tag should start with v, for example v1.3.1" ;;
esac

[ -x tools/validate_active_trail_cleanup_v1.sh ] || fail "tools/validate_active_trail_cleanup_v1.sh missing or not executable"
./tools/validate_active_trail_cleanup_v1.sh || fail "validation failed"

git status -sb

git add web/app.js || fail "git add web/app.js failed"

if git diff --cached --quiet -- web/app.js; then
  echo "INFO: web/app.js has no staged changes; using existing commit for release."
else
  git commit -m "$COMMIT_MESSAGE" || fail "git commit failed"
fi

git push || fail "git push failed"

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "INFO: local tag $TAG already exists"
else
  git tag -a "$TAG" -m "Release $TAG active aircraft map cleanup" || fail "git tag failed"
fi

git push origin "$TAG" || fail "git push origin $TAG failed"

[ -x tools/build_windows_service_release.sh ] || fail "tools/build_windows_service_release.sh missing or not executable"
./tools/build_windows_service_release.sh "$TAG" || fail "release package build failed"

ZIP="/c/Users/jim/Downloads/RTL-ADS-B-Tracker-Windows-Service-${TAG}.zip"
[ -f "$ZIP" ] || fail "expected release zip not found: $ZIP"

if ! command -v gh >/dev/null 2>&1; then
  fail "GitHub CLI gh not found. Install/login gh or upload $ZIP manually."
fi

gh auth status >/dev/null 2>&1 || fail "gh auth status failed"

NOTES="Release ${TAG} clears inactive aircraft markers and active trail display segments from the live map/table while preserving stored trail history for Restore History. It keeps aircraft role/startup and weather radar behavior from prior releases."

if gh release view "$TAG" >/dev/null 2>&1; then
  gh release upload "$TAG" "$ZIP" --clobber || fail "gh release upload failed"
else
  gh release create "$TAG" "$ZIP" --title "$TITLE" --notes "$NOTES" || fail "gh release create failed"
fi

gh release view "$TAG" || fail "gh release view failed"
pass "Committed, tagged, built, and uploaded release $TAG"
