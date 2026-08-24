#!/usr/bin/env bash
# Bootstrap baseline Pi 5 Trixie packages for PI-AIR-TRAFFIC-TRACKER.
# Run on the Raspberry Pi. This does not install a service yet.

set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() { printf 'PASS: %s\n' "$*"; PASS_COUNT=$((PASS_COUNT + 1)); return 0; }
warn() { printf 'WARN: %s\n' "$*"; WARN_COUNT=$((WARN_COUNT + 1)); return 0; }
fail() { printf 'FAIL: %s\n' "$*"; FAIL_COUNT=$((FAIL_COUNT + 1)); return 0; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

printf '=== Bootstrap Pi 5 Trixie runtime packages ===\n'

if [[ "$(uname -s 2>/dev/null || true)" != "Linux" ]]; then
  fail "this script must run on the Raspberry Pi/Linux target"
  printf 'FINAL: FAIL\n'
  exit 1
fi

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  printf 'OS: %s\n' "${PRETTY_NAME:-unknown}"
else
  warn "/etc/os-release not readable"
fi

if have_cmd sudo; then SUDO=sudo; else SUDO=; fi

if have_cmd apt-get; then
  pass "apt-get available"
else
  fail "apt-get missing"
  printf 'FINAL: FAIL\n'
  exit 1
fi

$SUDO apt-get update

$SUDO apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  make \
  build-essential \
  cmake \
  pkg-config \
  python3 \
  python3-venv \
  python3-pip \
  nodejs \
  npm \
  rtl-sdr \
  usbutils \
  sox \
  alsa-utils

if have_cmd rtl_test; then pass "rtl_test installed"; else fail "rtl_test unavailable after install"; fi
if have_cmd rtl_fm; then pass "rtl_fm installed"; else fail "rtl_fm unavailable after install"; fi
if have_cmd rtl_power; then pass "rtl_power installed"; else warn "rtl_power unavailable after install"; fi
if have_cmd python3; then pass "python3 installed"; else fail "python3 unavailable after install"; fi
if have_cmd node; then pass "node installed"; else warn "node unavailable after install"; fi

cat <<'NOTE'

Next manual hardware checks:
  - Connect FlyCatcher ADS-B USB side.
  - Connect FlyCatcher UAT USB side, even though UAT integration is reserved for later.
  - Connect the NESDR Nano2+ for NOAA and the dedicated RTL receiver for Airband.
  - Run: ./tools/pi5_flycatcher_preflight.sh

Serial role assignment will be finalized in the next port checkpoint after the devices enumerate cleanly.
NOTE

printf '\nSummary: %s PASS, %s WARN, %s FAIL\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"
if (( FAIL_COUNT > 0 )); then
  printf 'FINAL: FAIL\n'
  exit 1
fi
printf 'FINAL: PASS\n'
