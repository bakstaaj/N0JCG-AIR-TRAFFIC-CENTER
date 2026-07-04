#!/usr/bin/env python3
"""
Safe development launcher for RTP/RTL-Windows ADS-B Tracker.

Run from MSYS2 UCRT64 repo root:
  python3 tools/start_dev_from_repo_v2.py

This version avoids the previous recursion bug:
  - It refuses to start anything under tools/
  - It refuses to start itself
  - It excludes tests/build/dist/venv
  - It starts the most likely backend only if it looks like a real web/API server
  - It returns clear PASS/FAIL output
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


PORT = 8090
URLS = [
    f"http://127.0.0.1:{PORT}/",
    f"http://localhost:{PORT}/",
]

PREFERRED = [
    "src/rtl_windows_api.py",
    "src/rtl_windows_backend.py",
    "src/rtl_windows_server.py",
    "src/rtp_windows_api.py",
    "src/rtp_windows_backend.py",
    "src/rtp_windows_server.py",
    "src/windows_api.py",
    "src/backend.py",
    "src/server.py",
    "src/app.py",
    "rtl_windows_api.py",
    "rtl_windows_backend.py",
    "rtp_windows_api.py",
    "rtp_windows_backend.py",
    "backend.py",
    "server.py",
    "app.py",
    "main.py",
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
    "tools",
    "tests",
    "test_output",
}


def path_excluded(path: Path, repo: Path) -> bool:
    try:
        rel = path.relative_to(repo)
    except ValueError:
        return True
    return any(part in EXCLUDE_DIRS for part in rel.parts)


def port_is_free(port: int) -> bool:
    for host in ("127.0.0.1", "0.0.0.0"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
        except OSError:
            return False
        finally:
            sock.close()
    return True


def file_score(rel: Path, text: str) -> int:
    rel_s = rel.as_posix()
    lower = rel_s.lower()
    score = 0

    if rel_s in PREFERRED:
        score += 2000 - PREFERRED.index(rel_s)

    positive = {
        "Flask(": 250,
        "FastAPI(": 250,
        "waitress.serve": 220,
        "waitress": 160,
        "app.run": 180,
        "uvicorn.run": 180,
        "send_from_directory": 120,
        "static_folder": 90,
        "8090": 120,
        "/api/status": 220,
        "/api/aircraft": 220,
        "/api/noaa": 160,
        "/api/airband": 160,
        "aircraft.json": 120,
        "readsb": 100,
        "RTL": 40,
        "ADS-B": 40,
        "adsb": 40,
        "web": 25,
    }

    for token, value in positive.items():
        if token in text:
            score += value

    negative_name_terms = [
        "test",
        "validate",
        "patch",
        "import_",
        "package",
        "build",
        "install",
        "uninstall",
        "restart",
        "diagnostic",
        "diag",
        "probe",
    ]
    for term in negative_name_terms:
        if term in lower:
            score -= 250

    # Real servers usually have an executable main block or explicit server call.
    if 'if __name__ == "__main__"' in text or "if __name__ == '__main__'" in text:
        score += 120

    return score


def find_backend(repo: Path) -> tuple[Path | None, list[tuple[int, Path]]]:
    candidates: list[tuple[int, Path]] = []

    for rel_s in PREFERRED:
        path = repo / rel_s
        if path.exists() and not path_excluded(path, repo):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            candidates.append((file_score(path.relative_to(repo), text) + 5000, path))

    for path in repo.rglob("*.py"):
        if path_excluded(path, repo):
            continue
        try:
            rel = path.relative_to(repo)
        except ValueError:
            continue

        # Never start this launcher, even if copied somewhere unexpected.
        if path.name.startswith("start_dev_from_repo"):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        score = file_score(rel, text)
        if score >= 250:
            candidates.append((score, path))

    # Deduplicate, keeping best score.
    best_by_path: dict[Path, int] = {}
    for score, path in candidates:
        best_by_path[path] = max(best_by_path.get(path, -999999), score)

    ranked = sorted(((score, path) for path, score in best_by_path.items()), key=lambda item: (-item[0], item[1].as_posix()))

    if not ranked:
        return None, []

    top_score, top_path = ranked[0]

    # Require enough confidence to actually run it.
    if top_score < 350:
        return None, ranked[:10]

    return top_path, ranked[:10]


def wait_for_http(proc: subprocess.Popen, timeout_s: int = 35) -> bool:
    deadline = time.time() + timeout_s
    last_error = ""

    while time.time() < deadline:
        rc = proc.poll()
        if rc is not None:
            print("")
            print("FAIL: Development backend exited before the web UI responded.")
            print(f"Process exit code: {rc}")
            return False

        for url in URLS:
            try:
                with urlopen(url, timeout=2) as response:
                    if 200 <= response.status < 500:
                        print("")
                        print(f"PASS: Development web UI is responding at {url}")
                        return True
            except HTTPError as exc:
                if 200 <= exc.code < 500:
                    print("")
                    print(f"PASS: Development web UI is responding at {url} with HTTP {exc.code}")
                    return True
                last_error = f"{url}: HTTP {exc.code}"
            except URLError as exc:
                last_error = f"{url}: {exc.reason}"
            except TimeoutError:
                last_error = f"{url}: timed out"
            except Exception as exc:
                last_error = f"{url}: {exc!r}"

        time.sleep(1)

    print("")
    print(f"FAIL: Development backend did not respond on port {PORT} within {timeout_s} seconds.")
    if last_error:
        print(f"Last connection error: {last_error}")
    return False


def main() -> int:
    repo = Path.cwd()
    print("RTP/RTL-Windows safe development launcher")
    print(f"Repo: {repo}")

    if not (repo / "web" / "app.js").exists():
        print("")
        print("FAIL: web/app.js was not found.")
        print("Run from the repository root:")
        print("  cd ~/sdrdev/RTL-Windows-ADS-B-Tracker")
        return 2

    if not port_is_free(PORT):
        print("")
        print(f"FAIL: Port {PORT} is already in use.")
        print("Something is already serving the web UI, likely the installed service or a previous dev process.")
        print("Stop that process, then run this launcher again.")
        return 3

    backend, ranked = find_backend(repo)
    print("")
    if not backend:
        print("FAIL: Could not confidently identify the development backend entry point.")
        print("")
        print("Upload/paste this output back to ChatGPT.")
        if ranked:
            print("")
            print("Possible candidates found, but confidence was too low:")
            for score, path in ranked:
                print(f"  score={score:4d}  {path.relative_to(repo)}")
        else:
            print("No likely Python web/API server files were found outside excluded folders.")
        return 4

    print(f"Selected backend: {backend.relative_to(repo)}")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("HOST", "0.0.0.0")
    env.setdefault("PORT", str(PORT))
    env.setdefault("RTP_DEV", "1")
    env.setdefault("RTL_DEV", "1")

    print("Starting backend. Press Ctrl+C in this terminal to stop it after browser testing.")

    proc = subprocess.Popen(
        [sys.executable, "-u", str(backend.relative_to(repo))],
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
        print("Upload/paste this full output back to ChatGPT.")
        return 1

    print("")
    print("Browser validation:")
    print("  Open http://localhost:8090")
    print("  Press Ctrl+F5")
    print("  Double-click directly on an airplane icon")
    print("")
    print("Expected:")
    print("  PASS if the aircraft dialog opens and the map does not zoom.")
    print("  FAIL if the map zooms or no dialog opens.")
    print("")
    print("The development backend is still running.")
    print("Press Ctrl+C in this terminal when you are done testing.")

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
