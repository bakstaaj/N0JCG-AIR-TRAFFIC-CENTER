#!/usr/bin/env bash
# Probe Pi UAT 978 MHz hardware/tool readiness without starting persistent services.
set -u

PROJECT_ROOT="$(pwd)"
REPORT_DIR="runtime/preflight"
WORK_DIR="${REPORT_DIR}/uat_978_capability_$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${REPORT_DIR}/pi5_uat_978_capability_$(date +%Y%m%d_%H%M%S).txt"
BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://${PI_AIR_TRAFFIC_HOST:-127.0.0.1}:${PI_AIR_TRAFFIC_PORT:-8090}}"
UAT_SERIAL="${PI_AIR_TRAFFIC_UAT_SERIAL:-00000978}"
ADSB_SERIAL="${PI_AIR_TRAFFIC_ADSB_SERIAL:-00001090}"
AUDIO_SERIAL="${PI_AIR_TRAFFIC_AUDIO_SERIAL:-00000162}"
UAT_FREQUENCY_HZ="${PI_AIR_TRAFFIC_UAT_FREQUENCY_HZ:-978000000}"
UAT_SAMPLE_RATE="${PI_AIR_TRAFFIC_UAT_SAMPLE_RATE:-2083334}"
UAT_GAIN_DB="${PI_AIR_TRAFFIC_UAT_GAIN_DB:-49.6}"
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
    with open(path, 'r', encoding='utf-8') as handle:
        value = json.load(handle)
except Exception:
    print('')
    raise SystemExit(0)
for part in expr.split('.'):
    if not part:
        continue
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
PY
}

parse_rtl_devices() {
  local combined="$1"
  local output="$2"
  python3 - "$combined" "$output" <<'PY'
import json
import re
import sys
combined_path, output_path = sys.argv[1], sys.argv[2]
pattern = re.compile(r"^\s*(\d+):\s*([^,]+),\s*([^,]+),\s*SN:\s*(\S+)\s*$")
devices = []
for line in open(combined_path, 'r', encoding='utf-8', errors='replace'):
    match = pattern.match(line.rstrip())
    if match:
        index, vendor, product, serial = match.groups()
        devices.append({
            'index': int(index),
            'vendor': vendor.strip(),
            'product': product.strip(),
            'serial': serial.strip(),
        })
json.dump({'devices': devices, 'device_count': len(devices)}, open(output_path, 'w', encoding='utf-8'), indent=2)
PY
}

section "Environment"
log "PROJECT_ROOT=$PROJECT_ROOT"
log "BASE_URL=$BASE_URL"
log "UAT_SERIAL=$UAT_SERIAL"
log "UAT_FREQUENCY_HZ=$UAT_FREQUENCY_HZ"
log "UAT_SAMPLE_RATE=$UAT_SAMPLE_RATE"
log "UAT_GAIN_DB=$UAT_GAIN_DB"
if [[ -f README.md && -d src/backend && -d tools ]]; then
  pass "repository root appears valid"
else
  fail "run from the PI-AIR-TRAFFIC-TRACKER repository root"
fi
for cmd in python3 rtl_test timeout pgrep sed awk; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$cmd available at $(command -v "$cmd")"
  else
    fail "$cmd is required for the UAT probe"
  fi
done
if command -v curl >/dev/null 2>&1; then
  pass "curl available at $(command -v curl)"
else
  warn "curl is not available; service status/API checks will be skipped"
fi
if command -v rtl_sdr >/dev/null 2>&1; then
  pass "rtl_sdr available at $(command -v rtl_sdr)"
else
  warn "rtl_sdr is not available; 978 MHz raw capture check will be skipped"
fi

