#!/usr/bin/env bash
# Validate active NOAA live and Airband scan/listen control endpoints against the running Pi service.
# This is an operational validator: it starts/stops live audio modes and restores Airband tuning afterward.
set -u

BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://${PI_AIR_TRAFFIC_HOST:-127.0.0.1}:${PI_AIR_TRAFFIC_PORT:-8090}}"
REPORT_DIR="runtime/preflight"
REPORT_PATH="${REPORT_DIR}/pi5_active_noaa_airband_validation_$(date +%Y%m%d_%H%M%S).txt"
WORK_DIR="${REPORT_DIR}/active_noaa_airband_$(date +%Y%m%d_%H%M%S)"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
ORIGINAL_AIRBAND_JSON=""

mkdir -p "$REPORT_DIR" "$WORK_DIR"

log() { printf '%s\n' "$*" | tee -a "$REPORT_PATH"; }
pass() { PASS_COUNT=$((PASS_COUNT+1)); log "PASS: $*"; }
warn() { WARN_COUNT=$((WARN_COUNT+1)); log "WARN: $*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); log "FAIL: $*"; }
section() { log ""; log "===== $* ====="; }

json_get() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json
import sys
path, expr = sys.argv[1], sys.argv[2]
try:
    with open(path, 'r', encoding='utf-8') as handle:
        data = json.load(handle)
except Exception:
    print('')
    sys.exit(0)
value = data
for part in expr.split('.'):
    if part == '':
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

json_size() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json
import sys
path, expr = sys.argv[1], sys.argv[2]
try:
    with open(path, 'r', encoding='utf-8') as handle:
        data = json.load(handle)
except Exception:
    print('0')
    sys.exit(0)
value = data
for part in expr.split('.'):
    if not part:
        continue
    value = value.get(part) if isinstance(value, dict) else None
if isinstance(value, (list, dict)):
    print(len(value))
else:
    print('0')
PY
}

curl_json_get() {
  local path="$1"
  local output="$2"
  curl -sS --max-time 15 -H 'Cache-Control: no-cache' "$BASE_URL$path" -o "$output"
}

curl_json_post() {
  local path="$1"
  local payload="$2"
  local output="$3"
  curl -sS --max-time 25 -X POST -H 'Content-Type: application/json' --data "$payload" "$BASE_URL$path" -o "$output"
}

curl_post_empty() {
  local path="$1"
  local output="$2"
  curl -sS --max-time 25 -X POST "$BASE_URL$path" -o "$output"
}

curl_audio() {
  local path="$1"
  local output="$2"
  local headers="$3"
  curl -sS --max-time 15 -D "$headers" -o "$output" -w '%{http_code}' "$BASE_URL$path"
}

restore_airband_tuning() {
  if [[ -n "$ORIGINAL_AIRBAND_JSON" && -s "$ORIGINAL_AIRBAND_JSON" ]]; then
    local payload
    payload="$(python3 - "$ORIGINAL_AIRBAND_JSON" <<'PY'
import json, sys
try:
    with open(sys.argv[1], 'r', encoding='utf-8') as handle:
        data = json.load(handle)
except Exception:
    data = {}
allowed = {
    'airband_activity_threshold_rms',
    'airband_rf_gain_db',
    'airband_search_mode',
    'airband_spectrum_margin_db',
}
print(json.dumps({key: data[key] for key in allowed if key in data}, separators=(',', ':')))
PY
)"
    if [[ "$payload" != "{}" ]]; then
      curl_json_post "/api/settings/airband-scan" "$payload" "$WORK_DIR/restore_airband_tuning.json" >/dev/null 2>&1 || true
    fi
  fi
}

cleanup_runtime_modes() {
  curl_post_empty "/api/airband/scan/activity/stop" "$WORK_DIR/cleanup_airband_stop.json" >/dev/null 2>&1 || true
  curl_post_empty "/api/noaa/live/stop" "$WORK_DIR/cleanup_noaa_stop.json" >/dev/null 2>&1 || true
  restore_airband_tuning
}

trap cleanup_runtime_modes EXIT

section "Environment"
log "BASE_URL=$BASE_URL"
if [[ -f web/index.html && -d src/backend && -d tools ]]; then
  pass "repository root appears valid"
else
  fail "repository root does not look valid"
fi
for cmd in curl python3; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$cmd available at $(command -v "$cmd")"
  else
    fail "$cmd is required"
  fi
done

