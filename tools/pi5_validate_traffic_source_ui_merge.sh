#!/usr/bin/env bash
# Validate V0.2 traffic source switches and unified aircraft feed on the Pi.
set -u

PROJECT_ROOT="$(pwd)"
REPORT_DIR="runtime/preflight"
WORK_DIR="${REPORT_DIR}/traffic_source_ui_merge_$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${REPORT_DIR}/pi5_traffic_source_ui_merge_$(date +%Y%m%d_%H%M%S).txt"
BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://${PI_AIR_TRAFFIC_HOST:-127.0.0.1}:${PI_AIR_TRAFFIC_PORT:-8090}}"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
ORIGINAL_ADSB="true"
ORIGINAL_UAT="false"

mkdir -p "$REPORT_DIR" "$WORK_DIR"
log(){ printf '%s\n' "$*" | tee -a "$REPORT_PATH"; }
section(){ log ""; log "===== $* ====="; }
pass(){ PASS_COUNT=$((PASS_COUNT+1)); log "PASS: $*"; }
warn(){ WARN_COUNT=$((WARN_COUNT+1)); log "WARN: $*"; }
fail(){ FAIL_COUNT=$((FAIL_COUNT+1)); log "FAIL: $*"; }

json_get(){
  local file="$1" expr="$2"
  python3 - "$file" "$expr" <<'PY'
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
if isinstance(value, bool): print('true' if value else 'false')
elif value is None: print('')
else: print(value)
PY
}

post_json(){
  local url="$1" body="$2" output="$3"
  curl -sS --max-time 20 -X POST -H 'Content-Type: application/json' --data "$body" "$url" -o "$output"
}

restore_sources(){
  if command -v curl >/dev/null 2>&1; then
    post_json "$BASE_URL/api/settings/traffic-sources" "{\"adsb_1090_enabled\":$ORIGINAL_ADSB,\"uat_978_enabled\":$ORIGINAL_UAT}" "$WORK_DIR/restore_sources.json" >/dev/null 2>&1 || true
  fi
}
trap restore_sources EXIT

section "Environment"
log "PROJECT_ROOT=$PROJECT_ROOT"
log "BASE_URL=$BASE_URL"
if [[ -f README.md && -d src/backend && -d web ]]; then pass "repository root appears valid"; else fail "run from repository root"; fi
for cmd in python3 curl systemctl; do
  if command -v "$cmd" >/dev/null 2>&1; then pass "$cmd available at $(command -v "$cmd")"; else fail "$cmd is required"; fi
done

section "Static patch checks"
for path in web/index.html web/app.js web/app.css src/backend/pi_air_traffic_backend.py docs/PI_UAT_978_TRAFFIC_SOURCE_UI.md docs/guardrails/PI_TRAFFIC_SOURCE_MERGE_GUARDRAIL.md; do
  [[ -f "$path" ]] && pass "$path exists" || fail "$path missing"
done
grep -q 'trafficSource1090' web/index.html && pass "1090 traffic switch exists in Configuration menu" || fail "1090 traffic switch missing"
grep -q 'trafficSourceUat978' web/index.html && pass "UAT traffic switch exists in Configuration menu" || fail "UAT traffic switch missing"
grep -q '/api/settings/traffic-sources' web/app.js && pass "UI calls traffic source settings API" || fail "UI traffic source API call missing"
grep -q 'patch_pi_traffic_source_handler' src/backend/pi_air_traffic_backend.py && pass "Pi backend traffic source patch is installed" || fail "backend traffic source patch missing"
grep -q 'merged_aircraft_payload' src/backend/pi_air_traffic_backend.py && pass "backend merged aircraft payload is installed" || fail "merged aircraft payload missing"

section "Service status"
if systemctl is-active --quiet pi-air-traffic-tracker.service; then
  pass "pi-air-traffic-tracker.service is active"
else
  fail "pi-air-traffic-tracker.service is not active"
fi

