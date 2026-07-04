#!/usr/bin/env bash
# Build and install app-owned FlightAware dump978-fa binaries for the Pi UAT 978 MHz receiver.
# This does not start a persistent UAT service.
set -u

PROJECT_ROOT="$(pwd)"
REPORT_DIR="runtime/preflight"
WORK_DIR="${REPORT_DIR}/dump978_install_$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${REPORT_DIR}/pi5_install_app_owned_dump978_$(date +%Y%m%d_%H%M%S).txt"
DUMP978_REPO_URL="${PI_AIR_TRAFFIC_DUMP978_REPO_URL:-https://github.com/flightaware/dump978.git}"
DUMP978_REF="${PI_AIR_TRAFFIC_DUMP978_REF:-master}"
SRC_DIR="${PI_AIR_TRAFFIC_DUMP978_SRC_DIR:-${PROJECT_ROOT}/runtime/build/dump978-fa-src}"
BIN_DIR="${PROJECT_ROOT}/runtime/bin"
SKIP_APT="${PI_AIR_TRAFFIC_SKIP_APT:-0}"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

mkdir -p "$REPORT_DIR" "$WORK_DIR" "$BIN_DIR" "$(dirname "$SRC_DIR")"

log() { printf '%s\n' "$*" | tee -a "$REPORT_PATH"; }
section() { log ""; log "===== $* ====="; }
pass() { PASS_COUNT=$((PASS_COUNT+1)); log "PASS: $*"; }
warn() { WARN_COUNT=$((WARN_COUNT+1)); log "WARN: $*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); log "FAIL: $*"; }

section "Environment"
log "PROJECT_ROOT=$PROJECT_ROOT"
log "DUMP978_REPO_URL=$DUMP978_REPO_URL"
log "DUMP978_REF=$DUMP978_REF"
log "SRC_DIR=$SRC_DIR"
log "BIN_DIR=$BIN_DIR"
if [[ -f README.md && -d src/backend && -d tools ]]; then
  pass "repository root appears valid"
else
  fail "run from the PI-AIR-TRAFFIC-TRACKER repository root"
fi
for cmd in git make g++ python3; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$cmd available at $(command -v "$cmd")"
  else
    fail "$cmd is required"
  fi
done
if command -v sudo >/dev/null 2>&1; then
  pass "sudo available"
else
  warn "sudo is not available; apt dependency installation may fail if needed"
fi

section "Install build dependencies"
if [[ "$SKIP_APT" == "1" ]]; then
  warn "skipping apt dependency installation because PI_AIR_TRAFFIC_SKIP_APT=1"
else
  if command -v apt-get >/dev/null 2>&1; then
    log "Installing dump978-fa build dependencies with apt-get"
    if sudo apt-get update && sudo apt-get install -y \
      build-essential \
      git \
      make \
      g++ \
      pkg-config \
      libboost-program-options-dev \
      libboost-regex-dev \
      libboost-filesystem-dev \
      libsoapysdr-dev \
      soapysdr-tools \
      soapysdr-module-rtlsdr; then
      pass "apt build/runtime dependencies installed"
    else
      fail "apt dependency installation failed"
    fi
  else
    warn "apt-get is not available; assuming dependencies are already installed"
  fi
fi

section "Fetch dump978-fa source"
if [[ -d "$SRC_DIR/.git" ]]; then
  log "Updating existing source checkout"
  if git -C "$SRC_DIR" fetch --depth 1 origin "$DUMP978_REF" && git -C "$SRC_DIR" checkout --detach FETCH_HEAD; then
    pass "updated source checkout to $DUMP978_REF"
  else
    fail "failed to update existing dump978 source checkout"
  fi
else
  rm -rf "$SRC_DIR"
  if git clone --depth 1 --branch "$DUMP978_REF" "$DUMP978_REPO_URL" "$SRC_DIR"; then
    pass "cloned dump978 source"
  else
    fail "failed to clone dump978 source from $DUMP978_REPO_URL ref $DUMP978_REF"
  fi
fi
if [[ -d "$SRC_DIR/.git" ]]; then
  DUMP978_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || true)"
  log "DUMP978_COMMIT=${DUMP978_COMMIT:-unknown}"
else
  fail "source checkout is not available after fetch/clone"
fi

section "Build app-owned dump978 binaries"
if [[ -f "$SRC_DIR/Makefile" ]]; then
  if make -C "$SRC_DIR" clean && make -C "$SRC_DIR" -j"$(nproc 2>/dev/null || printf '2')" dump978-fa skyaware978; then
    pass "built dump978-fa and skyaware978"
  else
    fail "dump978-fa build failed"
  fi
else
  fail "Makefile not found in source checkout"
fi

section "Install app-owned binaries"
for bin in dump978-fa skyaware978; do
  if [[ -x "$SRC_DIR/$bin" ]]; then
    cp "$SRC_DIR/$bin" "$BIN_DIR/$bin"
    chmod 755 "$BIN_DIR/$bin"
    pass "installed runtime/bin/$bin"
  else
    fail "built binary missing or not executable: $SRC_DIR/$bin"
  fi
done

section "Binary smoke checks"
if [[ -x "$BIN_DIR/dump978-fa" ]]; then
  "$BIN_DIR/dump978-fa" --help >"$WORK_DIR/dump978_help.out" 2>"$WORK_DIR/dump978_help.err"
  help_rc=$?
  cat "$WORK_DIR/dump978_help.out" "$WORK_DIR/dump978_help.err" | sed -n '1,40p' | tee -a "$REPORT_PATH" >/dev/null
  if grep -q -- '--sdr' "$WORK_DIR/dump978_help.out" "$WORK_DIR/dump978_help.err" 2>/dev/null && grep -q -- '--json-port\|--json-stdout' "$WORK_DIR/dump978_help.out" "$WORK_DIR/dump978_help.err" 2>/dev/null; then
    pass "dump978-fa help exposes SDR and JSON options"
  else
    fail "dump978-fa help did not expose expected SDR/JSON options; rc=$help_rc"
  fi
else
  fail "runtime/bin/dump978-fa is not executable"
fi
if [[ -x "$BIN_DIR/skyaware978" ]]; then
  pass "runtime/bin/skyaware978 is executable"
else
  fail "runtime/bin/skyaware978 is not executable"
fi

section "Summary"
log "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
log "Report path: $REPORT_PATH"
log "Work dir: $WORK_DIR"
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  log "FINAL: PASS"
  exit 0
else
  log "FINAL: FAIL"
  exit 1
fi