section "Baseline service status"
STATUS_JSON="$WORK_DIR/status_initial.json"
if curl_json_get "/api/status" "$STATUS_JSON" && python3 -m json.tool "$STATUS_JSON" >/dev/null 2>&1; then
  pass "/api/status returned JSON"
else
  fail "/api/status did not return parseable JSON"
fi
if [[ "$(json_get "$STATUS_JSON" decoder.running)" == "true" ]]; then
  pass "ADS-B decoder is running before active audio tests"
else
  warn "ADS-B decoder was not reported running before active audio tests"
fi

section "Initial audio cleanup"
if curl_post_empty "/api/airband/scan/activity/stop" "$WORK_DIR/initial_airband_stop.json"; then
  pass "Airband stop endpoint accepted initial cleanup"
else
  warn "Airband stop cleanup request failed"
fi
if curl_post_empty "/api/noaa/live/stop" "$WORK_DIR/initial_noaa_stop.json"; then
  pass "NOAA stop endpoint accepted initial cleanup"
else
  warn "NOAA stop cleanup request failed"
fi

section "NOAA live control and audio"
NOAA_START_JSON="$WORK_DIR/noaa_live_start.json"
if curl_post_empty "/api/noaa/live/start" "$NOAA_START_JSON" && python3 -m json.tool "$NOAA_START_JSON" >/dev/null 2>&1; then
  if [[ "$(json_get "$NOAA_START_JSON" started)" == "true" ]]; then
    pass "NOAA live start returned started=true"
  else
    fail "NOAA live start did not return started=true"
  fi
else
  fail "NOAA live start did not return parseable JSON"
fi
sleep 1
NOAA_STATUS_JSON="$WORK_DIR/noaa_status_after_start.json"
if curl_json_get "/api/status" "$NOAA_STATUS_JSON" && python3 -m json.tool "$NOAA_STATUS_JSON" >/dev/null 2>&1; then
  audio_mode="$(json_get "$NOAA_STATUS_JSON" audio_mode)"
  live_running="$(json_get "$NOAA_STATUS_JSON" live_audio_running)"
  log "NOAA_STATUS_AUDIO_MODE=$audio_mode"
  log "NOAA_STATUS_LIVE_RUNNING=$live_running"
  if [[ "$audio_mode" == "noaa_live" || "$live_running" == "true" ]]; then
    pass "/api/status reports NOAA live audio active"
  else
    fail "/api/status did not report NOAA live audio active"
  fi
else
  fail "could not read /api/status after NOAA start"
fi

noaa_audio_ok=0
for attempt in $(seq 1 10); do
  audio_file="$WORK_DIR/noaa_live_audio_${attempt}.wav"
  headers_file="$WORK_DIR/noaa_live_audio_${attempt}.headers"
  code="$(curl_audio "/api/noaa/live/audio.wav?from=0" "$audio_file" "$headers_file" || true)"
  bytes=0
  [[ -f "$audio_file" ]] && bytes="$(wc -c < "$audio_file" | tr -d ' ')"
  log "NOAA_AUDIO_ATTEMPT=$attempt HTTP=$code BYTES=$bytes"
  if [[ "$code" == "200" && "$bytes" -gt 44 ]]; then
    pass "NOAA live audio endpoint returned WAV payload: ${bytes} bytes"
    noaa_audio_ok=1
    break
  fi
  sleep 1
done
if [[ "$noaa_audio_ok" -ne 1 ]]; then
  fail "NOAA live audio endpoint did not produce WAV payload"
fi

NOAA_STOP_JSON="$WORK_DIR/noaa_live_stop.json"
if curl_post_empty "/api/noaa/live/stop" "$NOAA_STOP_JSON" && python3 -m json.tool "$NOAA_STOP_JSON" >/dev/null 2>&1; then
  if [[ "$(json_get "$NOAA_STOP_JSON" stopped)" == "true" ]]; then
    pass "NOAA live stop returned stopped=true"
  else
    fail "NOAA live stop did not return stopped=true"
  fi
else
  fail "NOAA live stop did not return parseable JSON"
fi
sleep 1

section "Airband active scan control"
ORIGINAL_AIRBAND_JSON="$WORK_DIR/original_airband_tuning.json"
if curl_json_get "/api/settings/airband-scan" "$ORIGINAL_AIRBAND_JSON" && python3 -m json.tool "$ORIGINAL_AIRBAND_JSON" >/dev/null 2>&1; then
  pass "saved current Airband tuning for restore"