section "Traffic source settings API"
SETTINGS_JSON="$WORK_DIR/traffic_sources_initial.json"
if curl -sS --max-time 15 "$BASE_URL/api/settings/traffic-sources" -o "$SETTINGS_JSON" && python3 -m json.tool "$SETTINGS_JSON" >/dev/null 2>&1; then
  pass "/api/settings/traffic-sources returned JSON"
  ORIGINAL_ADSB="$(json_get "$SETTINGS_JSON" adsb_1090_enabled)"
  ORIGINAL_UAT="$(json_get "$SETTINGS_JSON" uat_978_enabled)"
  [[ "$ORIGINAL_ADSB" == "true" || "$ORIGINAL_ADSB" == "false" ]] || ORIGINAL_ADSB="true"
  [[ "$ORIGINAL_UAT" == "true" || "$ORIGINAL_UAT" == "false" ]] || ORIGINAL_UAT="false"
  log "ORIGINAL_ADSB=$ORIGINAL_ADSB"
  log "ORIGINAL_UAT=$ORIGINAL_UAT"
else
  fail "traffic source settings API did not return JSON"
fi

APPLY_JSON="$WORK_DIR/traffic_sources_apply.json"
if post_json "$BASE_URL/api/settings/traffic-sources" "{\"adsb_1090_enabled\":true,\"uat_978_enabled\":true}" "$APPLY_JSON" && python3 -m json.tool "$APPLY_JSON" >/dev/null 2>&1; then
  pass "enabled ADS-B and UAT through traffic source API"
  [[ "$(json_get "$APPLY_JSON" adsb_1090_enabled)" == "true" ]] && pass "ADS-B enabled state saved" || fail "ADS-B enabled state was not saved"
  [[ "$(json_get "$APPLY_JSON" uat_978_enabled)" == "true" ]] && pass "UAT enabled state saved" || fail "UAT enabled state was not saved"
else
  fail "failed to enable traffic sources through API"
fi

section "Unified aircraft feed"
AIRCRAFT_JSON="$WORK_DIR/aircraft_merged.json"
if curl -sS --max-time 25 "$BASE_URL/api/aircraft.json" -o "$AIRCRAFT_JSON" && python3 -m json.tool "$AIRCRAFT_JSON" >/dev/null 2>&1; then
  pass "/api/aircraft.json returned JSON"
  [[ "$(json_get "$AIRCRAFT_JSON" source_enabled.adsb_1090)" == "true" ]] && pass "merged feed reports ADS-B enabled" || fail "merged feed did not report ADS-B enabled"
  [[ "$(json_get "$AIRCRAFT_JSON" source_enabled.uat_978)" == "true" ]] && pass "merged feed reports UAT enabled" || fail "merged feed did not report UAT enabled"
  ADSB_COUNT="$(json_get "$AIRCRAFT_JSON" source_counts.adsb_1090)"
  UAT_COUNT="$(json_get "$AIRCRAFT_JSON" source_counts.uat_978)"
  log "MERGED_ADSB_COUNT=${ADSB_COUNT:-0}"
  log "MERGED_UAT_COUNT=${UAT_COUNT:-0}"
  pass "merged aircraft feed includes source_counts metadata"
else
  fail "unified aircraft feed did not return JSON"
fi

section "UAT runtime status"
UAT_STATUS="$WORK_DIR/uat_status.json"
if curl -sS --max-time 15 "$BASE_URL/api/uat/status" -o "$UAT_STATUS" && python3 -m json.tool "$UAT_STATUS" >/dev/null 2>&1; then
  pass "/api/uat/status returned JSON"
  [[ "$(json_get "$UAT_STATUS" running)" == "true" ]] && pass "UAT decoder is running after enabling source" || warn "UAT decoder is not running; inspect apply_errors and dump978 log"
  [[ "$(json_get "$UAT_STATUS" collector_running)" == "true" ]] && pass "UAT JSON collector is running" || warn "UAT JSON collector is not running; no UAT aircraft will merge yet"
else
  fail "UAT status API did not return JSON"
fi

section "Restore original traffic source settings"
RESTORE_JSON="$WORK_DIR/traffic_sources_restore.json"
if post_json "$BASE_URL/api/settings/traffic-sources" "{\"adsb_1090_enabled\":$ORIGINAL_ADSB,\"uat_978_enabled\":$ORIGINAL_UAT}" "$RESTORE_JSON" && python3 -m json.tool "$RESTORE_JSON" >/dev/null 2>&1; then
  pass "restored original traffic source settings"
else
  fail "failed to restore original traffic source settings"
fi
trap - EXIT

section "Summary"
log "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
log "Report path: $REPORT_PATH"
log "Work dir: $WORK_DIR"
if [[ "$FAIL_COUNT" -eq 0 ]]; then log "FINAL: PASS"; exit 0; else log "FINAL: FAIL"; exit 1; fi
