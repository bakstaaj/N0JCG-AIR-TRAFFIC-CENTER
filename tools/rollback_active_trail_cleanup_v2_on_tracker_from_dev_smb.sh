#!/usr/bin/env bash
# Roll back Active Trail Cleanup V2 on the tracker from the dev workstation.
# Pass the exact backup app.js path printed by the deploy script.
# No PowerShell and no tracker-side dev tools required.

set -u

SERVICE_NAME="${SERVICE_NAME:-RTLADSBTracker}"
TRACKER_HOST="${TRACKER_HOST:-192.168.68.135}"
TRACKER_INSTALL_ROOT="${TRACKER_INSTALL_ROOT:-}"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }
info() { echo "INFO: $*"; }

BACKUP_APP_JS="${1:-}"
[[ -n "$BACKUP_APP_JS" ]] || fail "Usage: $0 //<host>/c$/ProgramData/.../app.js.before_active_trail_cleanup_v2"
[[ -f "$BACKUP_APP_JS" ]] || fail "Backup app.js not found: $BACKUP_APP_JS"

win_to_unc() {
  local value="$1"
  value="${value//\\//}"
  if [[ "$value" =~ ^([A-Za-z]):/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1],,}"
    local rest="${BASH_REMATCH[2]}"
    printf '//%s/%s$/%s' "$TRACKER_HOST" "$drive" "$rest"
  elif [[ "$value" == //* ]]; then
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
    local found=()
    while IFS= read -r path; do found+=("$path"); done < <(ls -d "//${TRACKER_HOST}/c$"/RTL-ADS-B-Tracker-Windows-Service-v* 2>/dev/null | sort -V || true)
    if ((${#found[@]})); then
      for ((i=${#found[@]}-1; i>=0; i--)); do roots+=("${found[$i]}"); done
    fi
    roots+=("//${TRACKER_HOST}/c$/RTL-ADS-B-Tracker-Windows-Service-v1.3.1" "//${TRACKER_HOST}/c$/RTL-ADS-B-Tracker-Windows-Service-v1.3.0" "//${TRACKER_HOST}/c$/RTL-ADS-B-Tracker-Windows-Service-v1.2.1")
  fi

  local root candidate
  for root in "${roots[@]}"; do
    [[ -d "$root" ]] || continue
    for candidate in "$root/app/web" "$root/web" "$root/app/frontend/web"; do
      if [[ -f "$candidate/index.html" && -f "$candidate/app.js" ]]; then
        printf '%s' "$candidate"; return 0
      fi
    done
  done
  return 1
}

service_state() { sc.exe "\\\\${TRACKER_HOST}" query "$SERVICE_NAME" 2>/dev/null | tr -d '\r' | awk '/STATE/ {print $4; exit}'; }
wait_service_state() {
  local wanted="$1" label="$2" i state
  for i in {1..35}; do
    state="$(service_state || true)"
    [[ "$state" == "$wanted" ]] && { pass "$label"; return 0; }
    sleep 1
  done
  fail "Service did not reach $wanted; current state=$(service_state || true)"
}
stop_service() { sc.exe "\\\\${TRACKER_HOST}" stop "$SERVICE_NAME" >/dev/null 2>&1 || true; wait_service_state STOPPED "Remote service stopped"; }
start_service() { sc.exe "\\\\${TRACKER_HOST}" start "$SERVICE_NAME" >/dev/null 2>&1 || true; wait_service_state RUNNING "Remote service running"; }

web_dir="$(find_tracker_web_dir)" || fail "Could not find tracker web directory"
info "Remote web directory: $web_dir"

stop_service
cp -p "$BACKUP_APP_JS" "$web_dir/app.js" || { start_service || true; fail "Rollback copy failed"; }
pass "Restored app.js from backup"
start_service
pass "Rollback completed"