section "RTL-SDR serial inventory"
RTL_STDOUT="$WORK_DIR/rtl_test_t.stdout"
RTL_STDERR="$WORK_DIR/rtl_test_t.stderr"
RTL_COMBINED="$WORK_DIR/rtl_test_t.combined.txt"
RTL_JSON="$WORK_DIR/rtl_devices.json"
rtl_test -t >"$RTL_STDOUT" 2>"$RTL_STDERR"
rtl_rc=$?
cat "$RTL_STDOUT" "$RTL_STDERR" > "$RTL_COMBINED"
if [[ "$rtl_rc" -eq 0 || -s "$RTL_COMBINED" ]]; then
  pass "rtl_test -t produced receiver inventory output"
else
  fail "rtl_test -t did not produce receiver inventory output"
fi
parse_rtl_devices "$RTL_COMBINED" "$RTL_JSON"
cat "$RTL_JSON" | tee -a "$REPORT_PATH" >/dev/null
DEVICE_COUNT="$(json_get "$RTL_JSON" device_count)"
log "RTL_DEVICE_COUNT=${DEVICE_COUNT:-0}"
if [[ "${DEVICE_COUNT:-0}" =~ ^[0-9]+$ && "${DEVICE_COUNT:-0}" -ge 3 ]]; then
  pass "at least three RTL devices are visible"
else
  warn "fewer than three RTL devices were parsed; expected ADS-B, NOAA/Airband, and UAT"
fi

python3 - "$RTL_JSON" "$UAT_SERIAL" "$ADSB_SERIAL" "$AUDIO_SERIAL" "$WORK_DIR/uat_role.json" <<'PY'
import json
import sys
rtl_json, uat_serial, adsb_serial, audio_serial, output = sys.argv[1:]
data = json.load(open(rtl_json, 'r', encoding='utf-8'))
devices = data.get('devices', [])
serials = [str(device.get('serial')) for device in devices]
result = {
    'ok': False,
    'uat_serial': uat_serial,
    'adsb_serial': adsb_serial,
    'audio_serial': audio_serial,
    'duplicate_serials': sorted({serial for serial in serials if serials.count(serial) > 1}),
    'uat_matches': [device for device in devices if str(device.get('serial')) == uat_serial],
    'adsb_matches': [device for device in devices if str(device.get('serial')) == adsb_serial],
    'audio_matches': [device for device in devices if str(device.get('serial')) == audio_serial],
}
result['ok'] = len(result['uat_matches']) == 1 and not result['duplicate_serials']
json.dump(result, open(output, 'w', encoding='utf-8'), indent=2)
PY
cat "$WORK_DIR/uat_role.json" | tee -a "$REPORT_PATH" >/dev/null
DUPES="$(json_get "$WORK_DIR/uat_role.json" duplicate_serials)"
UAT_MATCH_COUNT="$(python3 - "$WORK_DIR/uat_role.json" <<'PY'
import json, sys
print(len(json.load(open(sys.argv[1], encoding='utf-8')).get('uat_matches', [])))
PY
)"
if [[ -n "$DUPES" && "$DUPES" != "[]" ]]; then
  fail "duplicate RTL serials detected: $DUPES"
else
  pass "no duplicate RTL serials detected"
fi
if [[ "$UAT_MATCH_COUNT" -eq 1 ]]; then
  UAT_INDEX="$(python3 - "$WORK_DIR/uat_role.json" <<'PY'
import json, sys
matches = json.load(open(sys.argv[1], encoding='utf-8')).get('uat_matches', [])
print(matches[0].get('index', ''))
PY
)"
  pass "UAT serial $UAT_SERIAL resolved to RTL runtime index $UAT_INDEX"
else
  fail "UAT serial $UAT_SERIAL was not detected exactly once"
fi

section "Running service and role contract"
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet pi-air-traffic-tracker.service; then
    pass "pi-air-traffic-tracker.service is active"
  else
    warn "pi-air-traffic-tracker.service is not active"
  fi
else
  warn "systemctl is not available"
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
      pass "/api/status reports expected UAT serial $UAT_SERIAL"
    else
      warn "/api/status did not report expected UAT serial; got ${status_uat_serial:-empty}"
    fi
    if [[ "$status_uat_enabled" == "false" ]]; then
      pass "UAT role is still disabled in V0.1/V0.2 probe state"
    else
      warn "UAT role enabled state is ${status_uat_enabled:-empty}; persistent UAT runtime may already be configured"
    fi
  else
    warn "/api/status was not available; continuing hardware-only probe"
  fi
