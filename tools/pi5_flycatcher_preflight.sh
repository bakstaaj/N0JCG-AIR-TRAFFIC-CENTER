#!/usr/bin/env bash
# Pi-side hardware/software preflight for Raspberry Pi 5 + FlyCatcher + NESDR Nano2+.
# Run on the Raspberry Pi, not in MSYS2.

set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() { printf 'PASS: %s\n' "$*"; PASS_COUNT=$((PASS_COUNT + 1)); return 0; }
warn() { printf 'WARN: %s\n' "$*"; WARN_COUNT=$((WARN_COUNT + 1)); return 0; }
fail() { printf 'FAIL: %s\n' "$*"; FAIL_COUNT=$((FAIL_COUNT + 1)); return 0; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

printf '=== Pi 5 FlyCatcher/NESDR preflight ===\n'

if [[ "$(uname -s 2>/dev/null || true)" == "Linux" ]]; then pass "Linux host detected"; else fail "not running on Linux"; fi

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  printf 'OS: %s\n' "${PRETTY_NAME:-unknown}"
  case "${VERSION_CODENAME:-}" in
    trixie) pass "Debian/Raspberry Pi OS Trixie codename detected" ;;
    *) warn "Trixie codename not detected: ${VERSION_CODENAME:-unknown}" ;;
  esac
else
  warn "/etc/os-release not readable"
fi

if have_cmd python3; then pass "python3 available"; else fail "python3 missing"; fi
if have_cmd rtl_test; then pass "rtl_test available"; else fail "rtl_test missing; install rtl-sdr package"; fi
if have_cmd rtl_eeprom; then pass "rtl_eeprom available"; else warn "rtl_eeprom missing; serial assignment checks limited"; fi
if have_cmd rtl_fm; then pass "rtl_fm available"; else fail "rtl_fm missing; audio receiver cannot run"; fi
if have_cmd rtl_power; then pass "rtl_power available"; else warn "rtl_power missing; fast spectrum scanner cannot run"; fi

if have_cmd lsusb; then
  USB_COUNT="$(lsusb | wc -l | tr -d ' ')"
  printf 'USB device rows: %s\n' "$USB_COUNT"
  pass "lsusb available"
else
  warn "lsusb missing"
fi

if have_cmd rtl_test; then
  TMP_RTL="$(mktemp)"
  if timeout 15 rtl_test -t >"$TMP_RTL" 2>&1; then
    pass "rtl_test tuner probe completed"
  else
    warn "rtl_test returned nonzero; continuing with captured output"
  fi
  sed -n '1,80p' "$TMP_RTL"
  FOUND_COUNT="$(python3 - "$TMP_RTL" <<'PY'
import re, sys
p=sys.argv[1]
text=open(p, errors='ignore').read()
m=re.search(r'Found\s+(\d+)\s+device', text)
print(m.group(1) if m else "unknown")
PY
)"
  printf 'RTL-SDR reported device count: %s\n' "$FOUND_COUNT"
  if [[ "$FOUND_COUNT" == "unknown" ]]; then
    warn "could not parse RTL-SDR device count"
  elif [[ "$FOUND_COUNT" -ge 3 ]]; then
    pass "expected three RTL-SDR receivers detected for FlyCatcher ADS-B/UAT plus Nano2+"
  else
    fail "expected at least three RTL-SDR receivers, found $FOUND_COUNT"
  fi
  rm -f "$TMP_RTL"
fi

if [[ -d src ]]; then
  PY_FILES="$(find src tools -type f -name '*.py' 2>/dev/null | tr '\n' ' ')"
  if [[ -n "$PY_FILES" ]]; then
    if python3 -m py_compile $PY_FILES; then pass "Python files compile"; else fail "Python compile failed"; fi
  else
    warn "no Python files found for compile check"
  fi
else
  warn "run this from the repository root for source compile checks"
fi

if [[ -f web/app.js ]] && have_cmd node; then
  if node --check web/app.js; then pass "web/app.js JavaScript syntax valid"; else fail "web/app.js JavaScript syntax invalid"; fi
elif [[ -f web/index.html ]] && have_cmd node; then
  TMP_JS="$(mktemp --suffix=.js)"
  python3 - "$TMP_JS" <<'PY'
from pathlib import Path
import re, sys
html = Path("web/index.html").read_text(encoding="utf-8", errors="ignore")
Path(sys.argv[1]).write_text("\n\n".join(re.findall(r"<script>(.*?)</script>", html, flags=re.S)), encoding="utf-8")
PY
  if node --check "$TMP_JS"; then pass "inline JavaScript syntax valid"; else fail "inline JavaScript syntax invalid"; fi
  rm -f "$TMP_JS"
else
  warn "node not available or no web JavaScript found; skipped JavaScript syntax check"
fi

printf '\nSummary: %s PASS, %s WARN, %s FAIL\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"
if (( FAIL_COUNT > 0 )); then
  printf 'FINAL: FAIL\n'
  exit 1
fi
printf 'FINAL: PASS\n'
