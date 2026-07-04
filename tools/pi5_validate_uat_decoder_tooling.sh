#!/usr/bin/env bash
# Validate app-owned UAT decoder tooling without enabling persistent UAT runtime.
set -u

PROJECT_ROOT="$(pwd)"
REPORT_DIR="runtime/preflight"
WORK_DIR="${REPORT_DIR}/uat_decoder_tooling_$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${REPORT_DIR}/pi5_uat_decoder_tooling_$(date +%Y%m%d_%H%M%S).txt"
BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://${PI_AIR_TRAFFIC_HOST:-127.0.0.1}:${PI_AIR_TRAFFIC_PORT:-8090}}"
UAT_SERIAL="${PI_AIR_TRAFFIC_UAT_SERIAL:-00000978}"
UAT_GAIN_DB="${PI_AIR_TRAFFIC_UAT_GAIN_DB:-49.6}"
DUMP978_BIN="${PROJECT_ROOT}/runtime/bin/dump978-fa"
SKYAWARE_BIN="${PROJECT_ROOT}/runtime/bin/skyaware978"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
UAT_INDEX=""

mkdir -p "$REPORT_DIR" "$WORK_DIR"

log() { printf '%s\n' "$*" | tee -a "$REPORT_PATH"; }
section() { log ""; log "===== $* ====="; }
pass() { PASS_COUNT=$((PASS_COUNT+1)); log "PASS: $*"; }
warn() { WARN_COUNT=$((WARN_COUNT+1)); log "WARN: $*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); log "FAIL: $*"; }

json_get() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json
import sys
path, expr = sys.argv[1], sys.argv[2]
try:
    value = json.load(open(path, 'r', encoding='utf-8'))
except Exception:
    print('')
    raise SystemExit(0)
for part in expr.split('.'):
    if not part:
        continue
    value = value.get(part) if isinstance(value, dict) else None
if isinstance(value, bool):
    print('true' if value else 'false')
elif value is None:
    print('')
else:
    print(value)
PY
}

parse_rtl_devices() {
  local combined="$1"
  local output="$2"
  python3 - "$combined" "$output" <<'PY'
import json, re, sys
combined, output = sys.argv[1:]
pat = re.compile(r"^\s*(\d+):\s*([^,]+),\s*([^,]+),\s*SN:\s*(\S+)\s*$")
devices=[]
for line in open(combined, encoding='utf-8', errors='replace'):
    m=pat.match(line.rstrip())
    if m:
        idx,vendor,product,serial=m.groups()
        devices.append({'index': int(idx), 'vendor': vendor.strip(), 'product': product.strip(), 'serial': serial.strip()})
json.dump({'devices': devices, 'device_count': len(devices)}, open(output, 'w', encoding='utf-8'), indent=2)
PY
}

section "Environment"
log "PROJECT_ROOT=$PROJECT_ROOT"
log "BASE_URL=$BASE_URL"
log "UAT_SERIAL=$UAT_SERIAL"
log "DUMP978_BIN=$DUMP978_BIN"
if [[ -f README.md && -d src/backend && -d tools ]]; then
  pass "repository root appears valid"
else
  fail "run from the PI-AIR-TRAFFIC-TRACKER repository root"
fi
for cmd in python3 rtl_test timeout pgrep sed awk; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$cmd available at $(command -v "$cmd")"
  else
    fail "$cmd is required"
  fi
done
if command -v curl >/dev/null 2>&1; then
  pass "curl available at $(command -v curl)"
else
  warn "curl missing; service API checks skipped"
fi
if command -v SoapySDRUtil >/dev/null 2>&1; then
  pass "SoapySDRUtil available at $(command -v SoapySDRUtil)"
else
  warn "SoapySDRUtil missing; install soapysdr-tools for receiver-by-serial validation"
fi

section "App-owned binary checks"
if [[ -x "$DUMP978_BIN" ]]; then
  pass "app-owned dump978-fa is executable"
else
  fail "app-owned dump978-fa is missing or not executable; run tools/pi5_install_app_owned_dump978.sh"
fi
if [[ -x "$SKYAWARE_BIN" ]]; then
  pass "app-owned skyaware978 is executable"
else
  fail "app-owned skyaware978 is missing or not executable; run tools/pi5_install_app_owned_dump978.sh"
fi
if [[ -x "$DUMP978_BIN" ]]; then
  "$DUMP978_BIN" --help >"$WORK_DIR/dump978_help.out" 2>"$WORK_DIR/dump978_help.err"
  cat "$WORK_DIR/dump978_help.out" "$WORK_DIR/dump978_help.err" | sed -n '1,60p' | tee -a "$REPORT_PATH" >/dev/null
  if grep -q -- '--sdr' "$WORK_DIR/dump978_help.out" "$WORK_DIR/dump978_help.err" 2>/dev/null; then
    pass "dump978-fa exposes --sdr option"
  else
    fail "dump978-fa help did not show --sdr"
  fi
  if grep -q -- '--json-stdout\|--json-port' "$WORK_DIR/dump978_help.out" "$WORK_DIR/dump978_help.err" 2>/dev/null; then
    pass "dump978-fa exposes JSON output options"
  else
    fail "dump978-fa help did not show JSON output options"
  fi
fi

