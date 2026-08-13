#!/usr/bin/env bash
# Remote first-deployment workflow. Invoked by install_pi_initial_deployment.sh.

set -Eeuo pipefail

BUNDLE_PATH="${1:?bundle path required}"
APP_USER="${2:?application user required}"
SOURCE_REVISION="${3:-unknown}"
APP_ROOT="/home/${APP_USER}/n0jcg-air-traffic-center"

pass() { printf 'PASS: %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
section() { printf '\n===== %s =====\n' "$*"; }
run_as_user() { sudo -u "$APP_USER" env HOME="/home/$APP_USER" "$@"; }

[[ "$(uname -s)" == "Linux" ]] || fail "this workflow must run on the Raspberry Pi"
command -v sudo >/dev/null 2>&1 || fail "sudo is required"
command -v tar >/dev/null 2>&1 || fail "tar is required"
[[ -f "$BUNDLE_PATH" ]] || fail "uploaded bundle not found: $BUNDLE_PATH"

section "Prepare application directory"
sudo install -d -o "$APP_USER" -g "$(id -gn "$APP_USER")" -m 0755 "$APP_ROOT"
sudo tar -xzf "$BUNDLE_PATH" --strip-components=1 -C "$APP_ROOT"
sudo chown -R "$APP_USER":"$(id -gn "$APP_USER")" "$APP_ROOT"
sudo install -d -o "$APP_USER" -g "$(id -gn "$APP_USER")" -m 0755 "$APP_ROOT/.git"
pass "installed committed revision $SOURCE_REVISION into $APP_ROOT"

cd "$APP_ROOT"
export PI_AIR_TRAFFIC_ADSB_SERIAL=00001090
export PI_AIR_TRAFFIC_AUDIO_SERIAL=00000162
export PI_AIR_TRAFFIC_UAT_SERIAL=00000978
export PI_AIR_TRAFFIC_WEB_HOST=0.0.0.0
export PI_AIR_TRAFFIC_WEB_PORT=8090

section "Install operating-system components"
./tools/pi5_install_runtime_dependencies.sh
./tools/pi5_install_app_owned_readsb.sh
./tools/pi5_install_app_owned_dump978.sh

section "Program RTL-SDR serial numbers one receiver at a time"
printf '%s\n' \
  'Safety: disconnect every RTL-SDR except the receiver currently being programmed.' \
  'The workflow uses device index 0 only after you confirm that one receiver is connected.' \
  'Never guess between the two FlyCatcher paths; use the board labels and antenna role.'

program_role() {
  local role="$1" serial="$2" backup="$3" confirmation current
  printf '\n--- %s -> serial %s ---\n' "$role" "$serial"
  read -r -p "Connect only the $role receiver, then press Enter. " _
  rtl_test -t || fail "rtl_test could not enumerate the $role receiver"
  mkdir -p runtime/preflight/serial-backups
  sudo rtl_eeprom -d 0 -r "runtime/preflight/serial-backups/$backup" || fail "EEPROM backup failed for $role"
  printf 'EEPROM backup saved: runtime/preflight/serial-backups/%s\n' "$backup"
  current="$(rtl_eeprom -d 0 2>&1 || true)"
  printf '%s\n' "$current" | sed -n '1,18p'
  read -r -p "Type PROGRAM to write serial $serial to this confirmed $role receiver: " confirmation
  [[ "$confirmation" == PROGRAM ]] || fail "serial programming cancelled for $role"
  sudo rtl_eeprom -d 0 -s "$serial" || fail "serial write failed for $role"
  printf '%s\n' 'Disconnect/reconnect this receiver, keep the other receivers disconnected, then press Enter.'
  read -r _
  rtl_test -t | tee "runtime/preflight/${role//[^A-Za-z0-9]/_}_after_write.txt"
  if ! grep -q "SN: $serial" "runtime/preflight/${role//[^A-Za-z0-9]/_}_after_write.txt"; then
    fail "$role did not report expected serial $serial after write"
  fi
  pass "$role reports serial $serial"
}

program_role "ADS-B 1090 / FlyCatcher ADS-B side" 00001090 adsb_1090_eeprom_before.bin
program_role "NOAA/Airband 162 / NESDR Nano2+" 00000162 noaa_airband_eeprom_before.bin
program_role "UAT 978 / FlyCatcher UAT side" 00000978 uat_978_eeprom_before.bin

section "Reconnect all receivers and validate roles before service startup"
printf '%s\n' 'Reconnect all three receivers, confirm their antennas, and press Enter.'
read -r _
./tools/pi5_validate_receiver_serial_mapping.sh || fail "receiver serial mapping validation failed"
[[ -f runtime/settings/pi_air_traffic_hardware_roles.detected.json ]] || fail "detected role mapping JSON was not created"
[[ -x runtime/bin/readsb ]] || fail "app-owned readsb is not executable"
runtime/bin/readsb --help 2>&1 | grep -Eiq 'rtlsdr|rtl-sdr|device-type' || fail "readsb RTL-SDR capability check failed"
pass "pre-service receiver and decoder validation passed"

section "Install, enable, and validate services"
sudo ./tools/pi5_install_systemd_service.sh
./tools/pi5_validate_systemd_service.sh
./tools/pi5_validate_ui_api_smoke.sh

section "Operator handoff"
PI_IP="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+(\.[0-9]+){3}$' | head -n 1 || true)"
printf 'Open a browser to: http://%s:8090\n' "${PI_IP:-<pi-ip-address>}"
printf 'The N0JCG Air Traffic Center should now be available on the LAN.\n'
