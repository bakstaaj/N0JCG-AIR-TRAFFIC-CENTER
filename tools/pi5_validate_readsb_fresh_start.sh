#!/usr/bin/env bash
set -u

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="runtime/preflight"
REPORT_PATH="${REPORT_DIR}/pi5_readsb_fresh_start_${STAMP}.txt"
SERVICE_NAME="${PI_AIR_TRAFFIC_SERVICE_NAME:-pi-air-traffic-tracker.service}"
BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://127.0.0.1:8090}"
ADSB_SERIAL="${PI_AIR_TRAFFIC_ADSB_SERIAL:-00001090}"
RUNTIME_ROOT="${RTL_ADSB_TRACKER_RUNTIME:-runtime}"
AIRCRAFT_JSON="${RUNTIME_ROOT}/settings/readsb-json/aircraft.json"
STATUS_JSON="${REPORT_DIR}/pi5_readsb_fresh_status_${STAMP}.json"
STATUS_TMP="${STATUS_JSON}.tmp"
CURL_ERR="${REPORT_DIR}/pi5_readsb_fresh_status_${STAMP}.curl.err"
WAS_ACTIVE=0
RESTORE_DONE=0

mkdir -p "${REPORT_DIR}"
exec > >(tee "${REPORT_PATH}") 2>&1

