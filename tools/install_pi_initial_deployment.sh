#!/usr/bin/env bash
# First-deployment launcher for N0JCG Air Traffic Center.
# Run from MSYS2/UCRT64 on the workstation that has this repository checkout.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
ENV_FILE="${PI_AIR_TRAFFIC_ENV_FILE:-$APP_ROOT/.env}"
REMOTE_INSTALLER="tools/pi5_initial_deployment.sh"
BUNDLE="$(mktemp "${TMPDIR:-/tmp}/n0jcg-air-traffic-center.XXXXXX.tar.gz")"
REMOTE_BUNDLE="/tmp/n0jcg-air-traffic-center-first-deployment.tar.gz"
REMOTE_INSTALLER_PATH="/tmp/pi5_initial_deployment.sh"

cleanup() { rm -f "$BUNDLE"; }
trap cleanup EXIT

die() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
info() { printf 'INFO: %s\n' "$*"; }

if [[ ! -d "$APP_ROOT/.git" || ! -f "$APP_ROOT/web/index.html" ]]; then
  die "run this script from the N0JCG Air Traffic Center repository checkout"
fi
cd "$APP_ROOT"

for cmd in ssh scp sshpass tar git; do
  command -v "$cmd" >/dev/null 2>&1 || die "$cmd is required; install it in MSYS2 before continuing"
done

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  . "$ENV_FILE"
  set +a
fi

read -r -p "Pi IP address [${PI_HOST:-}]: " entered_host
PI_HOST="${entered_host:-${PI_HOST:-}}"
read -r -p "Pi SSH user [${PI_USER:-pi}]: " entered_user
PI_USER="${entered_user:-${PI_USER:-pi}}"
if [[ -z "${PI_PASS:-}" ]]; then
  read -r -s -p "Pi SSH password: " PI_PASS
  printf '\n'
else
  read -r -s -p "Pi SSH password [saved value; press Enter to reuse]: " entered_pass
  printf '\n'
  PI_PASS="${entered_pass:-$PI_PASS}"
fi

[[ "$PI_HOST" =~ ^[A-Za-z0-9._:-]+$ ]] || die "invalid Pi host/IP address"
[[ "$PI_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]*$ ]] || die "invalid Pi SSH user"
[[ -n "$PI_PASS" ]] || die "Pi SSH password cannot be empty"

umask 077
{
  printf 'PI_HOST=%q\n' "$PI_HOST"
  printf 'PI_USER=%q\n' "$PI_USER"
  printf 'PI_PASS=%q\n' "$PI_PASS"
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"
info "saved reusable connection values to $ENV_FILE (mode 600; do not commit it)"

SSH_OPTS=(-o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new)
ssh_pi() { sshpass -p "$PI_PASS" ssh "${SSH_OPTS[@]}" "$PI_USER@$PI_HOST" "$@"; }
scp_pi() { sshpass -p "$PI_PASS" scp -O "${SSH_OPTS[@]}" "$@"; }

info "testing SSH access to $PI_USER@$PI_HOST"
ssh_pi 'printf "Connected to %s as %s\n" "$(hostname)" "$(id -un)"' || die "SSH connection failed"

REVISION="$(git rev-parse --short HEAD)"
info "building deployment bundle from committed revision $REVISION"
git archive --format=tar.gz --prefix=n0jcg-air-traffic-center/ -o "$BUNDLE" HEAD

info "uploading application bundle and first-deployment workflow"
scp_pi "$BUNDLE" "$PI_USER@$PI_HOST:$REMOTE_BUNDLE" || die "application bundle upload failed"
scp_pi "$APP_ROOT/$REMOTE_INSTALLER" "$PI_USER@$PI_HOST:$REMOTE_INSTALLER_PATH" || die "remote installer upload failed"

cat <<EOF

The Pi will now:
  1. Install OS/runtime packages and the app-owned RTL decoders.
  2. Guide you through one-at-a-time serial programming for the three receivers.
  3. Validate all serial roles before enabling the web service.
  4. Start and validate the service on port 8090.

Keep this terminal open. The remote installer will pause for physical receiver actions.
EOF
read -r -p "Press Enter to begin the Pi installation, or Ctrl-C to cancel. " _

sshpass -p "$PI_PASS" ssh -tt "${SSH_OPTS[@]}" "$PI_USER@$PI_HOST" \
  "bash $REMOTE_INSTALLER_PATH '$REMOTE_BUNDLE' '$PI_USER' '$REVISION'"

cat <<EOF

Installation workflow finished.
Open: http://${PI_HOST}:8090

The saved connection values are in $ENV_FILE. Keep that file private; it contains the SSH password.
EOF
