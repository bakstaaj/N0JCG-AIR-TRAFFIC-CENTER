#!/usr/bin/env bash
# MSYS2-only guarded push/merge workflow for RTL-Windows-ADS-B-Tracker UI updates.
# Stages only web/app.js and web/app.css, validates feature markers, commits if needed,
# merges into main when run from a feature branch, pushes main, and pushes the release tag.

set -u

RELEASE_TAG="${1:-v1.3.1}"
REMOTE_NAME="${REMOTE_NAME:-origin}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-Release ${RELEASE_TAG} UI cleanup, active trail cleanup, and map popout kiosk defaults}"
TAG_MESSAGE="${TAG_MESSAGE:-Release ${RELEASE_TAG} UI cleanup and map popout kiosk defaults}"
SKIP_TAG="${SKIP_TAG:-0}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

pass() {
  echo "PASS: $*"
}

info() {
  echo "INFO: $*"
}

run() {
  "$@"
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    fail "command failed ($rc): $*"
  fi
}

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not inside a git repository"
cd "$repo_root" || fail "could not cd to repo root: $repo_root"

repo_name="$(basename "$repo_root")"
[[ "$repo_name" == "RTL-Windows-ADS-B-Tracker" || "$repo_name" == "RTL-WINDOWS-ADS-B-TRACKER" ]] || \
  info "repo folder is '$repo_name'; continuing because git repository is valid"

[[ -f web/app.js ]] || fail "missing web/app.js"
[[ -f web/app.css ]] || fail "missing web/app.css"

pass "repo root: $repo_root"

# Validate syntax first.
if command -v node >/dev/null 2>&1; then
  run node --check web/app.js
  pass "JavaScript syntax check passed"
else
  fail "node is not available in MSYS2 PATH; install/use Node before release validation"
fi

# Feature marker validation. These are intentionally string-based because prior patches are append-only/resilient.
grep -q 'ACTIVE_TRAIL_CLEANUP_V3_START' web/app.js || fail "missing active trail cleanup V3 marker in web/app.js"
grep -q 'MAP_POPOUT_FULLSCREEN_V1_START\|MAP_POPOUT_KIOSK_DEFAULTS_V2_START\|MAP_POPOUT_KIOSK_DEFAULTS_V3_START' web/app.js || fail "missing map popout/fullscreen marker in web/app.js"
grep -q 'MAP_POPOUT_KIOSK_DEFAULTS_V3_START' web/app.js || fail "missing map popout kiosk defaults V3 marker in web/app.js"
grep -q '60' web/app.js || fail "could not verify 60-mile kiosk default appears in web/app.js"
pass "feature markers verified"

# Run feature-specific validators if available.
if [[ -x tools/validate_active_trail_cleanup_v3.sh ]]; then
  run ./tools/validate_active_trail_cleanup_v3.sh
  pass "active trail cleanup V3 validator passed"
elif [[ -x tools/validate_active_trail_cleanup_v2.sh ]]; then
  run ./tools/validate_active_trail_cleanup_v2.sh
  pass "active trail cleanup V2 validator passed"
else
  info "no active trail cleanup validator found; marker validation already passed"
fi

if [[ -x tools/validate_map_popout_kiosk_defaults_v3.sh ]]; then
  run ./tools/validate_map_popout_kiosk_defaults_v3.sh
  pass "map popout kiosk defaults V3 validator passed"
elif [[ -x tools/validate_map_popout_kiosk_defaults_v2.sh ]]; then
  run ./tools/validate_map_popout_kiosk_defaults_v2.sh
  pass "map popout kiosk defaults V2 validator passed"
elif [[ -x tools/validate_map_popout_fullscreen_v1.sh ]]; then
  run ./tools/validate_map_popout_fullscreen_v1.sh
  pass "map popout fullscreen V1 validator passed"
else
  info "no map popout validator found; marker validation already passed"
fi

# Show current status before staging.
info "current branch: $(git rev-parse --abbrev-ref HEAD)"
git status -sb

# Guard against unrelated staged work.
if ! git diff --cached --quiet -- . ':!web/app.js' ':!web/app.css'; then
  fail "unrelated files are already staged. Unstage them before running this script. Only web/app.js and web/app.css may be staged."
fi

# Stage only intended source files.
run git add web/app.js web/app.css
pass "staged only web/app.js and web/app.css"

echo "--- Cached diff stat ---"
git diff --cached --stat || true

# Commit only if staged changes exist.
if git diff --cached --quiet; then
  pass "no source changes to commit; working source may already be committed"
else
  run git commit -m "$COMMIT_MESSAGE"
  pass "committed UI changes"
