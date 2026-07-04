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

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  info "OS: ${PRETTY_NAME:-unknown}"
  case "${PRETTY_NAME:-}" in
    *Trixie*|*trixie*|*Debian*13*|*Raspberry*Pi*OS*) pass "Linux OS information available" ;;
    *) warn "OS is not clearly Raspberry Pi OS Trixie; continue only if this is the intended Pi image" ;;
  esac
else
  warn "/etc/os-release not readable"
fi

if command -v uname >/dev/null 2>&1; then
  info "Kernel: $(uname -a)"
  pass "kernel information available"
else
  warn "uname not found"
fi

if [[ -r /proc/device-tree/model ]]; then
  model="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)"
  info "Device model: $model"
  if [[ "$model" == *"Raspberry Pi 5"* ]]; then
    pass "Raspberry Pi 5 model detected"
  else
    warn "device model is not Raspberry Pi 5"
  fi
else
  warn "Raspberry Pi device model file not readable"
fi

for cmd in python3 git bash; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$cmd available"
  else
    fail "$cmd missing"
  fi
done

for cmd in rtl_test rtl_eeprom rtl_fm rtl_sdr lsusb arecord aplay sox; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$cmd available"
  else
    warn "$cmd not found yet"
  fi
done

if command -v readsb >/dev/null 2>&1; then
  pass "readsb available"
elif command -v dump1090 >/dev/null 2>&1; then
  pass "dump1090 available"
else
  warn "neither readsb nor dump1090 found yet"
fi

if command -v python3 >/dev/null 2>&1; then
  if python3 - <<'PY'
import compileall
import pathlib
import sys
roots = [pathlib.Path('src'), pathlib.Path('tools')]
ok = True
for root in roots:
    if root.exists():
        for path in root.rglob('*.py'):
            ok = compileall.compile_file(str(path), quiet=1) and ok
sys.exit(0 if ok else 1)
PY
  then
    pass "Python compile validation clean"
  else
    fail "Python compile validation failed"
  fi
fi

if [[ -f web/app.js ]]; then
  if command -v node >/dev/null 2>&1; then
    if node --check web/app.js >/dev/null 2>&1; then
      pass "web/app.js syntax valid"
    else
      fail "web/app.js syntax invalid"
    fi
  else
    warn "node not installed on Pi; skipped web/app.js syntax check"
  fi
fi

if [[ -f runtime/settings/pi_air_traffic_hardware_roles.template.json ]]; then
  if python3 -m json.tool runtime/settings/pi_air_traffic_hardware_roles.template.json >/dev/null 2>&1; then
    pass "hardware role template JSON valid"
  else
    fail "hardware role template JSON invalid"
  fi
else
  warn "hardware role template not found"
fi

for port in 8090 8091; do
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn "sport = :$port" 2>/dev/null | tail -n +2 | grep -q .; then
      warn "TCP port $port already appears to be listening"
    else
      pass "TCP port $port appears free"
    fi
  else
    warn "ss not available; skipped TCP port $port check"
  fi
done

echo
printf 'Summary: %d PASS, %d WARN, %d FAIL\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  echo "FINAL: PASS"
  exit 0
else
  echo "FINAL: FAIL"
  exit 1
fi
