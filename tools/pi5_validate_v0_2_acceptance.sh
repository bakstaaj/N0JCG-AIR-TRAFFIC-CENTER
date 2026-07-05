#!/usr/bin/env bash
# Validate the V0.2 UAT + unified traffic-source acceptance chain on the Pi.
set -u

PROJECT_ROOT="$(pwd)"
REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
WORK_DIR="${REPORT_DIR}/v0_2_acceptance_${STAMP}"
REPORT_PATH="${REPORT_DIR}/pi5_v0_2_acceptance_${STAMP}.txt"
BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://${PI_AIR_TRAFFIC_HOST:-127.0.0.1}:${PI_AIR_TRAFFIC_PORT:-8090}}"
SERVICE_NAME="${PI_AIR_TRAFFIC_SERVICE:-pi-air-traffic-tracker.service}"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

mkdir -p "$REPORT_DIR" "$WORK_DIR"
log(){ printf '%s\n' "$*" | tee -a "$REPORT_PATH"; }
section(){ log ""; log "===== $* ====="; }
pass(){ PASS_COUNT=$((PASS_COUNT+1)); log "PASS: $*"; }
warn(){ WARN_COUNT=$((WARN_COUNT+1)); log "WARN: $*"; }
fail(){ FAIL_COUNT=$((FAIL_COUNT+1)); log "FAIL: $*"; }

delay(){ sleep "${1:-1}"; }

json_get(){
  local file="$1" expr="$2"
  python3 - "$file" "$expr" <<'PY_JSON_GET_V02_ACCEPTANCE'
import json, sys
path, expr = sys.argv[1], sys.argv[2]
try:
    value = json.load(open(path, encoding='utf-8'))
except Exception:
    print('')
    raise SystemExit(0)
for part in expr.split('.'):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break
if isinstance(value, bool):
    print('true' if value else 'false')
elif value is None:
    print('')
else:
    print(value)
PY_JSON_GET_V02_ACCEPTANCE
}

write_diag(){
  {
    echo "--- systemctl status $SERVICE_NAME ---"
    systemctl status "$SERVICE_NAME" --no-pager -l || true
    echo
    echo "--- recent journal $SERVICE_NAME ---"
    journalctl -u "$SERVICE_NAME" --no-pager -n 80 || true
    echo
    echo "--- listening sockets 8090 ---"
    ss -ltnp 2>/dev/null | grep ':8090' || true
  } > "$WORK_DIR/service_diagnostics.txt" 2>&1
  log "Diagnostics: $WORK_DIR/service_diagnostics.txt"
}

wait_for_api(){
  local timeout_seconds="${1:-45}"
  local deadline=$((SECONDS + timeout_seconds))
  local target="$WORK_DIR/api_status_ready.json"
  while (( SECONDS < deadline )); do
    if curl -sS --max-time 4 "$BASE_URL/api/status" -o "$target" >/dev/null 2>&1 && python3 -m json.tool "$target" >/dev/null 2>&1; then
      pass "/api/status returned JSON after service readiness wait"
      return 0
    fi
    delay 1
  done
  fail "/api/status did not become ready at $BASE_URL within ${timeout_seconds}s"
  write_diag
  return 1
}

run_subvalidator(){
  local label="$1" script="$2" mode="${3:-required}"
  section "$label"
  if [[ ! -x "$script" ]]; then
    if [[ "$mode" == "optional" ]]; then
      warn "$script missing or not executable; skipping optional check"
      return 0
    fi
    fail "$script missing or not executable"
    return 1
  fi
  local out="$WORK_DIR/$(basename "$script" .sh).out"
  log "RUNNING: $script"
  if "$script" > "$out" 2>&1; then
    cat "$out" >> "$REPORT_PATH"
    pass "$label completed successfully"
    if grep -q '^FINAL: PASS' "$out"; then pass "$label reported FINAL: PASS"; else warn "$label completed but FINAL: PASS marker was not found"; fi
    return 0
  fi
  cat "$out" >> "$REPORT_PATH"
  fail "$label failed; see $out"
  return 1
}

section "Environment"
log "PROJECT_ROOT=$PROJECT_ROOT"
log "BASE_URL=$BASE_URL"
log "SERVICE_NAME=$SERVICE_NAME"
if [[ -f README.md && -d src/backend && -d web && -d tools ]]; then pass "repository root appears valid"; else fail "run from repository root"; fi
for cmd in python3 curl systemctl journalctl ss git; do
  if command -v "$cmd" >/dev/null 2>&1; then pass "$cmd available at $(command -v "$cmd")"; else fail "$cmd is required"; fi
done

section "Static V0.2 acceptance checks"
for path in \
  tools/pi5_validate_v0_1_acceptance.sh \
  tools/pi5_validate_uat_978_capability.sh \
  tools/pi5_validate_uat_decoder_tooling.sh \
  tools/pi5_validate_uat_backend_api.sh \
  tools/pi5_validate_traffic_source_ui_merge.sh \
  src/backend/pi_air_traffic_backend.py \
  web/index.html web/app.js web/app.css \
  docs/guardrails/PI_TRAFFIC_SOURCE_MERGE_GUARDRAIL.md; do
  [[ -e "$path" ]] && pass "$path exists" || fail "$path missing"
done