fi

source_branch="$(git rev-parse --abbrev-ref HEAD)"
source_sha="$(git rev-parse HEAD)"
pass "source branch/head: ${source_branch} ${source_sha}"

# Fetch remote refs.
run git fetch "$REMOTE_NAME" --prune
pass "fetched ${REMOTE_NAME}"

# Ensure main exists locally. If not, create tracking branch from origin/main.
if ! git show-ref --verify --quiet "refs/heads/${MAIN_BRANCH}"; then
  run git checkout -b "$MAIN_BRANCH" "${REMOTE_NAME}/${MAIN_BRANCH}"
else
  run git checkout "$MAIN_BRANCH"
fi
pass "checked out ${MAIN_BRANCH}"

# Fast-forward local main to origin/main before merge when possible.
if git show-ref --verify --quiet "refs/remotes/${REMOTE_NAME}/${MAIN_BRANCH}"; then
  run git merge --ff-only "${REMOTE_NAME}/${MAIN_BRANCH}"
  pass "${MAIN_BRANCH} fast-forwarded to ${REMOTE_NAME}/${MAIN_BRANCH}"
else
  info "remote ${REMOTE_NAME}/${MAIN_BRANCH} not found; continuing with local ${MAIN_BRANCH}"
fi

# Merge source branch if needed.
if [[ "$source_branch" != "$MAIN_BRANCH" ]]; then
  if git merge-base --is-ancestor "$source_sha" HEAD; then
    pass "source branch changes are already contained in ${MAIN_BRANCH}"
  else
    run git merge --no-ff "$source_sha" -m "Merge ${source_branch} into ${MAIN_BRANCH} for ${RELEASE_TAG}"
    pass "merged ${source_branch} into ${MAIN_BRANCH}"
  fi
else
  pass "changes are already on ${MAIN_BRANCH}"
fi

# Re-run core validation on main after merge.
run node --check web/app.js
grep -q 'ACTIVE_TRAIL_CLEANUP_V3_START' web/app.js || fail "post-merge missing active trail cleanup V3 marker"
grep -q 'MAP_POPOUT_KIOSK_DEFAULTS_V3_START' web/app.js || fail "post-merge missing map popout kiosk defaults V3 marker"
pass "post-merge validation passed on ${MAIN_BRANCH}"

# Push main.
run git push "$REMOTE_NAME" "$MAIN_BRANCH"
pass "pushed ${MAIN_BRANCH} to ${REMOTE_NAME}"

# Create/update tag locally only if it does not exist.
if [[ "$SKIP_TAG" == "1" ]]; then
  info "SKIP_TAG=1; skipping tag creation/push"
else
  if git rev-parse -q --verify "refs/tags/${RELEASE_TAG}" >/dev/null; then
    tag_sha="$(git rev-list -n 1 "$RELEASE_TAG")"
    head_sha="$(git rev-parse HEAD)"
    if [[ "$tag_sha" != "$head_sha" ]]; then
      fail "tag ${RELEASE_TAG} already exists at ${tag_sha}, but ${MAIN_BRANCH} HEAD is ${head_sha}. Choose a new tag or fix the existing tag intentionally."
    fi
    pass "local tag ${RELEASE_TAG} already points to ${MAIN_BRANCH} HEAD"
  else
    run git tag -a "$RELEASE_TAG" -m "$TAG_MESSAGE"
    pass "created tag ${RELEASE_TAG}"
  fi

  run git push "$REMOTE_NAME" "$RELEASE_TAG"
  pass "pushed tag ${RELEASE_TAG} to ${REMOTE_NAME}"
fi

# Final status checks.
run git fetch "$REMOTE_NAME" "$MAIN_BRANCH" --tags
local_main="$(git rev-parse "$MAIN_BRANCH")"
remote_main="$(git rev-parse "${REMOTE_NAME}/${MAIN_BRANCH}")"
[[ "$local_main" == "$remote_main" ]] || fail "local ${MAIN_BRANCH} (${local_main}) does not match ${REMOTE_NAME}/${MAIN_BRANCH} (${remote_main})"
pass "local ${MAIN_BRANCH} matches ${REMOTE_NAME}/${MAIN_BRANCH}: ${local_main}"

git status -sb

echo "--- Recent commits ---"
git log --oneline --decorate -8

if [[ "$SKIP_TAG" != "1" ]]; then
  echo "--- Tag ---"
  git show --no-patch --decorate --oneline "$RELEASE_TAG"
fi

pass "GitHub push/merge workflow complete"
echo "NEXT: If you want the GitHub release ZIP asset too, run the existing release/build script after this source push is confirmed."
