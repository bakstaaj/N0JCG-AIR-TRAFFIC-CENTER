#!/usr/bin/env bash
# Validate live Pi Air Traffic Tracker service functionality without changing runtime settings.

set -Eeuo pipefail

REPORT_DIR="${PI_AIR_TRAFFIC_REPORT_DIR:-runtime/preflight}"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${REPORT_DIR}/pi5_live_functional_validation_${STAMP}.txt"
HOST="${PI_AIR_TRAFFIC_HOST:-127.0.0.1}"
PORT="${PI_AIR_TRAFFIC_PORT:-8090}"
OBSERVE_SECONDS="${PI_AIR_TRAFFIC_OBSERVE_SECONDS:-30}"
NOAA_SECONDS="${PI_AIR_TRAFFIC_NOAA_SECONDS:-2}"

mkdir -p "$REPORT_DIR"
: > "$REPORT_PATH"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is required" | tee -a "$REPORT_PATH"
  echo "FINAL: FAIL" | tee -a "$REPORT_PATH"
  exit 1
fi

export REPORT_PATH HOST PORT OBSERVE_SECONDS NOAA_SECONDS
python3 - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

report_path = Path(os.environ["REPORT_PATH"])
host = os.environ.get("HOST", "127.0.0.1")
port = int(os.environ.get("PORT", "8090"))
observe_seconds = max(0, int(float(os.environ.get("OBSERVE_SECONDS", "30"))))
noaa_seconds = max(1, min(10, int(float(os.environ.get("NOAA_SECONDS", "2")))))
base = f"http://{host}:{port}"
pass_count = 0
warn_count = 0
fail_count = 0


def emit(level: str, message: str) -> None:
    global pass_count, warn_count, fail_count
    line = f"{level}: {message}"
    print(line)
    with report_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    if level == "PASS":
        pass_count += 1
    elif level == "WARN":
        warn_count += 1
    elif level == "FAIL":
        fail_count += 1