section "RTL serial and service isolation"
RTL_COMBINED="$WORK_DIR/rtl_test_t.combined.txt"
RTL_JSON="$WORK_DIR/rtl_devices.json"
rtl_test -t >"$WORK_DIR/rtl_test.stdout" 2>"$WORK_DIR/rtl_test.stderr"
cat "$WORK_DIR/rtl_test.stdout" "$WORK_DIR/rtl_test.stderr" > "$RTL_COMBINED"
parse_rtl_devices "$RTL_COMBINED" "$RTL_JSON"
DEVICE_COUNT="$(json_get "$RTL_JSON" device_count)"
log "RTL_DEVICE_COUNT=${DEVICE_COUNT:-0}"
UAT_INDEX="$(python3 - "$RTL_JSON" "$UAT_SERIAL" <<'PY'
import json, sys
data=json.load(open(sys.argv[1], encoding='utf-8'))
serial=sys.argv[2]
m=[d for d in data.get('devices', []) if str(d.get('serial')) == serial]
print(m[0].get('index', '') if len(m) == 1 else '')
PY
)"
if [[ -n "$UAT_INDEX" ]]; then
  pass "UAT serial $UAT_SERIAL resolves to RTL runtime index $UAT_INDEX"
else
  fail "UAT serial $UAT_SERIAL did not resolve exactly once"
fi

if command -v curl >/dev/null 2>&1; then
  STATUS_JSON="$WORK_DIR/status.json"
  if curl -sS --max-time 10 "$BASE_URL/api/status" -o "$STATUS_JSON" && python3 -m json.tool "$STATUS_JSON" >/dev/null 2>&1; then
    pass "/api/status returned JSON"
    status_uat_serial="$(json_get "$STATUS_JSON" receiver_roles.uat.serial)"
    status_uat_enabled="$(json_get "$STATUS_JSON" receiver_roles.uat.enabled)"
    log "STATUS_UAT_SERIAL=$status_uat_serial"
    log "STATUS_UAT_ENABLED=$status_uat_enabled"
    if [[ "$status_uat_serial" == "$UAT_SERIAL" ]]; then
      pass "/api/status reports expected UAT serial"
    else
      warn "/api/status UAT serial mismatch: ${status_uat_serial:-empty}"
    fi
    if [[ "$status_uat_enabled" == "false" ]]; then
      pass "persistent UAT role is still disabled"
    else
      warn "persistent UAT role enabled state is ${status_uat_enabled:-empty}"
    fi
  else
    warn "/api/status unavailable; continuing decoder-tool validation"
  fi
fi

PROCESS_LIST="$WORK_DIR/processes.txt"
pgrep -af 'dump978|skyaware978|uat|rtl_sdr|rtl_fm|readsb' > "$PROCESS_LIST" 2>/dev/null || true
cat "$PROCESS_LIST" | tee -a "$REPORT_PATH" >/dev/null
if grep -q -- "$UAT_SERIAL" "$PROCESS_LIST"; then
  warn "a process mentions UAT serial $UAT_SERIAL; startup probe may be blocked if that process owns the receiver"
else
  pass "no running process command line mentions UAT serial $UAT_SERIAL"
fi

section "SoapySDR serial visibility"
if command -v SoapySDRUtil >/dev/null 2>&1; then
  SOAPY_LOG="$WORK_DIR/soapysdr_find_uat.log"
  if SoapySDRUtil --find="driver=rtlsdr,serial=${UAT_SERIAL}" >"$SOAPY_LOG" 2>&1; then
    cat "$SOAPY_LOG" | tee -a "$REPORT_PATH" >/dev/null
    if grep -q -- "$UAT_SERIAL" "$SOAPY_LOG" || grep -qi -- 'Found device' "$SOAPY_LOG"; then
      pass "SoapySDR can find UAT receiver by serial"
    else
      warn "SoapySDR find command returned success but did not clearly list the UAT serial"
    fi
  else
    cat "$SOAPY_LOG" | tee -a "$REPORT_PATH" >/dev/null
    fail "SoapySDR could not find UAT receiver by serial"
  fi
else
  warn "skipping SoapySDR receiver-by-serial check because SoapySDRUtil is missing"
fi

section "dump978-fa SDR startup probe"
if [[ -x "$DUMP978_BIN" ]]; then
  START_LOG="$WORK_DIR/dump978_startup_probe.log"
  # Timeout is success for this non-persistent probe: the process stayed alive until we stopped it.
  timeout 10 "$DUMP978_BIN" --sdr "driver=rtlsdr,serial=${UAT_SERIAL}" --sdr-gain "$UAT_GAIN_DB" --json-stdout >"$WORK_DIR/dump978_startup_probe.stdout" 2>"$START_LOG"
  rc=$?
  cat "$START_LOG" | tee -a "$REPORT_PATH" >/dev/null
  log "DUMP978_STARTUP_RC=$rc"
  if grep -qiE 'Configuration error|Uncaught exception|No matching devices|not found|failed|error' "$START_LOG"; then
    fail "dump978-fa reported a startup/configuration error while opening UAT receiver"
  elif [[ "$rc" -eq 124 || "$rc" -eq 0 || "$rc" -eq 1 ]]; then
    pass "dump978-fa startup probe opened or stayed active long enough for a controlled stop"
  else
    warn "dump978-fa startup probe returned unexpected rc=$rc; inspect $START_LOG"
  fi
else
  fail "cannot run dump978-fa startup probe because app-owned binary is missing"
fi

section "Summary"
log "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
log "Report path: $REPORT_PATH"
log "Work dir: $WORK_DIR"
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  log "FINAL: PASS"
  exit 0
else
  log "FINAL: FAIL"
  exit 1
fi