fi

section "Process ownership check"
PROCESS_LIST="$WORK_DIR/processes.txt"
pgrep -af 'pi_air_traffic_backend|readsb|dump978|uat|rtl_fm|rtl_sdr|rtl_adsb|dump1090' > "$PROCESS_LIST" 2>/dev/null || true
cat "$PROCESS_LIST" | tee -a "$REPORT_PATH" >/dev/null
if grep -q -- "$UAT_SERIAL" "$PROCESS_LIST"; then
  warn "a running process mentions UAT serial $UAT_SERIAL; exclusive probe may fail if it owns the receiver"
else
  pass "no running process command line mentions UAT serial $UAT_SERIAL"
fi

section "Exclusive UAT receiver open check"
if [[ -n "$UAT_INDEX" ]]; then
  UAT_RTL_TEST_STDOUT="$WORK_DIR/uat_rtl_test.stdout"
  UAT_RTL_TEST_STDERR="$WORK_DIR/uat_rtl_test.stderr"
  timeout 10 rtl_test -d "$UAT_INDEX" -t >"$UAT_RTL_TEST_STDOUT" 2>"$UAT_RTL_TEST_STDERR"
  open_rc=$?
  cat "$UAT_RTL_TEST_STDOUT" "$UAT_RTL_TEST_STDERR" | tee -a "$REPORT_PATH" >/dev/null
  if [[ "$open_rc" -eq 0 ]]; then
    pass "UAT RTL receiver opened successfully with rtl_test -d $UAT_INDEX -t"
  else
    fail "UAT RTL receiver could not be opened exclusively; rtl_test exit code $open_rc"
  fi
else
  fail "skipping exclusive open because UAT runtime index was not resolved"
fi