grep -q 'trafficSource1090' web/index.html && pass "1090 traffic source switch is present" || fail "1090 traffic source switch missing"
grep -q 'trafficSourceUat978' web/index.html && pass "978 UAT traffic source switch is present" || fail "978 UAT traffic source switch missing"
grep -q 'menu refresh pause' web/app.js || grep -q 'pause.*refresh.*menu\|menu.*refresh.*pause' web/app.js && pass "UI contains menu refresh pause logic" || fail "UI menu refresh pause logic missing"
grep -q 'socket.timeout' src/backend/pi_air_traffic_backend.py && pass "UAT collector handles socket timeout" || fail "UAT collector socket timeout handling missing"
grep -q 'cannot read from timed out object' src/backend/pi_air_traffic_backend.py && fail "UAT collector still contains timed-out object error string" || pass "UAT collector does not hard-code timed-out object as an error"
python3 -m py_compile src/backend/pi_air_traffic_backend.py && pass "Python syntax valid: src/backend/pi_air_traffic_backend.py" || fail "Python syntax failed: src/backend/pi_air_traffic_backend.py"
python3 -m json.tool runtime/settings/pi_air_traffic_hardware_roles.pi5-flycatcher-serials.json >/dev/null 2>&1 && pass "hardware roles JSON validates" || warn "hardware roles JSON not present or not valid at runtime/settings"

section "Service readiness"
if systemctl is-active --quiet "$SERVICE_NAME"; then pass "$SERVICE_NAME is active"; else fail "$SERVICE_NAME is not active"; fi
wait_for_api 45 || true

# Run the already validated chain. V0.1 is optional here because it can be a longer full-system test;
# set RUN_V0_1_BASELINE=1 to include it inside this acceptance chain.
RUN_V0_1_BASELINE="${RUN_V0_1_BASELINE:-${PI_AIR_TRAFFIC_RUN_V0_1_ACCEPTANCE:-0}}"
if [[ "$RUN_V0_1_BASELINE" == "1" ]]; then
  run_subvalidator "V0.1 baseline acceptance" "./tools/pi5_validate_v0_1_acceptance.sh" required || true
else
  section "V0.1 baseline acceptance"
  warn "skipped V0.1 baseline acceptance by default; set RUN_V0_1_BASELINE=1 to include it"
fi

run_subvalidator "UAT 978 hardware capability" "./tools/pi5_validate_uat_978_capability.sh" required || true
run_subvalidator "UAT dump978 decoder tooling" "./tools/pi5_validate_uat_decoder_tooling.sh" required || true
run_subvalidator "UAT backend API controls" "./tools/pi5_validate_uat_backend_api.sh" required || true
run_subvalidator "Traffic source UI and unified merge" "./tools/pi5_validate_traffic_source_ui_merge.sh" required || true

section "Post-chain unified source sanity"
wait_for_api 45 || true
TRAFFIC_JSON="$WORK_DIR/final_traffic_sources.json"
AIRCRAFT_JSON="$WORK_DIR/final_aircraft.json"
UAT_STATUS_JSON="$WORK_DIR/final_uat_status.json"

if curl -sS --max-time 15 "$BASE_URL/api/settings/traffic-sources" -o "$TRAFFIC_JSON" && python3 -m json.tool "$TRAFFIC_JSON" >/dev/null 2>&1; then
  pass "traffic source settings API returns JSON after full chain"
  log "FINAL_ADSB_ENABLED=$(json_get "$TRAFFIC_JSON" adsb_1090_enabled)"
  log "FINAL_UAT_ENABLED=$(json_get "$TRAFFIC_JSON" uat_978_enabled)"
else
  fail "traffic source settings API failed after full chain"
fi

if curl -sS --max-time 20 "$BASE_URL/api/aircraft.json" -o "$AIRCRAFT_JSON" && python3 -m json.tool "$AIRCRAFT_JSON" >/dev/null 2>&1; then
  pass "unified aircraft feed returns JSON after full chain"
  log "FINAL_SOURCE_COUNTS_ADSB=$(json_get "$AIRCRAFT_JSON" source_counts.adsb_1090)"
  log "FINAL_SOURCE_COUNTS_UAT=$(json_get "$AIRCRAFT_JSON" source_counts.uat_978)"
  pass "978 UAT aircraft count may be zero when no live UAT traffic is present"
else
  fail "unified aircraft feed failed after full chain"
fi

if curl -sS --max-time 15 "$BASE_URL/api/uat/status" -o "$UAT_STATUS_JSON" && python3 -m json.tool "$UAT_STATUS_JSON" >/dev/null 2>&1; then
  pass "UAT status API returns JSON after full chain"
  UAT_ERROR="$(json_get "$UAT_STATUS_JSON" collector_error)"
  if [[ "$UAT_ERROR" == *"timed out object"* ]]; then
    fail "UAT collector still reports timed-out object error"
  elif [[ -n "$UAT_ERROR" ]]; then
    warn "UAT collector reports non-timeout error: $UAT_ERROR"
  else
    pass "UAT collector idle state is non-fatal"
  fi
else
  fail "UAT status API failed after full chain"
fi

section "Evidence bundle"
log "Acceptance report: $REPORT_PATH"
log "Work dir: $WORK_DIR"
if command -v git >/dev/null 2>&1; then
  git rev-parse HEAD > "$WORK_DIR/git_head.txt" 2>/dev/null || true
  git status --short > "$WORK_DIR/git_status_short.txt" 2>/dev/null || true
  log "Git head: $(cat "$WORK_DIR/git_head.txt" 2>/dev/null || echo unknown)"
fi

section "Summary"
log "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
log "Report path: $REPORT_PATH"
log "Work dir: $WORK_DIR"
if [[ "$FAIL_COUNT" -eq 0 ]]; then log "FINAL: PASS"; exit 0; else log "FINAL: FAIL"; exit 1; fi
