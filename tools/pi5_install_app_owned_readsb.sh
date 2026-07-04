#!/usr/bin/env bash
# Install the proven app-owned RTL-SDR-enabled readsb binary for PI-AIR-TRAFFIC-TRACKER.
# Run on the Raspberry Pi from the repository root.

set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="runtime/preflight"
REPORT_PATH="$REPORT_DIR/pi5_install_app_owned_readsb_${STAMP}.txt"
READSB_SOURCE_URL="${READSB_SOURCE_URL:-https://raw.githubusercontent.com/bakstaaj/RTL-Pi-ADS-B-TRACKER/main/vendor/readsb/linux-aarch64/readsb}"
TARGET_DIR="runtime/bin"
TARGET="$TARGET_DIR/readsb"
TMP_PATH="/tmp/pi-air-traffic-readsb-${STAMP}"
ADSB_SERIAL="${PI_AIR_TRAFFIC_ADSB_SERIAL:-00001090}"

pass() { echo "PASS: $*" | tee -a "$REPORT_PATH"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "WARN: $*" | tee -a "$REPORT_PATH"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "FAIL: $*" | tee -a "$REPORT_PATH"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

mkdir -p "$REPORT_DIR" runtime/logs "$TARGET_DIR"
: > "$REPORT_PATH"

if [[ ! -d .git || ! -f src/backend/pi_air_traffic_backend.py || ! -d web ]]; then
  echo "FAIL: run from PI-AIR-TRAFFIC-TRACKER repository root" | tee -a "$REPORT_PATH"
  exit 2
fi
pass "repo root validated"

if [[ "$(uname -s)" != "Linux" ]]; then
  fail "this installer must run on the Raspberry Pi/Linux host"
fi
if [[ "$(uname -m)" != "aarch64" ]]; then
  fail "expected aarch64 Raspberry Pi runtime; detected $(uname -m)"
else
  pass "aarch64 runtime detected"
fi

if command -v curl >/dev/null 2>&1; then
  pass "curl available"
else
  fail "curl missing"
fi
if command -v file >/dev/null 2>&1; then
  pass "file available"
else
  warn "file command missing; binary type check will be skipped"
fi
if command -v rtl_test >/dev/null 2>&1; then
  pass "rtl_test available"
else
  warn "rtl_test missing; SDR enumeration check skipped"
fi

if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-enabled readsb.service >/dev/null 2>&1 || systemctl is-active readsb.service >/dev/null 2>&1; then
    sudo systemctl disable --now readsb.service >/dev/null 2>&1 || true
    pass "disabled package readsb.service to avoid SDR ownership conflict"
  else
    pass "package readsb.service is not enabled/active"
  fi
else
  warn "systemctl not available; skipped package readsb.service disable check"
fi

if [[ "$FAIL_COUNT" -ne 0 ]]; then
  echo "" | tee -a "$REPORT_PATH"
  echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL" | tee -a "$REPORT_PATH"
  echo "FINAL: FAIL" | tee -a "$REPORT_PATH"
  exit 1
fi

echo "INFO: downloading app-owned readsb from:" | tee -a "$REPORT_PATH"
echo "  $READSB_SOURCE_URL" | tee -a "$REPORT_PATH"
if curl -fL --retry 3 --connect-timeout 15 "$READSB_SOURCE_URL" -o "$TMP_PATH" >>"$REPORT_PATH" 2>&1; then
  pass "downloaded app-owned readsb binary"
else
  fail "failed to download app-owned readsb binary"
fi

if [[ -s "$TMP_PATH" ]]; then
  chmod 0755 "$TMP_PATH"
  install -m 0755 "$TMP_PATH" "$TARGET"
  pass "installed app-owned readsb to $TARGET"
else
  fail "downloaded readsb binary is empty or missing"
fi

if [[ -x "$TARGET" ]]; then
  pass "app-owned readsb is executable"
else
  fail "app-owned readsb is not executable: $TARGET"
fi

if command -v file >/dev/null 2>&1 && [[ -x "$TARGET" ]]; then
  file "$TARGET" | tee -a "$REPORT_PATH" || true
fi

if [[ -x "$TARGET" ]]; then
  set +e
  "$TARGET" --usage >"runtime/logs/app_owned_readsb_usage_${STAMP}.txt" 2>&1
  usage_rc=$?
  set -e
  if grep -Eq 'rtlsdr|rtl-sdr|device-type' "runtime/logs/app_owned_readsb_usage_${STAMP}.txt"; then
    pass "app-owned readsb usage includes RTL-SDR/device markers"
  else
    warn "app-owned readsb usage did not include obvious RTL-SDR markers; runtime probe will decide"
  fi
  if [[ "$usage_rc" -ne 0 ]]; then
    warn "readsb --usage returned $usage_rc; continuing because some builds return nonzero for usage output"
  fi
fi

if [[ -x "$TARGET" ]]; then
  PROBE_ROOT="$REPORT_DIR/app_owned_readsb_probe_${STAMP}"
  mkdir -p "$PROBE_ROOT/json"
  set +e
  timeout 8s "$TARGET" \
    --device-type rtlsdr \
    --device "$ADSB_SERIAL" \
    --gain -10 \
    --ppm 0 \
    --write-json "$PROBE_ROOT/json" \
    --write-json-every 1 \
    --auto-exit 2 \
    --quiet \
    >"$PROBE_ROOT/readsb_stdout.log" 2>"$PROBE_ROOT/readsb_stderr.log"
  rc=$?
  set -e
  echo "INFO: app-owned readsb RTL probe exit code: $rc" | tee -a "$REPORT_PATH"
  cat "$PROBE_ROOT/readsb_stdout.log" "$PROBE_ROOT/readsb_stderr.log" >>"$REPORT_PATH" 2>/dev/null || true
  if grep -Rqi "SDR type 'rtlsdr' not recognized\|Unknown device type:rtlsdr" "$PROBE_ROOT"; then
    fail "app-owned readsb did not accept --device-type rtlsdr"
  elif [[ "$rc" -eq 0 || "$rc" -eq 124 ]]; then
    pass "app-owned readsb accepts --device-type rtlsdr"
  else
    warn "app-owned readsb accepted rtlsdr parsing but probe exited $rc; check $PROBE_ROOT logs if backend validation fails"
  fi
fi

if [[ "$FAIL_COUNT" -eq 0 ]]; then
  FINAL="PASS"
else
  FINAL="FAIL"
fi

echo "" | tee -a "$REPORT_PATH"
echo "Report path: $REPORT_PATH" | tee -a "$REPORT_PATH"
echo "Installed readsb: $TARGET" | tee -a "$REPORT_PATH"
echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL" | tee -a "$REPORT_PATH"
echo "FINAL: $FINAL" | tee -a "$REPORT_PATH"

[[ "$FINAL" == "PASS" ]]