section "978 MHz raw capture check"
RTL_SDR_CMD="$(command -v rtl_sdr 2>/dev/null || true)"
if [[ -n "$UAT_INDEX" && -n "$RTL_SDR_CMD" && -x "$RTL_SDR_CMD" ]]; then
  UAT_IQ_OK=0
  UAT_IQ_BYTES=0
  UAT_CAPTURE_SUCCESS_LABEL=""
  UAT_CAPTURE_ATTEMPT=0
  UAT_CAPTURE_MATRIX="$WORK_DIR/uat_978_capture_matrix.tsv"
  printf 'attempt\tdevice_arg\tsample_rate\tgain_arg\texit_code\tbytes\tfile\n' > "$UAT_CAPTURE_MATRIX"

  # rtl_sdr builds vary in accepted gain syntax and sync-read behavior.  Try a
  # small matrix before declaring the UAT hardware path failed.  Keep this as a
  # hardware-open/capture proof only; it does not decode UAT frames yet.
  read -r -a UAT_SAMPLE_RATE_CANDIDATES <<< "${PI_AIR_TRAFFIC_UAT_SAMPLE_RATE_CANDIDATES:-$UAT_SAMPLE_RATE 2400000 2048000 2000000 1024000}"
  read -r -a UAT_GAIN_CANDIDATES <<< "${PI_AIR_TRAFFIC_UAT_GAIN_CANDIDATES:-$UAT_GAIN_DB 496 480 auto}"

  for device_arg in "$UAT_INDEX" "$UAT_SERIAL"; do
    [[ -z "$device_arg" ]] && continue
    for sample_rate in "${UAT_SAMPLE_RATE_CANDIDATES[@]}"; do
      [[ -z "$sample_rate" ]] && continue
      for gain_arg in "${UAT_GAIN_CANDIDATES[@]}"; do
        [[ -z "$gain_arg" ]] && continue
        UAT_CAPTURE_ATTEMPT=$((UAT_CAPTURE_ATTEMPT+1))
        UAT_IQ="$WORK_DIR/uat_978_probe_${UAT_CAPTURE_ATTEMPT}.iq"
        UAT_CAPTURE_LOG="$WORK_DIR/uat_978_rtl_sdr_${UAT_CAPTURE_ATTEMPT}.log"
        rm -f "$UAT_IQ"
        sleep 1
        if [[ "$gain_arg" == "auto" ]]; then
          timeout 12 rtl_sdr -d "$device_arg" -f "$UAT_FREQUENCY_HZ" -s "$sample_rate" -n 262144 "$UAT_IQ" >"$UAT_CAPTURE_LOG" 2>&1
        else
          timeout 12 rtl_sdr -d "$device_arg" -f "$UAT_FREQUENCY_HZ" -s "$sample_rate" -g "$gain_arg" -n 262144 "$UAT_IQ" >"$UAT_CAPTURE_LOG" 2>&1
        fi
        cap_rc=$?
        bytes=0
        [[ -f "$UAT_IQ" ]] && bytes="$(wc -c < "$UAT_IQ" | tr -d ' ')"
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$UAT_CAPTURE_ATTEMPT" "$device_arg" "$sample_rate" "$gain_arg" "$cap_rc" "$bytes" "$UAT_IQ" >> "$UAT_CAPTURE_MATRIX"
        log "UAT_CAPTURE_ATTEMPT=$UAT_CAPTURE_ATTEMPT DEVICE_ARG=$device_arg SAMPLE_RATE=$sample_rate GAIN_ARG=$gain_arg EXIT=$cap_rc BYTES=$bytes"
        sed -n '1,20p' "$UAT_CAPTURE_LOG" | sed "s/^/  rtl_sdr: /" | tee -a "$REPORT_PATH" >/dev/null
        if [[ "${bytes:-0}" =~ ^[0-9]+$ && "${bytes:-0}" -ge 131072 ]]; then
          UAT_IQ_OK=1
          UAT_IQ_BYTES="$bytes"
          UAT_CAPTURE_SUCCESS_LABEL="device_arg=$device_arg sample_rate=$sample_rate gain_arg=$gain_arg exit_code=$cap_rc bytes=$bytes"
          if [[ "$cap_rc" -ne 0 ]]; then
            warn "rtl_sdr produced IQ bytes but exited with code $cap_rc; treating hardware capture as usable and recording warning"
          fi
          break 3
        fi
      done
    done
  done
  log "UAT_CAPTURE_MATRIX=$UAT_CAPTURE_MATRIX"
  log "UAT_IQ_BYTES=$UAT_IQ_BYTES"
  if [[ "$UAT_IQ_OK" -eq 1 ]]; then
    pass "captured raw IQ at 978 MHz from UAT receiver: $UAT_CAPTURE_SUCCESS_LABEL"
  else
    fail "raw 978 MHz IQ capture failed across capture matrix; see $UAT_CAPTURE_MATRIX and rtl_sdr logs in $WORK_DIR"
  fi
else
  warn "skipping raw 978 MHz capture because rtl_sdr is missing or UAT index is unresolved"
fi

section "UAT decoder tool inventory"
found_decoder=0
for decoder in dump978-fa dump978 uat2json skyaware978; do
  if command -v "$decoder" >/dev/null 2>&1; then
    pass "UAT decoder/tool candidate available: $decoder at $(command -v "$decoder")"
    found_decoder=1
  else
    warn "UAT decoder/tool candidate not found: $decoder"
  fi
done
if [[ "$found_decoder" -eq 1 ]]; then
  pass "at least one UAT decoder/tool candidate is present"
else
  warn "no UAT decoder candidate was found; next V0.2 step should install/build app-owned UAT decoder tooling"
fi

section "Recommendation"
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  log "UAT_PROBE_RECOMMENDATION=Hardware path is ready for decoder/tooling integration. Keep persistent UAT runtime disabled until decoder selection is complete."
else
  log "UAT_PROBE_RECOMMENDATION=Resolve failed hardware/open/capture checks before adding a persistent UAT decoder."
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
