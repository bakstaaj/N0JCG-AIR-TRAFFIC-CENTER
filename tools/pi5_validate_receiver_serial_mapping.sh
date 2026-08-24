#!/usr/bin/env bash
# Validate serial-based receiver mapping on Raspberry Pi 5 with FlyCatcher + NESDR Nano2+.

set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() { echo "PASS: $*"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "WARN: $*"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "FAIL: $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

if [[ ! -d .git || ! -d runtime || ! -d tools ]]; then
  echo "FAIL: run from PI-AIR-TRAFFIC-TRACKER repository root" >&2
  exit 1
fi
pass "repo root validated"

mkdir -p runtime/preflight runtime/settings
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT="runtime/preflight/pi5_receiver_serial_mapping_${STAMP}.txt"
DETECTED_JSON="runtime/settings/pi_air_traffic_hardware_roles.detected.json"

{
  echo "=== Pi 5 receiver serial mapping validation ==="
  date -Is
  echo
  echo "uname: $(uname -a)"
  if [[ -r /etc/os-release ]]; then
    echo "os-release:"
    sed -n '1,12p' /etc/os-release
  fi
  echo
  echo "=== lsusb ==="
  lsusb || true
  echo
  echo "=== rtl_test -t ==="
  rtl_test -t 2>&1 || true
  echo
  echo "=== rtl_eeprom ==="
  rtl_eeprom 2>&1 || true
} > "$REPORT"
pass "captured receiver serial mapping report: $REPORT"

if ! command -v rtl_test >/dev/null 2>&1; then
  fail "rtl_test unavailable"
else
  pass "rtl_test available"
fi

if ! command -v rtl_eeprom >/dev/null 2>&1; then
  fail "rtl_eeprom unavailable"
else
  pass "rtl_eeprom available"
fi

python3 - "$REPORT" "$DETECTED_JSON" <<'PY'
from pathlib import Path
import json
import re
import sys

report_path = Path(sys.argv[1])
detected_path = Path(sys.argv[2])
text = report_path.read_text(encoding="utf-8", errors="replace")

# rtl_test lines normally look like:
#   0:  Realtek, RTL2838UHIDIR, SN: 00000162
#   1:  Nooelec, FlyCatcher_UAT, SN: 00000978
#   2:  Nooelec, FlyCatcher_ADS_B, SN: 00001090
pattern = re.compile(r"^\s*(\d+):\s+(.*?),\s+(.*?),\s+SN:\s*(\S+)\s*$", re.MULTILINE)
devices = []
for match in pattern.finditer(text):
    devices.append({
        "index": int(match.group(1)),
        "vendor": match.group(2).strip(),
        "product": match.group(3).strip(),
        "serial": match.group(4).strip(),
    })

expected = {
    "noaa": "00000162",
    "airband": "00000118",
    "adsb_1090": "00001090",
    "uat_978": "00000978",
}
by_serial = {device["serial"]: device for device in devices}
missing = [serial for serial in expected.values() if serial not in by_serial]
duplicate_serials = sorted({device["serial"] for device in devices if [d["serial"] for d in devices].count(device["serial"]) > 1})

roles = {}
for role, serial in expected.items():
    device = by_serial.get(serial)
    roles[role] = {
        "rtl_serial": serial,
        "rtl_index": device["index"] if device else None,
        "vendor": device["vendor"] if device else None,
        "product": device["product"] if device else None,
        "enabled": role != "uat_978",
    }

payload = {
    "ok": not missing and not duplicate_serials and len(devices) >= 4,
    "schema_version": 2,
    "generated_from": str(report_path),
    "mapping_strategy": "resolve_runtime_index_from_rtl_serial",
    "expected_serials": expected,
    "device_count": len(devices),
    "devices": devices,
    "roles": roles,
    "missing_expected_serials": missing,
    "duplicate_serials": duplicate_serials,
}
detected_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")

print(json.dumps({
    "ok": payload["ok"],
    "device_count": len(devices),
    "missing_expected_serials": missing,
    "duplicate_serials": duplicate_serials,
    "roles": roles,
}, indent=2))

if not payload["ok"]:
    sys.exit(2)
PY
PY_STATUS=$?
if [[ "$PY_STATUS" -eq 0 ]]; then
  pass "expected serial mapping detected"
else
  fail "expected serial mapping not detected"
fi

if python3 -m json.tool "$DETECTED_JSON" >/dev/null; then
  pass "detected mapping JSON valid: $DETECTED_JSON"
else
  fail "detected mapping JSON invalid: $DETECTED_JSON"
fi

if [[ -f runtime/settings/pi_air_traffic_hardware_roles.pi5-flycatcher-serials.json ]]; then
  if python3 -m json.tool runtime/settings/pi_air_traffic_hardware_roles.pi5-flycatcher-serials.json >/dev/null; then
    pass "serial role template JSON valid"
  else
    fail "serial role template JSON invalid"
  fi
else
  warn "serial role template not present in this checkout"
fi

echo
echo "Report path: $REPORT"
echo "Detected mapping JSON: $DETECTED_JSON"
echo
echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  echo "FINAL: PASS"
  exit 0
fi
echo "FINAL: FAIL"
exit 1
