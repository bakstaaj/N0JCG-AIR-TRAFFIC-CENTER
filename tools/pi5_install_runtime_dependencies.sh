#!/usr/bin/env bash
set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
REBOOT_RECOMMENDED=0

pass() { PASS_COUNT=$((PASS_COUNT + 1)); printf 'PASS: %s\n' "$*"; }
warn() { WARN_COUNT=$((WARN_COUNT + 1)); printf 'WARN: %s\n' "$*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); printf 'FAIL: %s\n' "$*"; }

finish() {
  printf '\nPi runtime dependency installer summary:\n'
  printf '  PASS: %d\n' "$PASS_COUNT"
  printf '  WARN: %d\n' "$WARN_COUNT"
  printf '  FAIL: %d\n' "$FAIL_COUNT"
  if [[ "$REBOOT_RECOMMENDED" -eq 1 ]]; then
    printf '\nREBOOT RECOMMENDED: group membership or RTL driver blacklist changed.\n'
    printf 'Run: sudo reboot\n'
  fi
  if [[ "$FAIL_COUNT" -eq 0 ]]; then
    printf 'FINAL: PASS\n'
  else
    printf 'FINAL: FAIL\n'
  fi
}
trap finish EXIT

require_repo_root() {
  if [[ ! -d .git ]]; then
    fail "not running from a git repo root"
    exit 1
  fi
  local base
  base="$(basename "$PWD")"
  if [[ "$base" != "PI-AIR-TRAFFIC-TRACKER" && "$base" != "N0JCG-AIR-TRAFFIC-CENTER" ]]; then
    fail "expected repo root PI-AIR-TRAFFIC-TRACKER or N0JCG-AIR-TRAFFIC-CENTER, got $base"
    exit 1
  fi
  pass "repo root validated"
}

require_linux_pi() {
  if [[ ! -r /etc/os-release ]]; then
    fail "/etc/os-release not available"
    exit 1
  fi
  # shellcheck disable=SC1091
  . /etc/os-release
  printf 'INFO: OS: %s\n' "${PRETTY_NAME:-unknown}"
  if [[ "${ID:-}" == "debian" || "${ID_LIKE:-}" == *debian* || "${PRETTY_NAME:-}" == *Raspberry* ]]; then
    pass "Debian-family OS detected"
  else
    warn "OS is not clearly Debian/Raspberry Pi OS; continuing"
  fi

  local model="unknown"
  if [[ -r /proc/device-tree/model ]]; then
    model="$(tr -d '\000' </proc/device-tree/model)"
  fi
  printf 'INFO: Device model: %s\n' "$model"
  if [[ "$model" == *"Raspberry Pi 5"* ]]; then
    pass "Raspberry Pi 5 model detected"
  else
    warn "Raspberry Pi 5 model not detected; continuing"
  fi
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_packages_required() {
  local packages=(
    alsa-utils
    build-essential
    ca-certificates
    cmake
    curl
    git
    jq
    libusb-1.0-0-dev
    pkg-config
    python3
    python3-pip
    python3-venv
    rtl-sdr
    sox
    libsox-fmt-all
  )

  if ! have_cmd sudo; then
    fail "sudo is required"
    exit 1
  fi
  if ! have_cmd apt-get; then
    fail "apt-get is required"
    exit 1
  fi

  if sudo apt-get update; then
    pass "apt package index updated"
  else
    fail "apt-get update failed"
    return 0
  fi

  if sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"; then
    pass "base Pi SDR/audio/build packages installed"
  else
    fail "base package install failed"
  fi
}

install_first_available_adsb_decoder() {
  local candidates=(readsb dump1090-mutability dump1090-fa)
  local pkg
  for pkg in "${candidates[@]}"; do
    if apt-cache show "$pkg" >/dev/null 2>&1; then
      if sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg"; then
        pass "installed ADS-B decoder package: $pkg"
        disable_decoder_services
        return 0
      else
        warn "ADS-B decoder package exists but install failed: $pkg"
      fi
    fi
  done
  warn "no packaged readsb/dump1090 decoder installed; app-owned ADS-B decoder build will be added in a later patch if needed"
}

disable_decoder_services() {
  local svc
  for svc in readsb dump1090-mutability dump1090-fa dump1090; do
    if systemctl list-unit-files "$svc.service" >/dev/null 2>&1; then
      if sudo systemctl disable --now "$svc.service" >/dev/null 2>&1; then
        pass "disabled package service to avoid SDR ownership conflict: $svc.service"
      else
        warn "could not disable package service: $svc.service"
      fi
    fi
  done
}

configure_rtl_blacklist() {
  local target="/etc/modprobe.d/rtl-sdr-blacklist.conf"
  local tmp
  tmp="$(mktemp)"
  cat > "$tmp" <<'BLACKLIST'
# PI-AIR-TRAFFIC-TRACKER: keep generic DVB drivers from binding RTL-SDR receivers.
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
BLACKLIST
  if [[ -r "$target" ]] && cmp -s "$tmp" "$target"; then
    pass "RTL-SDR kernel blacklist already configured"
    rm -f "$tmp"
    return 0
  fi
  if sudo install -m 0644 "$tmp" "$target"; then
    pass "RTL-SDR kernel blacklist configured"
    REBOOT_RECOMMENDED=1
  else
    fail "failed to write RTL-SDR kernel blacklist"
  fi
  rm -f "$tmp"
}

configure_user_groups() {
  local grp
  local changed=0
  for grp in audio dialout plugdev; do
    if getent group "$grp" >/dev/null 2>&1; then
      if id -nG "$USER" | tr ' ' '\n' | grep -Fxq "$grp"; then
        pass "user already in group: $grp"
      else
        if sudo usermod -aG "$grp" "$USER"; then
          pass "added user to group: $grp"
          changed=1
        else
          warn "could not add user to group: $grp"
        fi
      fi
    else
      warn "group not present: $grp"
    fi
  done
  if [[ "$changed" -eq 1 ]]; then
    REBOOT_RECOMMENDED=1
  fi
}

validate_tools() {
  local required=(python3 git bash lsusb arecord aplay rtl_test rtl_eeprom rtl_fm rtl_sdr sox)
  local cmd
  for cmd in "${required[@]}"; do
    if have_cmd "$cmd"; then
      pass "$cmd available"
    else
      warn "$cmd not found after install"
    fi
  done

  if have_cmd readsb || have_cmd dump1090 || have_cmd dump1090-mutability || have_cmd dump1090-fa; then
    pass "ADS-B decoder command available"
  else
    warn "no ADS-B decoder command available yet"
  fi
}

main() {
  require_repo_root
  require_linux_pi
  install_packages_required
  install_first_available_adsb_decoder
  configure_rtl_blacklist
  configure_user_groups
  validate_tools
}

main "$@"