def section(title: str) -> None:
    line = f"\n===== {title} ====="
    print(line)
    with report_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def fetch(path: str, timeout: float = 5.0) -> tuple[int, str, bytes]:
    url = base + path
    req = urllib.request.Request(url, headers={"User-Agent": "pi-live-functional-validator/1"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        status = int(getattr(response, "status", response.getcode()))
        content_type = response.headers.get("Content-Type", "")
        body = response.read()
    return status, content_type, body


def fetch_json(path: str, timeout: float = 5.0) -> dict:
    status, content_type, body = fetch(path, timeout=timeout)
    if status < 200 or status >= 300:
        raise RuntimeError(f"{path} returned HTTP {status}")
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"{path} did not return valid JSON: {exc}; content_type={content_type}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} JSON was not an object")
    return payload


def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


section("Environment")
emit("PASS", f"target base URL: {base}")
if Path(".git").is_dir() and Path("web").is_dir() and Path("src/backend/pi_air_traffic_backend.py").is_file():
    emit("PASS", "repository root appears valid")
else:
    emit("WARN", "repository root markers were not all found; continuing because remote host validation is supported")

if host in ("127.0.0.1", "localhost"):
    try:
        ips = subprocess.check_output(["hostname", "-I"], text=True, timeout=2).strip().split()
        for ip in sorted({item for item in ips if item and not item.startswith("127.")}):
            emit("PASS", f"local LAN candidate URL: http://{ip}:{port}")
    except Exception as exc:
        emit("WARN", f"could not determine local LAN URLs: {exc}")

section("Static UI assets")
try:
    status, content_type, body = fetch("/", timeout=5)
    if status == 200 and (b"<html" in body.lower() or b"<!doctype" in body.lower()):
        emit("PASS", f"UI root loaded: HTTP {status}, {len(body)} bytes")
    else:
        emit("FAIL", f"UI root response unexpected: HTTP {status}, content_type={content_type}, bytes={len(body)}")
except Exception as exc:
    emit("FAIL", f"UI root did not load: {exc}")

for path, minimum, label in (("/app.js", 1000, "JavaScript asset"), ("/app.css", 500, "CSS asset")):
    try:
        status, content_type, body = fetch(path, timeout=5)
        if status == 200 and len(body) >= minimum:
            emit("PASS", f"{label} loaded from {path}: {len(body)} bytes")
        else:
            emit("FAIL", f"{label} from {path} unexpected: HTTP {status}, content_type={content_type}, bytes={len(body)}")
    except Exception as exc:
        emit("FAIL", f"{label} from {path} did not load: {exc}")

section("/api/status contract")
status_payload: dict = {}
try:
    status_payload = fetch_json("/api/status", timeout=6)
    emit("PASS", "/api/status returned JSON")
except Exception as exc:
    emit("FAIL", f"/api/status failed: {exc}")

if status_payload:
    roles = status_payload.get("receiver_roles") or {}
    expected = {"adsb": "00001090", "audio": "00000162", "airband": "00000118", "uat": "00000978"}
    for key, serial in expected.items():
        role = roles.get(key) or {}
        if str(role.get("serial")) == serial:
            emit("PASS", f"receiver role {key} reports serial {serial}")
        else:
            emit("FAIL", f"receiver role {key} serial mismatch: expected {serial}, got {role}")

    decoder = status_payload.get("decoder") or {}
    if decoder.get("running"):
        emit("PASS", "ADS-B decoder reports running")
    else:
        emit("FAIL", f"ADS-B decoder not running: {decoder}")

    if status_payload.get("readsb_json_available") or decoder.get("json_ready"):
        emit("PASS", "readsb JSON is available through status")
    else:
        emit("WARN", f"readsb JSON not yet marked available: decoder={decoder}")

    command = ((status_payload.get("pi_backend") or {}).get("readsb_command")) or decoder.get("profile", {}).get("decoder")
    if command:
        emit("PASS", f"readsb command reported: {command}")
    else:
        emit("WARN", "readsb command path was not reported")

section("ADS-B aircraft JSON and message observation")
messages_before = safe_int(status_payload.get("messages") or (status_payload.get("decoder") or {}).get("messages"), 0)
try:
    aircraft_payload = fetch_json("/api/aircraft.json", timeout=8)
    aircraft = aircraft_payload.get("aircraft")
    if isinstance(aircraft, list):
        emit("PASS", f"/api/aircraft.json returned aircraft list with {len(aircraft)} item(s)")
    else:
        emit("FAIL", "/api/aircraft.json did not include an aircraft list")
    if "messages" in aircraft_payload:
        emit("PASS", f"/api/aircraft.json messages={safe_int(aircraft_payload.get('messages'), 0)}")
    else:
        emit("WARN", "/api/aircraft.json did not include a messages field")
except Exception as exc:
    emit("FAIL", f"/api/aircraft.json failed: {exc}")

if observe_seconds > 0 and status_payload:
    emit("PASS", f"observing ADS-B message count for {observe_seconds} seconds")
    time.sleep(observe_seconds)
    try:
        after_payload = fetch_json("/api/status", timeout=6)
        messages_after = safe_int(after_payload.get("messages") or (after_payload.get("decoder") or {}).get("messages"), 0)
        if messages_after > messages_before:
            emit("PASS", f"ADS-B messages increased: {messages_before} -> {messages_after}")
        elif messages_after >= messages_before and ((after_payload.get("decoder") or {}).get("running") or after_payload.get("readsb_json_available")):
            emit("WARN", f"ADS-B messages did not increase during observation: {messages_before} -> {messages_after}; RF conditions may be quiet")
        else:
            emit("FAIL", f"ADS-B messages did not increase and decoder status is not healthy: {messages_before} -> {messages_after}")
    except Exception as exc:
        emit("FAIL", f"could not re-read /api/status after observation: {exc}")

section("NOAA capture endpoint")
try:
    status, content_type, body = fetch(f"/api/noaa/capture.wav?seconds={noaa_seconds}", timeout=noaa_seconds + 20)
    if status == 200 and len(body) > 1024 and ("audio" in content_type.lower() or body.startswith(b"RIFF")):
        emit("PASS", f"NOAA capture returned WAV/audio payload: {len(body)} bytes, content_type={content_type}")
    else:
        emit("FAIL", f"NOAA capture unexpected: HTTP {status}, content_type={content_type}, bytes={len(body)}")
except urllib.error.HTTPError as exc:
    try:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
    except Exception:
        detail = "<unavailable>"
    emit("FAIL", f"NOAA capture HTTP {exc.code}: {detail}")
except Exception as exc:
    emit("FAIL", f"NOAA capture failed: {exc}")

section("Airband passive API endpoints")
try:
    airband_status = fetch_json("/api/airband/scan/status", timeout=6)
    if "airband_scan_state" in airband_status:
        emit("PASS", f"airband scan status endpoint returned state={airband_status.get('airband_scan_state')}")
    else:
        emit("FAIL", "airband scan status endpoint did not include airband_scan_state")
except Exception as exc:
    emit("FAIL", f"airband scan status endpoint failed: {exc}")

try:
    status, content_type, body = fetch("/api/airband/channels", timeout=8)
    if status == 200:
        try:
            parsed = json.loads(body.decode("utf-8"))
            if isinstance(parsed, (list, dict)):
                size = len(parsed) if hasattr(parsed, "__len__") else 0
                emit("PASS", f"airband channel endpoint returned JSON {type(parsed).__name__} with size {size}")
            else:
                emit("WARN", f"airband channel endpoint returned JSON {type(parsed).__name__}")
        except Exception as exc:
            emit("FAIL", f"airband channel endpoint returned non-JSON content: {exc}")
    else:
        emit("FAIL", f"airband channel endpoint returned HTTP {status}, content_type={content_type}")
except Exception as exc:
    emit("FAIL", f"airband channel endpoint failed: {exc}")

section("Summary")
summary = f"Summary: {pass_count} PASS, {warn_count} WARN, {fail_count} FAIL"
final = "PASS" if fail_count == 0 else "FAIL"
print(summary)
print(f"Report path: {report_path}")
print(f"FINAL: {final}")
with report_path.open("a", encoding="utf-8") as handle:
    handle.write(summary + "\n")
    handle.write(f"Report path: {report_path}\n")
    handle.write(f"FINAL: {final}\n")
sys.exit(0 if final == "PASS" else 1)
PY
