#!/usr/bin/env bash
set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() { echo "PASS: $*"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "WARN: $*"; WARN_COUNT=$((WARN_COUNT + 1)); return 0; }
fail() { echo "FAIL: $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); return 0; }
info() { echo "INFO: $*"; }

if [[ ! -d .git || ! -d web || ! -d tools ]]; then
  echo "FAIL: run this script from the PI-AIR-TRAFFIC-TRACKER repo root" >&2
  exit 1
fi
pass "repo root validated"

out_dir="runtime/preflight"
mkdir -p "$out_dir"
stamp="$(date +%Y%m%d_%H%M%S)"
report="$out_dir/hardware_arrival_checklist_$stamp.txt"

{
  echo "PI Air Traffic Tracker hardware arrival checklist"
  echo "Timestamp: $stamp"
  echo
  echo "Expected connected SDR roles:"
  echo "  - FlyCatcher ADS-B side: 1090 MHz, active now"
  echo "  - FlyCatcher UAT side: 978 MHz, reserved for later"
  echo "  - NESDR Nano2+: NOAA NFM and civil airband AM, active now"
  echo
  echo "Commands and captured output:"
  echo
} > "$report"

capture_cmd() {
  local label="$1"
  shift
  {
    echo "===== $label ====="
    if "$@"; then
      echo "===== END $label: exit 0 ====="
    else
      local rc=$?
      echo "===== END $label: exit $rc ====="
    fi
    echo
  } >> "$report" 2>&1
}

if command -v lsusb >/dev/null 2>&1; then
  capture_cmd "lsusb" lsusb
  pass "captured lsusb"
else
  warn "lsusb not available"
fi

if command -v rtl_test >/dev/null 2>&1; then
  capture_cmd "rtl_test -t" rtl_test -t
  pass "captured rtl_test -t"
else
  warn "rtl_test not available"
fi

if command -v rtl_eeprom >/dev/null 2>&1; then
  capture_cmd "rtl_eeprom" rtl_eeprom
  pass "captured rtl_eeprom"
else
  warn "rtl_eeprom not available"
fi

if [[ -d /dev ]]; then
  {
    echo "===== /dev SDR candidates ====="
    ls -l /dev/rtl* /dev/bus/usb/*/* 2>/dev/null || true
    echo
  } >> "$report"
  pass "captured /dev SDR candidate listing"
fi

cat >> "$report" <<'EOF_REPORT'
Manual notes to fill in after reviewing this file:

1. Which enumerated RTL device is FlyCatcher ADS-B side?
2. Which enumerated RTL device is FlyCatcher UAT side?
3. Which enumerated RTL device is NESDR Nano2+?
4. Are serial numbers already unique and useful?
5. If serials are duplicated/default, should we set explicit serials before service work?
6. Is ADS-B 1090 service allowed to own its device continuously?
7. Confirm NOAA and Airband use separate receivers: 00000162 and 00000118.
EOF_REPORT

info "report written: $report"
pass "hardware checklist report created"

echo
printf 'Summary: %d PASS, %d WARN, %d FAIL\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  echo "FINAL: PASS"
  exit 0
else
  echo "FINAL: FAIL"
  exit 1
fi
