#!/usr/bin/env bash
# Install and validate the PI Air Traffic Tracker systemd service.

set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="$REPORT_DIR/pi5_systemd_service_install_${STAMP}.txt"
SERVICE_NAME="${PI_AIR_TRAFFIC_SERVICE_NAME:-pi-air-traffic-tracker.service}"
WEB_HOST="${PI_AIR_TRAFFIC_WEB_HOST:-0.0.0.0}"
WEB_PORT="${PI_AIR_TRAFFIC_WEB_PORT:-8090}"
ADSB_SERIAL="${PI_AIR_TRAFFIC_ADSB_SERIAL:-00001090}"
AUDIO_SERIAL="${PI_AIR_TRAFFIC_AUDIO_SERIAL:-00000162}"
AIRBAND_SERIAL="${PI_AIR_TRAFFIC_AIRBAND_SERIAL:-00000118}"
UAT_SERIAL="${PI_AIR_TRAFFIC_UAT_SERIAL:-00000978}"

pass() { echo "PASS: $*" | tee -a "$REPORT_PATH"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "WARN: $*" | tee -a "$REPORT_PATH"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "FAIL: $*" | tee -a "$REPORT_PATH"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
section() { echo "" | tee -a "$REPORT_PATH"; echo "===== $* =====" | tee -a "$REPORT_PATH"; }

mkdir -p "$REPORT_DIR" runtime/logs runtime/settings runtime/bin
: > "$REPORT_PATH"

if [[ "$(uname -s)" != "Linux" || -n "${MSYSTEM:-}" ]]; then
  echo "FAIL: run this installer on the Raspberry Pi, not MSYS2/Windows" | tee -a "$REPORT_PATH"
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "FAIL: run with sudo from the Pi repository root" | tee -a "$REPORT_PATH"
  echo "Example: sudo ./tools/pi5_install_systemd_service.sh" | tee -a "$REPORT_PATH"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
cd "$APP_ROOT"

if [[ ! -d .git || ! -f src/backend/pi_air_traffic_backend.py || ! -f web/index.html ]]; then
  fail "repository root validation failed: $APP_ROOT"
  exit 1
fi
pass "repo root validated: $APP_ROOT"

if [[ -n "${PI_AIR_TRAFFIC_SERVICE_USER:-}" ]]; then
  APP_USER="$PI_AIR_TRAFFIC_SERVICE_USER"
elif [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
  APP_USER="$SUDO_USER"
else
  APP_USER="$(stat -c '%U' "$APP_ROOT")"
fi
APP_GROUP="$(id -gn "$APP_USER")"
pass "service user resolved: ${APP_USER}:${APP_GROUP}"

section "Prerequisite checks"
if [[ -x runtime/bin/readsb ]]; then
  pass "app-owned readsb executable exists: runtime/bin/readsb"
else
  fail "runtime/bin/readsb missing; run ./tools/pi5_install_app_owned_readsb.sh before installing service"
fi

if runtime/bin/readsb --help 2>&1 | grep -Eiq 'rtlsdr|rtl-sdr|device-type'; then
  pass "app-owned readsb help includes RTL/device markers"
else
  fail "app-owned readsb did not show RTL/device markers"
fi

for cmd in python3 rtl_test systemctl; do
  if command -v "$cmd" >/dev/null 2>&1; then pass "$cmd available"; else fail "$cmd missing"; fi
done

if rtl_test -t > "runtime/preflight/pi5_systemd_install_rtl_test_${STAMP}.txt" 2>&1; then
  if grep -q "SN: ${ADSB_SERIAL}" "runtime/preflight/pi5_systemd_install_rtl_test_${STAMP}.txt" && \
     grep -q "SN: ${AUDIO_SERIAL}" "runtime/preflight/pi5_systemd_install_rtl_test_${STAMP}.txt" && \
     grep -q "SN: ${AIRBAND_SERIAL}" "runtime/preflight/pi5_systemd_install_rtl_test_${STAMP}.txt" && \
     grep -q "SN: ${UAT_SERIAL}" "runtime/preflight/pi5_systemd_install_rtl_test_${STAMP}.txt"; then
    pass "expected receiver serials visible"
  else
    fail "expected receiver serials not all visible; see runtime/preflight/pi5_systemd_install_rtl_test_${STAMP}.txt"
  fi
else
  fail "rtl_test -t failed; see runtime/preflight/pi5_systemd_install_rtl_test_${STAMP}.txt"
fi

if [[ "$FAIL_COUNT" -ne 0 ]]; then
  echo "" | tee -a "$REPORT_PATH"
  echo "Report path: $REPORT_PATH" | tee -a "$REPORT_PATH"
  echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL" | tee -a "$REPORT_PATH"
  echo "FINAL: FAIL" | tee -a "$REPORT_PATH"
  exit 1
fi

section "Runtime ownership"
mkdir -p runtime/logs runtime/settings runtime/audio runtime/noaa runtime/airband runtime/bin
chown -R "${APP_USER}:${APP_GROUP}" runtime
usermod -aG plugdev,audio,video,dialout "$APP_USER" 2>/dev/null || warn "could not add $APP_USER to all SDR/audio groups; continuing"
pass "runtime directories prepared"

section "Installing dump978 log rotation"
LOGROTATE_PATH="/etc/logrotate.d/n0jcg-air-traffic-center"
cat > "$LOGROTATE_PATH" <<LOGROTATE
${APP_ROOT}/runtime/logs/dump978_uat_978.log {
    su ${APP_USER} ${APP_GROUP}
    size 10M
    rotate 3
    daily
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
}
LOGROTATE
chmod 0644 "$LOGROTATE_PATH"
pass "dump978 log rotation configured at 10 MB: $LOGROTATE_PATH"

section "Disabling conflicting distro readsb service"
systemctl disable --now readsb.service >/dev/null 2>&1 || true
if systemctl is-active --quiet readsb.service 2>/dev/null; then
  fail "readsb.service is still active and may own the ADS-B receiver"
else
  pass "distro readsb.service is not active"
fi

section "Writing systemd unit"
cat > "/etc/systemd/system/${SERVICE_NAME}" <<UNIT
[Unit]
Description=PI Air Traffic Tracker Web/API Service
After=network-online.target
Wants=network-online.target
Conflicts=readsb.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
SupplementaryGroups=plugdev audio video dialout
WorkingDirectory=${APP_ROOT}
Environment=PYTHONUNBUFFERED=1
Environment=RTL_ADSB_TRACKER_ROOT=${APP_ROOT}
Environment=RTL_ADSB_TRACKER_RUNTIME=${APP_ROOT}/runtime
Environment=PI_AIR_TRAFFIC_ADSB_SERIAL=${ADSB_SERIAL}
Environment=PI_AIR_TRAFFIC_AUDIO_SERIAL=${AUDIO_SERIAL}
Environment=PI_AIR_TRAFFIC_AIRBAND_SERIAL=${AIRBAND_SERIAL}
Environment=PI_AIR_TRAFFIC_UAT_SERIAL=${UAT_SERIAL}
Environment=PATH=${APP_ROOT}/runtime/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/usr/bin/python3 ${APP_ROOT}/src/backend/pi_air_traffic_backend.py --host ${WEB_HOST} --port ${WEB_PORT} --autostart --foreground-log --log-file ${APP_ROOT}/runtime/logs/pi_air_traffic_tracker_service.log --log-level INFO
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
pass "wrote /etc/systemd/system/${SERVICE_NAME}"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null
systemctl restart "$SERVICE_NAME"
pass "enabled and restarted $SERVICE_NAME"

sleep 3

section "Service validation"
if ./tools/pi5_validate_systemd_service.sh; then
  pass "systemd service validator passed"
else
  fail "systemd service validator failed"
fi

if [[ "$FAIL_COUNT" -eq 0 ]]; then FINAL="PASS"; else FINAL="FAIL"; fi

echo "" | tee -a "$REPORT_PATH"
echo "Report path: $REPORT_PATH" | tee -a "$REPORT_PATH"
echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL" | tee -a "$REPORT_PATH"
echo "FINAL: $FINAL" | tee -a "$REPORT_PATH"
[[ "$FINAL" == "PASS" ]]