pass() { echo "PASS: $*"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "WARN: $*"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "FAIL: $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
section() { echo; echo "===== $* ====="; }

restore_service_state() {
  (( RESTORE_DONE == 1 )) && return 0
  RESTORE_DONE=1
  if (( WAS_ACTIVE == 1 )); then
    systemctl start "${SERVICE_NAME}" >/dev/null 2>&1 || true
  else
    systemctl stop "${SERVICE_NAME}" >/dev/null 2>&1 || true
  fi
}

finish() {
  local rc=0
  section "Summary"
  echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
  echo "Report path: ${REPORT_PATH}"
  if (( FAIL_COUNT == 0 )); then
    echo "FINAL: PASS"
    rc=0
  else
    echo "FINAL: FAIL"
    rc=1
  fi
  restore_service_state
  exit "${rc}"
}
trap finish EXIT

json_value() {
  local path="$1"
  local expr="$2"
  python3 - "$path" "$expr" <<'PY'
import json
import sys
path, expr = sys.argv[1:3]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
value = data
for part in expr.split("."):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break
if isinstance(value, bool):
    print("true" if value else "false")
elif value is None:
    print("")
else:
    print(value)
PY
}

status_ready() {
  local path="$1"
  python3 - "$path" "${ADSB_SERIAL}" <<'PY'
import json
import sys
path, expected_serial = sys.argv[1:3]
try:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception as exc:
    print(f"parse_error={exc}")
    sys.exit(2)
roles = data.get("receiver_roles") or {}
adsb = roles.get("adsb") or {}
decoder = data.get("decoder") or {}
profile = decoder.get("profile") or {}
cmd = str(profile.get("decoder") or data.get("pi_backend", {}).get("readsb_command") or "")
problems = []
if adsb.get("serial") != expected_serial:
    problems.append(f"adsb_serial={adsb.get('serial')!r}")
if decoder.get("running") is not True:
    problems.append(f"decoder_running={decoder.get('running')!r}")
if "runtime/bin/readsb" not in cmd:
    problems.append(f"decoder_cmd={cmd!r}")
if problems:
    print("; ".join(problems))
    sys.exit(3)
print("ready")
PY
}

wait_for_status_ready() {
  local deadline=$((SECONDS + 45))
  local last_detail="<none>"
  while (( SECONDS < deadline )); do
    rm -f "${STATUS_TMP}"
    if curl -fsS --max-time 4 "${BASE_URL}/api/status" > "${STATUS_TMP}" 2>"${CURL_ERR}"; then
      if [[ -s "${STATUS_TMP}" ]]; then
        if detail="$(status_ready "${STATUS_TMP}" 2>&1)"; then
          mv -f "${STATUS_TMP}" "${STATUS_JSON}"
          echo "STATUS_READY_DETAIL: ${detail}"
          return 0
        fi
        last_detail="${detail}"
      else
        last_detail="empty /api/status response"
      fi
    else
      last_detail="curl failed: $(tr '\n' ' ' < "${CURL_ERR}" 2>/dev/null || true)"
    fi
    sleep 1
  done
  echo "LAST_STATUS_DETAIL: ${last_detail}"
  if [[ -f "${STATUS_TMP}" ]]; then
    echo "LAST_STATUS_BODY_BEGIN"
    sed -n '1,80p' "${STATUS_TMP}" || true
    echo "LAST_STATUS_BODY_END"
  fi
  return 1
}

read_aircraft_messages() {
  local path="$1"
  python3 - "$path" <<'PY'
import json
import sys
try:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    print(int(data.get("messages", 0)))
except Exception:
    print("")
PY
}

section "Environment"
if [[ -d .git && -f src/backend/pi_air_traffic_backend.py ]]; then
  pass "repository root appears valid"
else
  fail "run from PI-AIR-TRAFFIC-TRACKER repository root"
fi
echo "SERVICE_NAME=${SERVICE_NAME}"
echo "BASE_URL=${BASE_URL}"
echo "AIRCRAFT_JSON=${AIRCRAFT_JSON}"
for command in systemctl curl python3 sha256sum pgrep; do
  if command -v "${command}" >/dev/null 2>&1; then
    pass "${command} available"
  else
    fail "${command} is required"
  fi
done
(( FAIL_COUNT > 0 )) && exit 1

section "Stop service and create stale JSON sentinel"
if systemctl is-active --quiet "${SERVICE_NAME}"; then
  WAS_ACTIVE=1
  pass "${SERVICE_NAME} was active before test"
else
  WAS_ACTIVE=0
  warn "${SERVICE_NAME} was not active before test; validator will stop it again at the end"
fi

if systemctl stop "${SERVICE_NAME}"; then
  pass "stopped ${SERVICE_NAME}"
else
  fail "failed to stop ${SERVICE_NAME}"
  exit 1
fi
sleep 2

mkdir -p "$(dirname "${AIRCRAFT_JSON}")"
cat > "${AIRCRAFT_JSON}" <<'JSON'
{"now": 1, "messages": 3, "aircraft": []}
JSON
SENTINEL_SHA="$(sha256sum "${AIRCRAFT_JSON}" | awk '{print $1}')"
pass "wrote stale aircraft.json sentinel with messages=3"

section "Start service"
if systemctl start "${SERVICE_NAME}"; then
  pass "started ${SERVICE_NAME}"
else
  fail "failed to start ${SERVICE_NAME}"
  exit 1
fi

section "Wait for /api/status readiness"
if wait_for_status_ready; then
  pass "/api/status reached ready Pi ADS-B decoder contract"
else
  fail "/api/status did not reach ready Pi ADS-B decoder contract"
fi

if [[ -s "${STATUS_JSON}" ]]; then
  ADSB_STATUS_SERIAL="$(json_value "${STATUS_JSON}" "receiver_roles.adsb.serial")"
  READSB_CMD="$(json_value "${STATUS_JSON}" "decoder.profile.decoder")"
  DECODER_RUNNING="$(json_value "${STATUS_JSON}" "decoder.running")"
  echo "STATUS_ADSB_SERIAL=${ADSB_STATUS_SERIAL}"
  echo "READSB_CMD=${READSB_CMD}"
  echo "DECODER_RUNNING=${DECODER_RUNNING}"
  if [[ "${ADSB_STATUS_SERIAL}" == "${ADSB_SERIAL}" ]]; then
    pass "status receiver_roles.adsb.serial reports ${ADSB_SERIAL}"
  else
    fail "status receiver_roles.adsb.serial expected ${ADSB_SERIAL}, got ${ADSB_STATUS_SERIAL:-<empty>}"
  fi
  if [[ "${READSB_CMD}" == *"runtime/bin/readsb"* ]]; then
    pass "status reports app-owned runtime/bin/readsb command"
  else
    fail "status did not report app-owned runtime/bin/readsb command: ${READSB_CMD:-<empty>}"
  fi
  if [[ "${DECODER_RUNNING}" == "true" ]]; then
    pass "status decoder.running is true"
  else
    fail "status decoder.running was not true: ${DECODER_RUNNING:-<empty>}"
  fi
else
  fail "status JSON file was not captured"
fi

section "Process and JSON freshness"
READSB_PATTERN="${PWD}/runtime/bin/readsb.*--device ${ADSB_SERIAL}"
if pgrep -af "${READSB_PATTERN}" >/tmp/pi_air_traffic_readsb_pgrep.txt 2>/dev/null; then
  pass "app-owned readsb process is running for serial ${ADSB_SERIAL}"
  cat /tmp/pi_air_traffic_readsb_pgrep.txt
else
  fail "app-owned readsb process for serial ${ADSB_SERIAL} was not found"
fi

JSON_REFRESHED=0
for _ in $(seq 1 30); do
  if [[ -s "${AIRCRAFT_JSON}" ]]; then
    CURRENT_SHA="$(sha256sum "${AIRCRAFT_JSON}" | awk '{print $1}')"
    if [[ "${CURRENT_SHA}" != "${SENTINEL_SHA}" ]]; then
      JSON_REFRESHED=1
      break
    fi
  fi
  sleep 1
done
if (( JSON_REFRESHED == 1 )); then
  pass "aircraft.json was replaced/refreshed by readsb"
else
  fail "aircraft.json still matches stale sentinel after service start"
fi

section "ADS-B observation"
START_MESSAGES="$(read_aircraft_messages "${AIRCRAFT_JSON}")"
echo "START_MESSAGES=${START_MESSAGES:-<empty>}"
sleep 30
END_MESSAGES="$(read_aircraft_messages "${AIRCRAFT_JSON}")"
echo "END_MESSAGES=${END_MESSAGES:-<empty>}"
if [[ "${START_MESSAGES}" =~ ^[0-9]+$ && "${END_MESSAGES}" =~ ^[0-9]+$ ]]; then
  if (( END_MESSAGES > START_MESSAGES )); then
    pass "ADS-B messages increased after service fresh start: ${START_MESSAGES} -> ${END_MESSAGES}"
  else
    warn "ADS-B messages did not increase during observation: ${START_MESSAGES} -> ${END_MESSAGES}; RF conditions may be quiet"
  fi
else
  fail "could not parse ADS-B message counts"
fi
