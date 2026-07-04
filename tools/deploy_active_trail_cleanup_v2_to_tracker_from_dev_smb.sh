#!/usr/bin/env bash
# Deploy Active Trail Cleanup V2 from the dev workstation to the tracker host.
# MSYS2-only workflow: all validation/build work happens on the dev machine.
# The tracker receives finished web assets only and needs no Python/Node/Git/Docker/MSYS2 dev tools.
# No PowerShell scripts are used.

set -u

SERVICE_NAME="${SERVICE_NAME:-RTLADSBTracker}"
TRACKER_HOST="${TRACKER_HOST:-192.168.68.135}"
TRACKER_PORT="${TRACKER_PORT:-8090}"
REPO_DIR="${REPO_DIR:-$PWD}"
PRIMARY_MARKER="ACTIVE_TRAIL_CLEANUP_V2_START"
SECONDARY_MARKER="activeTrailCleanupFilterAircraftPayload"

# Optional. If unset, the script searches common install roots on the tracker C$ admin share.
# Example: TRACKER_INSTALL_ROOT='C:/RTL-ADS-B-Tracker-Windows-Service-v1.3.0'
TRACKER_INSTALL_ROOT="${TRACKER_INSTALL_ROOT:-}"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }
info() { echo "INFO: $*"; }

require_file() { [[ -f "$1" ]] || fail "Missing required file: $1"; }

