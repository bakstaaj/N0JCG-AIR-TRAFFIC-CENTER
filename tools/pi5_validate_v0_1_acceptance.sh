#!/usr/bin/env bash
# Run the V0.1 Pi initial-port acceptance suite and write one combined summary.
# This script intentionally runs only repository validation tools; it does not commit reports.
set -u

REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
WORK_DIR="${REPORT_DIR}/v0_1_acceptance_${STAMP}"
REPORT_PATH="${REPORT_DIR}/pi5_v0_1_acceptance_${STAMP}.txt"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

mkdir -p "$REPORT_DIR" "$WORK_DIR"

log() { printf '%s\n' "$*" | tee -a "$REPORT_PATH"; }
pass() { PASS_COUNT=$((PASS_COUNT+1)); log "PASS: $*"; }
warn() { WARN_COUNT=$((WARN_COUNT+1)); log "WARN: $*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); log "FAIL: $*"; }
section() { log ""; log "===== $* ====="; }

run_validator() {
  local label="$1"
  local script_path="$2"
  local required="$3"
  local output_file="$WORK_DIR/${script_path##*/}.out"

  section "$label"
  if [[ ! -x "$script_path" ]]; then
    if [[ "$required" == "required" ]]; then
      fail "missing or non-executable required validator: $script_path"
    else
      warn "missing optional validator: $script_path"
    fi
    return 1
  fi

  log "RUN: $script_path"
  "$script_path" 2>&1 | tee "$output_file" | tee -a "$REPORT_PATH"
  local rc=${PIPESTATUS[0]}

  if grep -q '^FINAL: PASS' "$output_file"; then
    pass "$label returned FINAL: PASS"
    return 0
  fi

  if [[ "$required" == "required" ]]; then
    fail "$label did not return FINAL: PASS (exit=$rc)"
    return 1
  fi

  warn "$label did not return FINAL: PASS (exit=$rc); optional for V0.1 acceptance"
  return 0
}

section "Environment"
log "PROJECT_ROOT=$(pwd)"
log "REPORT_PATH=$REPORT_PATH"
log "WORK_DIR=$WORK_DIR"
if [[ -f web/index.html && -d src/backend && -d tools ]]; then
  pass "repository root appears valid"
else
  fail "repository root does not look valid; run from PI-AIR-TRAFFIC-TRACKER root"
fi
for cmd in bash grep tee date; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$cmd available at $(command -v "$cmd")"
  else
    fail "$cmd is required"
  fi
done

section "Required V0.1 acceptance validators"
run_validator "Systemd service validation" "./tools/pi5_validate_systemd_service.sh" "required"
run_validator "ADS-B fresh-start/stale-JSON validation" "./tools/pi5_validate_readsb_fresh_start.sh" "required"
run_validator "Live functional UI/API validation" "./tools/pi5_validate_live_functional.sh" "required"
run_validator "Active NOAA/Airband validation" "./tools/pi5_validate_active_noaa_airband.sh" "required"

section "Optional catalog validation"
if [[ -s runtime/settings/faa_airband_catalog.json ]]; then
  run_validator "FAA Airband catalog validation" "./tools/pi5_validate_airband_catalog.sh" "optional"
else
  warn "FAA Airband catalog runtime file is missing; acceptable for V0.1 fast_spectrum scanning, but traditional catalog channel lists remain unavailable"
fi

section "Acceptance summary"
log "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
log "Report path: $REPORT_PATH"
log "Work dir: $WORK_DIR"
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  log "FINAL: PASS"
  exit 0
fi
log "FINAL: FAIL"
exit 1
