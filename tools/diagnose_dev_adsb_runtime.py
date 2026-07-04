#!/usr/bin/env python3
"""
Diagnose development ADS-B / 1090 runtime.

Run from MSYS2 UCRT64 repo root while the development web UI is running:
  python3 tools/diagnose_dev_adsb_runtime.py

This script produces PASS/FAIL output only. It does not use grep/diff and does
not require you to interpret raw code searches.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


BASE_URLS = [
    "http://127.0.0.1:8090",
    "http://localhost:8090",
]

API_PATHS = [
    "/api/status",
    "/api/aircraft",
]

ADS_B_PORTS = [
    ("SBS/BaseStation", 30003),
    ("Beast output", 30005),
    ("Raw input", 30001),
    ("Raw output", 30002),
    ("Beast input", 30104),
]

DATA_FILE_CANDIDATES = [
    "runtime/readsb/aircraft.json",
    "runtime/aircraft.json",
    "runtime/settings/aircraft.json",
    "run/readsb/aircraft.json",
    "readsb/aircraft.json",
    "aircraft.json",
]

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    "release",
    "releases",
    "test_output",
}

SCRIPT_NAME = "diagnose_dev_adsb_runtime.py"


def http_get_json(url: str, timeout: int = 3) -> tuple[bool, str, object | None]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                return True, f"HTTP {response.status}", json.loads(body)
            except json.JSONDecodeError:
                return True, f"HTTP {response.status}; non-JSON response: {body[:200]!r}", None
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return False, f"HTTP {exc.code}: {body[:300]}", None
    except URLError as exc:
        return False, f"URL error: {exc.reason}", None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", None


def http_get_text(url: str, timeout: int = 3) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return True, f"HTTP {response.status}: {body[:300]}"
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return False, f"HTTP {exc.code}: {body[:300]}"
    except URLError as exc:
        return False, f"URL error: {exc.reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def socket_open(port: int, timeout: float = 0.75) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def describe_aircraft_payload(payload: object) -> tuple[bool, str]:
    if isinstance(payload, dict):
        if isinstance(payload.get("aircraft"), list):
            count = len(payload["aircraft"])
            if count > 0:
                return True, f"aircraft list has {count} entries"
            return False, "aircraft list exists but has 0 entries"
        msg = payload.get("error") or payload.get("message") or payload.get("detail")
        if msg:
            return False, str(msg)
        return False, "JSON response does not contain an aircraft list"
    return False, "response was not JSON"


def describe_status(payload: object) -> str:
    if not isinstance(payload, dict):
        return "status response was not JSON"

    keys = [
        "adsb_running",
        "adsb_decoder_running",
        "readsb_running",
        "aircraft_count",
        "messages",
        "receiver_connected",
        "adsb_error",
        "decoder_error",
        "readsb_error",
    ]

    parts = []
    for key in keys:
        if key in payload:
            parts.append(f"{key}={payload[key]!r}")

    if not parts:
        # Keep output compact but useful.
        compact = {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                compact[key] = value
        return json.dumps(compact, indent=2)[:1000]

    return ", ".join(parts)


def file_summary(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "not found"

    age_s = time.time() - path.stat().st_mtime
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        return False, f"found, age={age_s:.1f}s, but could not parse JSON: {exc}"

    if isinstance(payload, dict) and isinstance(payload.get("aircraft"), list):
        return True, f"found, age={age_s:.1f}s, aircraft_count={len(payload['aircraft'])}"

    return True, f"found, age={age_s:.1f}s, JSON keys={list(payload)[:12] if isinstance(payload, dict) else type(payload).__name__}"


def path_excluded(path: Path, repo: Path) -> bool:
    try:
        rel = path.relative_to(repo)
    except ValueError:
        return True
    return any(part in EXCLUDE_DIRS for part in rel.parts)


def find_candidates(repo: Path) -> tuple[list[str], list[str]]:
    exe_candidates: list[str] = []
    script_candidates: list[str] = []

    exe_terms = ("readsb", "dump1090", "rtl_adsb", "rtl_adsb", "adsb")
    script_terms = ("readsb", "dump1090", "rtl_adsb", "adsb", "1090")

    for path in repo.rglob("*"):
        if path_excluded(path, repo):
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        lower = rel.lower()

        if path.suffix.lower() == ".exe" and any(term in lower for term in exe_terms):
            exe_candidates.append(rel)

        if path.suffix.lower() in {".py", ".sh", ".bat", ".cmd"} and any(term in lower for term in script_terms):
            if path.name == SCRIPT_NAME:
                continue
            if any(skip in lower for skip in ("patch", "validate", "diagnose", "package", "build_release")):
                continue
            script_candidates.append(rel)

    exe_candidates = sorted(set(exe_candidates))[:30]
    script_candidates = sorted(set(script_candidates))[:30]
    return exe_candidates, script_candidates


def main() -> int:
    repo = Path.cwd()
    print("RTP/RTL-Windows development ADS-B runtime diagnosis")
    print(f"Repo: {repo}")

    if not (repo / "web" / "app.js").exists():
        print("")
        print("FAIL: web/app.js was not found.")
        print("Run this from the repository root:")
        print("  cd ~/sdrdev/RTL-Windows-ADS-B-Tracker")
        return 2

    print("")
    print("Backend/API checks:")
    base_ok = None
    status_payload = None

    for base in BASE_URLS:
        ok, msg = http_get_text(base + "/", timeout=3)
        print(f"  {'PASS' if ok else 'FAIL'}: UI root {base}/ -> {msg}")
        if ok and base_ok is None:
            base_ok = base

    if base_ok is None:
        print("")
        print("FAIL: Development backend is not reachable on port 8090.")
        print("Start the development backend first, then rerun this diagnosis.")
        return 1

    api_failures: list[str] = []
    aircraft_live = False

    ok, msg, payload = http_get_json(base_ok + "/api/status", timeout=4)
    print(f"  {'PASS' if ok else 'FAIL'}: /api/status -> {msg}")
    if ok:
        status_payload = payload
        print(f"    status summary: {describe_status(payload)}")
    else:
        api_failures.append("/api/status failed: " + msg)

    ok, msg, payload = http_get_json(base_ok + "/api/aircraft", timeout=6)
    print(f"  {'PASS' if ok else 'FAIL'}: /api/aircraft -> {msg}")
    if ok:
        live_ok, detail = describe_aircraft_payload(payload)
        print(f"    aircraft summary: {detail}")
        aircraft_live = live_ok
        if not live_ok:
            api_failures.append("/api/aircraft returned no live aircraft: " + detail)
    else:
        api_failures.append("/api/aircraft failed: " + msg)

    print("")
    print("Local ADS-B port checks:")
    any_port = False
    for label, port in ADS_B_PORTS:
        open_ = socket_open(port)
        print(f"  {'PASS' if open_ else 'FAIL'}: port {port} ({label}) {'is open' if open_ else 'is not open'}")
        any_port = any_port or open_

    print("")
    print("Local aircraft.json checks:")
    fresh_data = False
    for rel in DATA_FILE_CANDIDATES:
        ok, detail = file_summary(repo / rel)
        print(f"  {'PASS' if ok else 'FAIL'}: {rel} -> {detail}")
        if ok and "age=" in detail:
            try:
                age_part = detail.split("age=", 1)[1].split("s", 1)[0]
                if float(age_part) < 20:
                    fresh_data = True
            except Exception:
                pass

    print("")
    print("Repo decoder/launcher candidates:")
    exe_candidates, script_candidates = find_candidates(repo)
    if exe_candidates:
        print("  PASS: decoder executable candidates found:")
        for item in exe_candidates:
            print(f"    - {item}")
    else:
        print("  FAIL: no obvious decoder executable candidates found in repo")

    if script_candidates:
        print("  PASS: ADS-B launcher/script candidates found:")
        for item in script_candidates:
            print(f"    - {item}")
    else:
        print("  FAIL: no obvious ADS-B launcher/script candidates found in repo")

    print("")
    if aircraft_live:
        print("PASS: ADS-B aircraft data is available through the development backend.")
        print("You can proceed with the browser double-click test.")
        return 0

    print("FAIL: Development backend is running, but live ADS-B aircraft data is not available.")
    print("")
    print("Most likely cause:")
    print("  The installed Windows service used to start/manage the 1090 decoder.")
    print("  After uninstalling the service and running only the dev backend, the decoder is not running.")
    print("")
    print("Upload/paste this full diagnosis output back to ChatGPT.")
    print("The candidate list above will let us create the correct full-stack dev launcher without guessing.")

    if api_failures:
        print("")
        print("API failure details:")
        for failure in api_failures:
            print(f"  - {failure}")

    if not any_port:
        print("")
        print("Decoder port finding:")
        print("  No common local ADS-B decoder ports are open.")

    if not fresh_data:
        print("")
        print("Data-file finding:")
        print("  No fresh aircraft.json file was found under the repo runtime paths checked.")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
