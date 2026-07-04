#!/usr/bin/env bash
# Import a FAA NASR FRQ CSV ZIP into runtime/settings/faa_airband_catalog.json and validate nearby channels.
# This is intentionally a Pi-side runtime-data helper; the generated JSON is not committed.
set -euo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${REPORT_DIR}/pi5_import_faa_airband_catalog_${STAMP}.txt"

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
  if [[ "${FAIL_COUNT}" -eq 0 ]]; then
    printf 'FINAL: PASS\n'
  else
    printf 'FINAL: FAIL\n'
  fi
}
trap finish EXIT

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://127.0.0.1:8090}"
OUTPUT="${PI_AIR_TRAFFIC_AIRBAND_CATALOG:-${PROJECT_ROOT}/runtime/settings/faa_airband_catalog.json}"
ZIP_ARG="${1:-}"

section "Environment"
printf 'PROJECT_ROOT=%s\n' "${PROJECT_ROOT}"
printf 'BASE_URL=%s\n' "${BASE_URL}"
printf 'OUTPUT=%s\n' "${OUTPUT}"
[[ -f src/backend/faa_airband_catalog.py ]] && pass "catalog importer module exists" || fail "src/backend/faa_airband_catalog.py missing"
for cmd in python3 curl unzip; do
  if command -v "${cmd}" >/dev/null 2>&1; then
    pass "${cmd} available at $(command -v "${cmd}")"
  else
    fail "${cmd} is required but not available"
  fi
done

section "Resolve FAA FRQ ZIP"
declare -a candidates=()
if [[ -n "${ZIP_ARG}" ]]; then
  candidates+=("${ZIP_ARG}")
fi
if [[ -n "${FAA_FRQ_ZIP:-}" ]]; then
  candidates+=("${FAA_FRQ_ZIP}")
fi
candidates+=(
  "${PROJECT_ROOT}/runtime/sources/FAA_NASR_FRQ_CSV.zip"
  "${PROJECT_ROOT}/runtime/sources/FAA_NASR_2026-05-14_FRQ_CSV.zip"
  "${HOME}/Downloads/FAA_NASR_FRQ_CSV.zip"
)
while IFS= read -r found; do
  [[ -n "${found}" ]] && candidates+=("${found}")
done < <(find "${HOME}/Downloads" /tmp "${PROJECT_ROOT}/runtime/sources" -maxdepth 1 -type f \( -iname '*FRQ*CSV*.zip' -o -iname '*NASR*FRQ*.zip' -o -iname '*FRQ*.zip' \) 2>/dev/null | sort -r)

FRQ_ZIP=""
for candidate in "${candidates[@]}"; do
  if [[ -s "${candidate}" ]]; then
    FRQ_ZIP="${candidate}"
    break
  fi
done

if [[ -z "${FRQ_ZIP}" ]]; then
  fail "FAA FRQ CSV ZIP not found"
  cat <<'HELP'
Copy the FAA NASR FRQ CSV ZIP to the Pi, then rerun this command with the file path.
Example from Windows MSYS2:
  scp -O /c/Users/jim/Downloads/FAA_NASR_2026-05-14_FRQ_CSV.zip pi@192.168.254.63:/tmp/

Example on the Pi:
  ./tools/pi5_import_faa_airband_catalog.sh /tmp/FAA_NASR_2026-05-14_FRQ_CSV.zip
HELP
  exit 0
fi
pass "selected FAA FRQ ZIP: ${FRQ_ZIP}"
unzip -l "${FRQ_ZIP}" | sed -n '1,25p'
if unzip -l "${FRQ_ZIP}" | awk '{print $4}' | grep -Eiq '(^|/)FRQ\.CSV$'; then
  pass "FRQ.CSV is present inside ZIP"
else
  fail "FRQ.CSV was not found inside ZIP"
  exit 0
fi

section "Import catalog"
python3 src/backend/faa_airband_catalog.py --frq-zip "${FRQ_ZIP}" --output "${OUTPUT}" > "${REPORT_DIR}/faa_airband_catalog_import_${STAMP}.json"
cat "${REPORT_DIR}/faa_airband_catalog_import_${STAMP}.json"
if [[ -s "${OUTPUT}" ]]; then
  pass "catalog output exists: ${OUTPUT}"
else
  fail "catalog output was not created: ${OUTPUT}"
  exit 0
fi

python3 - "${OUTPUT}" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
print("CATALOG_CHANNEL_COUNT=%s" % data.get("channel_count"))
print("CATALOG_SOURCE_ARCHIVE=%s" % data.get("source_archive"))
print("CATALOG_EFFECTIVE_DATES=%s" % ",".join(data.get("effective_dates", [])[:5]))
count = int(data.get("channel_count") or 0)
raise SystemExit(0 if count > 0 else 2)
PY
case "$?" in
  0) pass "catalog contains airband channels" ;;
  *) fail "catalog channel_count was zero"; exit 0 ;;
esac

section "Restart service if active"
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet pi-air-traffic-tracker.service; then
  sudo systemctl restart pi-air-traffic-tracker.service
  pass "restarted pi-air-traffic-tracker.service to reload catalog"
else
  warn "pi-air-traffic-tracker.service is not active; skipping service restart"
fi

section "Validate API channels"
for attempt in $(seq 1 30); do
  http="$(curl -sS -m 3 -o "${REPORT_DIR}/airband_channels_after_import_${STAMP}.json" -w '%{http_code}' "${BASE_URL}/api/airband/channels" || true)"
  if [[ "${http}" == "200" ]]; then
    channel_count="$(python3 - "${REPORT_DIR}/airband_channels_after_import_${STAMP}.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    print(data.get("channel_count", len(data.get("channels", []))))
except Exception:
    print("")
PY
)"
    printf 'CHANNEL_ATTEMPT=%s HTTP=%s CHANNEL_COUNT=%s\n' "${attempt}" "${http}" "${channel_count}"
    if [[ "${channel_count}" =~ ^[0-9]+$ && "${channel_count}" -gt 0 ]]; then
      pass "/api/airband/channels returned ${channel_count} nearby channel(s)"
      python3 - "${REPORT_DIR}/airband_channels_after_import_${STAMP}.json" <<'PY'
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
      exit 0
    fi
  else
    printf 'CHANNEL_ATTEMPT=%s HTTP=%s\n' "${attempt}" "${http}"
  fi
  sleep 1
done
fail "/api/airband/channels did not return nearby channels after import"