else
  warn "could not save current Airband tuning; restore may be skipped"
  ORIGINAL_AIRBAND_JSON=""
fi

CHANNELS_JSON="$WORK_DIR/airband_channels.json"
AIRBAND_VALIDATION_MODE="fast_spectrum"
if curl_json_get "/api/airband/channels" "$CHANNELS_JSON" && python3 -m json.tool "$CHANNELS_JSON" >/dev/null 2>&1; then
  channel_count="$(json_size "$CHANNELS_JSON" channels)"
  log "AIRBAND_CHANNEL_COUNT=$channel_count"
  if [[ "$channel_count" -gt 0 ]]; then
    pass "Airband nearby channel list contains ${channel_count} channel(s)"
    AIRBAND_VALIDATION_MODE="traditional"
  else
    warn "Airband nearby channel list is empty; validating active scanner with fast_spectrum unlisted-frequency mode"
    AIRBAND_VALIDATION_MODE="fast_spectrum"
  fi
else
  fail "Airband channel endpoint did not return parseable JSON"
fi

# Use traditional mode when the FAA catalog provides nearby channels.  If the
# catalog is missing/empty, keep validation useful by exercising fast_spectrum,
# which can scan unlisted 120-130 MHz channels without catalog data.
if [[ "$AIRBAND_VALIDATION_MODE" == "traditional" ]]; then
  TUNING_PAYLOAD='{"airband_search_mode":"traditional","airband_activity_threshold_rms":1300,"airband_rf_gain_db":40.2}'
else
  TUNING_PAYLOAD='{"airband_search_mode":"fast_spectrum","airband_activity_threshold_rms":1300,"airband_rf_gain_db":40.2,"airband_spectrum_margin_db":8}'
fi
TUNING_JSON="$WORK_DIR/airband_tuning_${AIRBAND_VALIDATION_MODE}.json"
if curl_json_post "/api/settings/airband-scan" "$TUNING_PAYLOAD" "$TUNING_JSON" && python3 -m json.tool "$TUNING_JSON" >/dev/null 2>&1; then
  if [[ "$(json_get "$TUNING_JSON" airband_search_mode)" == "$AIRBAND_VALIDATION_MODE" ]]; then
    pass "Airband tuning set to ${AIRBAND_VALIDATION_MODE} scanner mode for active validation"
  else
    fail "Airband tuning did not switch to ${AIRBAND_VALIDATION_MODE} mode"
  fi
else
  fail "Airband tuning update failed"
fi

AIRBAND_START_JSON="$WORK_DIR/airband_start.json"
if curl_post_empty "/api/airband/scan/activity/start?scope=priority" "$AIRBAND_START_JSON" && python3 -m json.tool "$AIRBAND_START_JSON" >/dev/null 2>&1; then
  if [[ "$(json_get "$AIRBAND_START_JSON" started)" == "true" ]]; then
    pass "Airband scan start returned started=true"
  else
    fail "Airband scan start did not return started=true; error=$(json_get "$AIRBAND_START_JSON" error)"
  fi
else
  fail "Airband scan start did not return parseable JSON"
fi

state_seen=0
hold_seen=0
for attempt in $(seq 1 20); do
  SCAN_STATUS_JSON="$WORK_DIR/airband_scan_status_${attempt}.json"
  if curl_json_get "/api/airband/scan/status" "$SCAN_STATUS_JSON" && python3 -m json.tool "$SCAN_STATUS_JSON" >/dev/null 2>&1; then
    running="$(json_get "$SCAN_STATUS_JSON" airband_scan_running)"
    state="$(json_get "$SCAN_STATUS_JSON" airband_scan_state)"
    scanned="$(json_get "$SCAN_STATUS_JSON" airband_channels_scanned)"
    hold="$(json_get "$SCAN_STATUS_JSON" airband_hold_active)"
    err="$(json_get "$SCAN_STATUS_JSON" airband_scan_error)"
    log "AIRBAND_STATUS_ATTEMPT=$attempt RUNNING=$running STATE=$state SCANNED=${scanned:-0} HOLD=$hold ERROR=${err:-}"
    if [[ -n "$err" && "$err" != "None" ]]; then
      fail "Airband scan reported error: $err"
      break
    fi
    if [[ "$running" == "true" && "$state" != "stopped" ]]; then
      state_seen=1
    fi
    if [[ "${scanned:-0}" =~ ^[0-9]+$ && "${scanned:-0}" -gt 0 ]]; then
      state_seen=1
    fi
    if [[ "$hold" == "true" ]]; then
      hold_seen=1
      break
    fi
  fi
  sleep 1
