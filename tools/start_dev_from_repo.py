#!/usr/bin/env python3
"""
Start RTP/RTL-Windows ADS-B Tracker from the development repository.

Run from MSYS2 UCRT64 repo root:
  python3 tools/start_dev_from_repo.py

What it does:
  - Verifies web/app.js exists in the current repo.
  - Finds the most likely Python backend entry point.
  - Starts it from the repo, not from the installed Windows service location.
  - Polls http://localhost:8090 until it responds.
  - Prints PASS or FAIL.
  - Keeps the backend running until you press Ctrl+C.

This script is intentionally user-facing: it does not ask you to inspect grep/diff output.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


PORT = 8090
URL = f"http://127.0.0.1:{PORT}/"


PREFERRED = [
    "src/rtl_windows_api.py",
    "src/rtp_windows_api.py",
    "src/windows_api.py",
    "src/rtl_api.py",
    "src/api.py",
    "src/backend.py",
    "rtl_windows_api.py",
    "rtp_windows_api.py",
    "app.py",
    "server.py",
    "main.py",
]


def port_is_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def score_python_file(path: Path, text: str) -> int:
    rel = path.as_posix()
    score = 0

    preferred_map = {p: 1000 - i for i, p in enumerate(PREFERRED)}
    score += preferred_map.get(rel, 0)

    tokens = {
        "8090": 120,
        "Flask(": 100,
        "FastAPI(": 100,
        "waitress": 100,
        "app.run": 80,
        "uvicorn": 80,
        "send_from_directory": 60,
        "static_folder": 50,
        "/api/aircraft": 120,
        "/api/status": 100,
        "aircraft.json": 80,
        "readsb": 60,
        "RTL": 20,
        "ADS-B": 20,
        "adsb": 20,
    }

    for token, value in tokens.items():
        if token in text:
            score += value

    lowered = rel.lower()
    if "/test" in lowered or lowered.startswith("test") or "validate" in lowered:
        score -= 500
    if lowered.startswith("tools/"):
        score -= 200
    if lowered.startswith("build/") or lowered.startswith("dist/"):
        score -= 800

    return score


def find_entrypoint(repo: Path) -> Path | None:
    for rel in PREFERRED:
        p = repo / rel
        if p.exists():
            return p

    candidates: list[tuple[int, Path]] = []
    for path in repo.rglob("*.py"):
        if any(part in {".git", "__pycache__", ".venv", "venv", "build", "dist"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        score = score_python_file(path.relative_to(repo), text)
        if score >= 100:
            candidates.append((score, path))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1].as_posix()))
    return candidates[0][1]


def wait_for_http(proc: subprocess.Popen, timeout_s: int = 25) -> bool:
    deadline = time.time() + timeout_s
    last_error = ""

    while time.time() < deadline:
        if proc.poll() is not None:
            print("")
            print("FAIL: Development backend exited before the web UI responded.")
            print(f"Process exit code: {proc.returncode}")
            return False

        try:
            with urlopen(URL, timeout=2) as response:
                if 200 <= response.status < 500:
                    print("")
                    print(f"PASS: Development web UI is responding at {URL}")
                    return True
        except HTTPError as exc:
            if 200 <= exc.code < 500:
                print("")
                print(f"PASS: Development web UI is responding at {URL} with HTTP {exc.code}")
                return True
            last_error = f"HTTP {exc.code}"
        except URLError as exc:
            last_error = str(exc.reason)
        except Exception as exc:
            last_error = repr(exc)

        time.sleep(1)

    print("")
    print(f"FAIL: Development backend did not respond at {URL} within {timeout_s} seconds.")
    if last_error:
        print(f"Last connection error: {last_error}")
    return False


def main() -> int:
    repo = Path.cwd()
    print("RTP/RTL-Windows development launcher")
    print(f"Repo: {repo}")

    if not (repo / "web" / "app.js").exists():
        print("")
        print("FAIL: web/app.js was not found.")
        print("Run this from the repository root:")
        print("  cd ~/sdrdev/RTL-Windows-ADS-B-Tracker")
        return 2

    if not port_is_free(PORT):
        print("")
        print(f"FAIL: Port {PORT} is already in use.")
        print("The installed service or another dev server is probably still running.")
        print("Stop it, then run this script again.")
        return 3

    entrypoint = find_entrypoint(repo)
    if not entrypoint:
        print("")
        print("FAIL: Could not find a likely Python backend entry point.")
        print("Upload this full output back to ChatGPT.")
        return 4

    rel_entrypoint = entrypoint.relative_to(repo)
    print("")
    print(f"Starting development backend from: {rel_entrypoint}")
    print("Press Ctrl+C in this terminal to stop it.")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("HOST", "0.0.0.0")
    env.setdefault("PORT", str(PORT))
    env.setdefault("RTP_DEV", "1")
    env.setdefault("RTL_DEV", "1")

    proc = subprocess.Popen(
        [sys.executable, "-u", str(rel_entrypoint)],
        cwd=str(repo),
        env=env,
    )

    ok = wait_for_http(proc)
    if not ok:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        print("")
        print("FAIL: Development app did not start cleanly.")
        print("Upload this full output back to ChatGPT.")
        return 1

    print("")
    print("Browser test:")
    print("  1. Open http://localhost:8090")
    print("  2. Press Ctrl+F5")
    print("  3. Double-click directly on an airplane icon")
    print("")
    print("Expected:")
    print("  PASS if the aircraft dialog opens and the map does not zoom.")
    print("  FAIL if the map zooms or no dialog opens.")
    print("")
    print("Backend is still running. Press Ctrl+C here when done testing.")

    try:
        while True:
            rc = proc.poll()
            if rc is not None:
                print("")
                print(f"FAIL: Development backend exited unexpectedly with code {rc}.")
                return rc if rc else 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("")
        print("Stopping development backend...")
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        print("PASS: Development backend stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