win_to_unc() {
  local value="$1"
  value="${value//\\//}"
  if [[ "$value" =~ ^([A-Za-z]):/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1],,}"
    local rest="${BASH_REMATCH[2]}"
    printf '//%s/%s$/%s' "$TRACKER_HOST" "$drive" "$rest"
  elif [[ "$value" == //* ]]; then
    printf '%s' "$value"
  elif [[ "$value" == /* ]]; then
    printf '%s' "$value"
  else
    fail "Unsupported TRACKER_INSTALL_ROOT path format: $value"
  fi
}

find_tracker_web_dir() {
  local roots=()

  if [[ -n "$TRACKER_INSTALL_ROOT" ]]; then
    roots+=("$(win_to_unc "$TRACKER_INSTALL_ROOT")")
  else
    roots+=(
      "//${TRACKER_HOST}/c$/RTL-ADS-B-Tracker-Windows-Service-v1.3.1"
      "//${TRACKER_HOST}/c$/RTL-ADS-B-Tracker-Windows-Service-v1.3.0"
      "//${TRACKER_HOST}/c$/RTL-ADS-B-Tracker-Windows-Service-v1.2.1"
      "//${TRACKER_HOST}/c$/RTL-ADS-B-Tracker-Windows-Service-v1.2.0"
    )

    local found=()
    while IFS= read -r path; do
      found+=("$path")
    done < <(ls -d "//${TRACKER_HOST}/c$"/RTL-ADS-B-Tracker-Windows-Service-v* 2>/dev/null | sort -V || true)
    if ((${#found[@]})); then
      for ((i=${#found[@]}-1; i>=0; i--)); do
        roots+=("${found[$i]}")
      done
    fi
  fi

  local root candidate
  for root in "${roots[@]}"; do
    [[ -d "$root" ]] || continue
    for candidate in "$root/app/web" "$root/web" "$root/app/frontend/web"; do
      if [[ -f "$candidate/index.html" && -f "$candidate/app.js" ]]; then
        printf '%s' "$candidate"
        return 0
      fi
    done
  done

  return 1
}

service_state() {
  sc.exe "\\\\${TRACKER_HOST}" query "$SERVICE_NAME" 2>/dev/null | tr -d '\r' | awk '/STATE/ {print $4; exit}'
}

wait_service_state() {
  local wanted="$1"
  local label="$2"
  local i state
  for i in {1..35}; do
    state="$(service_state || true)"
    if [[ "$state" == "$wanted" ]]; then
      pass "$label"
      return 0
    fi
    sleep 1
  done
  state="$(service_state || true)"
  fail "Service did not reach ${wanted}; current state=${state:-unknown}"
}

stop_service() {
  local state
  state="$(service_state || true)"
  if [[ -z "$state" ]]; then
    fail "Could not query service ${SERVICE_NAME} on ${TRACKER_HOST}. Check host, firewall, admin rights, and service name."
  fi
  info "Current remote service state: $state"
  if [[ "$state" == "STOPPED" ]]; then
    pass "Remote service already stopped"
    return 0
  fi
  info "Stopping ${SERVICE_NAME} on ${TRACKER_HOST}"
  sc.exe "\\\\${TRACKER_HOST}" stop "$SERVICE_NAME" >/dev/null 2>&1 || true
  wait_service_state "STOPPED" "Remote service stopped"
}

start_service() {
  info "Starting ${SERVICE_NAME} on ${TRACKER_HOST}"
  sc.exe "\\\\${TRACKER_HOST}" start "$SERVICE_NAME" >/dev/null 2>&1 || true
  wait_service_state "RUNNING" "Remote service running"
}

verify_http() {
  local base="http://${TRACKER_HOST}:${TRACKER_PORT}"
  local tmp

  tmp="$(mktemp)"
  if curl -fsS --max-time 15 "${base}/api/status" >"$tmp"; then
    pass "Tracker API reachable at ${base}/api/status"
  else
    cat "$tmp" 2>/dev/null || true
    rm -f "$tmp"
    fail "Tracker API not reachable at ${base}/api/status"
  fi
  rm -f "$tmp"

  tmp="$(mktemp)"
  if curl -fsS --max-time 15 "${base}/app.js?activeTrailCleanupV2=$(date +%s)" >"$tmp" && \
     grep -Fq "$PRIMARY_MARKER" "$tmp" && grep -Fq "$SECONDARY_MARKER" "$tmp"; then
    pass "Served app.js contains Active Trail Cleanup V2 markers"
  else
    rm -f "$tmp"
    fail "Served app.js does not contain Active Trail Cleanup V2 markers; verify the service web root and press Ctrl+F5 in the browser"
  fi
  rm -f "$tmp"
}

main() {
  cd "$REPO_DIR" || fail "Cannot cd to repo: $REPO_DIR"
  require_file "web/app.js"
  require_file "web/index.html"

  if [[ -x tools/validate_active_trail_cleanup_v2.sh ]]; then
    ./tools/validate_active_trail_cleanup_v2.sh || fail "Local V2 validation failed"
  else
    info "tools/validate_active_trail_cleanup_v2.sh not found/executable; using built-in marker validation"
  fi

  grep -Fq "$PRIMARY_MARKER" web/app.js || fail "Local web/app.js missing ${PRIMARY_MARKER}. Run apply_active_trail_cleanup_v2.py first."
  grep -Fq "$SECONDARY_MARKER" web/app.js || fail "Local web/app.js missing ${SECONDARY_MARKER}. Run apply_active_trail_cleanup_v2.py first."
  pass "Local Active Trail Cleanup V2 markers present"

  if command -v node >/dev/null 2>&1; then
    node --check web/app.js >/dev/null || fail "Local JavaScript syntax check failed"
    pass "Local JavaScript syntax check passed"
  else
    info "node not found on dev path; skipping local JS syntax check"
  fi

  local web_dir backup_root timestamp backup_dir
  web_dir="$(find_tracker_web_dir)" || fail "Could not find tracker web directory over //${TRACKER_HOST}/c$. Set TRACKER_INSTALL_ROOT='C:/RTL-ADS-B-Tracker-Windows-Service-vX.Y.Z'."
  info "Remote web directory: $web_dir"

  timestamp="$(date +%Y%m%d_%H%M%S)"
  backup_root="//${TRACKER_HOST}/c$/ProgramData/RTL ADS-B Tracker/backups"
  backup_dir="${backup_root}/active_trail_cleanup_v2_${timestamp}"
  mkdir -p "$backup_dir" || fail "Could not create backup directory: $backup_dir"

  cp -p "$web_dir/app.js" "$backup_dir/app.js.before_active_trail_cleanup_v2" || fail "Could not backup remote app.js"
  pass "Remote app.js backed up to $backup_dir"

  stop_service

  cp -p web/app.js "$web_dir/app.js" || {
    echo "FAIL: copy failed; attempting service restart before exiting" >&2
    start_service || true
    exit 1
  }
  pass "Patched app.js copied to tracker"

  if [[ -f web/app.css && -f "$web_dir/app.css" ]]; then
    cp -p "$web_dir/app.css" "$backup_dir/app.css.before_active_trail_cleanup_v2" || true
    cp -p web/app.css "$web_dir/app.css" || fail "Could not copy app.css"
    pass "app.css synchronized to tracker"
  fi

  grep -Fq "$PRIMARY_MARKER" "$web_dir/app.js" || fail "Remote app.js copy completed but ${PRIMARY_MARKER} is missing"
  grep -Fq "$SECONDARY_MARKER" "$web_dir/app.js" || fail "Remote app.js copy completed but ${SECONDARY_MARKER} is missing"
  pass "Remote app.js markers verified on admin share"

  start_service
  sleep 5
  verify_http

  echo
  pass "Active Trail Cleanup V2 deployed from dev to tracker host ${TRACKER_HOST}"
  echo "INFO: Open http://${TRACKER_HOST}:${TRACKER_PORT} and press Ctrl+F5."
  echo "INFO: Backup: $backup_dir"
}

main "$@"