done
if [[ "$state_seen" -eq 1 ]]; then
  pass "Airband scan entered an active/searching state or scanned channels"
else
  fail "Airband scan did not enter an active/searching state"
fi

if [[ "$hold_seen" -eq 1 ]]; then
  audio_file="$WORK_DIR/airband_live_audio.wav"
  headers_file="$WORK_DIR/airband_live_audio.headers"
  code="$(curl_audio "/api/airband/scan/live/audio.wav?from=0" "$audio_file" "$headers_file" || true)"
  bytes=0
  [[ -f "$audio_file" ]] && bytes="$(wc -c < "$audio_file" | tr -d ' ')"
  log "AIRBAND_LIVE_AUDIO_HTTP=$code BYTES=$bytes"
  if [[ "$code" == "200" && "$bytes" -gt 44 ]]; then
    pass "Airband held-channel live audio endpoint returned WAV payload: ${bytes} bytes"
  else
    warn "Airband hold was seen but live audio chunk was not available during the polling window"
  fi
  SKIP_JSON="$WORK_DIR/airband_skip.json"
  if curl_post_empty "/api/airband/scan/activity/skip" "$SKIP_JSON" && python3 -m json.tool "$SKIP_JSON" >/dev/null 2>&1; then
    if [[ "$(json_get "$SKIP_JSON" released)" == "true" ]]; then
      pass "Airband skip control released held channel"
    else
      warn "Airband skip endpoint responded but did not report released=true"
    fi
  else
    warn "Airband skip endpoint was not testable after hold window"
  fi
else
  warn "No active Airband transmission was held; live audio and skip/block controls were not fully exercised"
fi

BEST_AUDIO="$WORK_DIR/airband_best_audio.wav"
BEST_HEADERS="$WORK_DIR/airband_best_audio.headers"
best_code="$(curl_audio "/api/airband/scan/best_audio.wav" "$BEST_AUDIO" "$BEST_HEADERS" || true)"
best_bytes=0
[[ -f "$BEST_AUDIO" ]] && best_bytes="$(wc -c < "$BEST_AUDIO" | tr -d ' ')"
if [[ "$best_code" == "200" && "$best_bytes" -gt 44 ]]; then
  pass "Airband best-audio endpoint returned WAV payload: ${best_bytes} bytes"
else
  warn "Airband best-audio endpoint did not have a captured WAV payload yet"
fi

AIRBAND_STOP_JSON="$WORK_DIR/airband_stop.json"
if curl_post_empty "/api/airband/scan/activity/stop" "$AIRBAND_STOP_JSON" && python3 -m json.tool "$AIRBAND_STOP_JSON" >/dev/null 2>&1; then
  if [[ "$(json_get "$AIRBAND_STOP_JSON" stopped)" == "true" ]]; then
    pass "Airband scan stop returned stopped=true"
  else
    fail "Airband scan stop did not return stopped=true"
  fi
else
  fail "Airband scan stop did not return parseable JSON"
fi
restore_airband_tuning
pass "Airband tuning restore attempted"

section "Final idle status"
FINAL_STATUS_JSON="$WORK_DIR/status_final.json"
if curl_json_get "/api/status" "$FINAL_STATUS_JSON" && python3 -m json.tool "$FINAL_STATUS_JSON" >/dev/null 2>&1; then
  scan_running="$(json_get "$FINAL_STATUS_JSON" airband_scan_running)"
  live_running="$(json_get "$FINAL_STATUS_JSON" live_audio_running)"
  audio_mode="$(json_get "$FINAL_STATUS_JSON" audio_mode)"
  log "FINAL_SCAN_RUNNING=$scan_running"
  log "FINAL_LIVE_AUDIO_RUNNING=$live_running"
  log "FINAL_AUDIO_MODE=$audio_mode"
  if [[ "$scan_running" == "false" && "$live_running" == "false" ]]; then
    pass "final status reports active audio modes stopped"
  else
    fail "final status still reports active audio mode"
  fi
else
  fail "could not read final /api/status"
fi

section "Summary"
log "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
log "Report path: $REPORT_PATH"
log "Work dir: $WORK_DIR"
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  log "FINAL: PASS"
  exit 0
fi
log "FINAL: FAIL"
exit 1
