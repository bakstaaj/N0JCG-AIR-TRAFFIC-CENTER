#!/usr/bin/env bash
# Validate Phase 1 weather radar overlay source changes.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

printf '\nChecking JavaScript syntax...\n'
node --check web/app.js

printf '\nChecking weather radar markers...\n'
grep -n 'BEGIN Phase 1 weather radar overlay\|weatherRadarControls\|nexrad-n0q\|BEGIN Phase 1 weather radar overlay controls' web/app.js web/app.css

printf '\nChanged files:\n'
git status -sb

printf '\nDiff stat:\n'
git diff --stat -- web/app.js web/app.css

printf '\nPASS: Phase 1 weather radar overlay source validation completed.\n'
