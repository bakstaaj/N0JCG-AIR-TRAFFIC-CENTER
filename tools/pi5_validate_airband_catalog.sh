#!/usr/bin/env bash
# Validate that the Pi service can see runtime/settings/faa_airband_catalog.json and returns nearby Airband channels.
set -euo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${REPORT_DIR}/pi5_airband_catalog_validation_${STAMP}.txt"
mkdir -p "${REPORT_DIR}"
exec > >(tee "${REPORT_PATH}") 2>&1

section() { printf '\n===== %s =====\n' "$1"; }
pass() { printf 'PASS: %s\n' "$1"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { printf 'WARN: %s\n' "$1"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { printf 'FAIL: %s\n' "$1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
finish() {
  section "Summary"
  printf 'Report path: %s\n' "${REPORT_PATH}"
  printf 'Summary: %s PASS, %s WARN, %s FAIL\n' "${PASS_COUNT}" "${WARN_COUNT}" "${FAIL_COUNT}"
  if [[ "${FAIL_COUNT}" -eq 0 ]]; then printf 'FINAL: PASS\n'; else printf 'FINAL: FAIL\n'; fi
}
trap finish EXIT

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"
BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://127.0.0.1:8090}"
CATALOG="${PI_AIR_TRAFFIC_AIRBAND_CATALOG:-${PROJECT_ROOT}/runtime/settings/faa_airband_catalog.json}"

section "Environment"
printf 'PROJECT_ROOT=%s\n' "${PROJECT_ROOT}"
printf 'BASE_URL=%s\n' "${BASE_URL}"
printf 'CATALOG=%s\n' "${CATALOG}"
[[ -f src/backend/faa_airband_catalog.py ]] && pass "catalog module exists" || fail "catalog module missing"
for cmd in python3 curl; do command -v "${cmd}" >/dev/null 2>&1 && pass "${cmd} available" || fail "${cmd} missing"; done

section "Catalog file"
if [[ ! -s "${CATALOG}" ]]; then
  fail "catalog file is missing or empty: ${CATALOG}"
  printf 'Run: ./tools/pi5_import_faa_airband_catalog.sh /path/to/FAA_NASR_*_FRQ_CSV.zip\n'
  exit 0
fi
pass "catalog file exists"
python3 - "${CATALOG}" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
print("source=%s" % data.get("source"))
print("source_archive=%s" % data.get("source_archive"))
print("channel_count=%s" % data.get("channel_count"))
print("effective_dates=%s" % ",".join(data.get("effective_dates", [])[:8]))
raise SystemExit(0 if int(data.get("channel_count") or 0) > 0 else 2)
PY
case "$?" in
  0) pass "catalog JSON has channel_count > 0" ;;
  *) fail "catalog JSON channel_count is zero"; exit 0 ;;
esac

section "Service/API catalog visibility"
status_http="$(curl -sS -m 5 -o "${REPORT_DIR}/airband_catalog_status_${STAMP}.json" -w '%{http_code}' "${BASE_URL}/api/status" || true)"
[[ "${status_http}" == "200" ]] && pass "/api/status returned HTTP 200" || fail "/api/status HTTP=${status_http}"
python3 - "${REPORT_DIR}/airband_catalog_status_${STAMP}.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    print("receiver_location=%s" % data.get("receiver_location"))
    print("airband_radius_miles=%s" % data.get("receiver_location", {}).get("airband_radius_miles"))
except Exception as exc:
    print("status_parse_error=%s" % exc)
PY

channels_http="$(curl -sS -m 10 -o "${REPORT_DIR}/airband_catalog_channels_${STAMP}.json" -w '%{http_code}' "${BASE_URL}/api/airband/channels" || true)"
[[ "${channels_http}" == "200" ]] && pass "/api/airband/channels returned HTTP 200" || fail "/api/airband/channels HTTP=${channels_http}"
channel_count="$(python3 - "${REPORT_DIR}/airband_catalog_channels_${STAMP}.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    print(data.get("channel_count", len(data.get("channels", []))))
except Exception:
    print("")
PY
)"
printf 'API_CHANNEL_COUNT=%s\n' "${channel_count}"
if [[ "${channel_count}" =~ ^[0-9]+$ && "${channel_count}" -gt 0 ]]; then
  pass "/api/airband/channels returned ${channel_count} nearby channel(s)"
  python3 - "${REPORT_DIR}/airband_catalog_channels_${STAMP}.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
for i, ch in enumerate(data.get("channels", [])[:10], 1):
    print("%02d %.3f MHz %-16s %-8s %-24s %s mi" % (
        i,
        float(ch.get("frequency_mhz", 0)),
        str(ch.get("serviced_facility", ""))[:16],
        str(ch.get("category", ""))[:8],
        str(ch.get("frequency_use", ""))[:24],
        ch.get("distance_miles", ""),
    ))
PY
else
  fail "/api/airband/channels is empty; import/restart catalog before active Airband scanner validation"
fi
