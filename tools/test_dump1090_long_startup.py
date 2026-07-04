#!/usr/bin/env python3
r"""
Long Dump1090 startup wait test for RTL-Windows / RTP-Windows.

Run from MSYS2 UCRT64 repo root:
  python3 tools/test_dump1090_long_startup.py

Why this exists:
  The previous repair test showed dump1090 now stays running, but it was busy
  downloading/loading/building aircraft-database.csv.sqlite. This longer test
  waits for that first-time initialization to finish and for network/http ports
  to appear.

Output:
  C:/Users/jim/Downloads/rtl_windows_dump1090_long_startup_YYYYMMDD_HHMMSS.txt

It does NOT call cmd.exe, PowerShell, or WSL.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


EXPECTED_ADSB_DEVICE_INDEX = "1"
MAX_WAIT_SECONDS = 360
POLL_SECONDS = 5

PORTS_TO_CHECK = [
    (30003, "SBS/BaseStation"),
    (30002, "raw output"),
    (30005, "Beast output"),
    (8080, "Dump1090 HTTP"),
    (8754, "Dump1090 alternate HTTP"),
]

JSON_URLS = [
    "http://127.0.0.1:8080/data/aircraft.json",
    "http://localhost:8080/data/aircraft.json",
    "http://127.0.0.1:8754/data/aircraft.json",
    "http://localhost:8754/data/aircraft.json",
]


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def find_package(repo: Path) -> Path | None:
    root = repo / "runtime" / "build" / "windows-service"
    if not root.exists():
        return None
    pkgs = [p for p in root.glob("RTL-ADS-B-Tracker-Windows-Service-*") if p.is_dir()]
    pkgs = [p for p in pkgs if (p / "dist" / "third_party" / "dump1090" / "dump1090.exe").exists()]
    pkgs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return pkgs[0] if pkgs else None


def make_env(package: Path, dump_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([
        str(dump_dir),
        str(package / "bin"),
        "C:/msys64/ucrt64/bin",
        env.get("PATH", ""),
    ])
    env.setdefault("DUMP1090_HOMEPOS", "38.814165,-105.189199")
    return env


def port_open(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        sock.close()


def summarize_body(body: str) -> str:
    if not body:
        return ""
    try:
        payload = json.loads(body)
    except Exception:
        return " ".join(body.split())[:260]
    if isinstance(payload, dict):
        if isinstance(payload.get("aircraft"), list):
            return f"JSON aircraft_count={len(payload['aircraft'])}; keys={','.join(list(payload.keys())[:8])}"
        return f"JSON keys={','.join(list(payload.keys())[:12])}"
    return f"JSON {type(payload).__name__}"


def http_get(url: str, timeout: int = 2) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(1200).decode("utf-8", errors="replace")
            return True, f"HTTP {response.status}: {summarize_body(body)}"
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read(800).decode("utf-8", errors="replace")
        except Exception:
            pass
        return False, f"HTTP {exc.code}: {summarize_body(body)}"
    except URLError as exc:
        return False, f"URL error: {exc.reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def reader_thread(stream, out_queue: queue.Queue[str]) -> None:
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            out_queue.put(line.rstrip("\r\n"))
    except Exception as exc:
        out_queue.put(f"[reader error] {type(exc).__name__}: {exc}")


def drain_output(out_queue: queue.Queue[str], output_lines: list[str], max_lines: int = 10000) -> list[str]:
    new_lines = []
    while True:
        try:
            line = out_queue.get_nowait()
        except queue.Empty:
            break
        output_lines.append(line)
        new_lines.append(line)
        if len(output_lines) > max_lines:
            del output_lines[:len(output_lines) - max_lines]
    return new_lines


def main() -> int:
    repo = Path.cwd()
    downloads = downloads_dir()
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = downloads / f"rtl_windows_dump1090_long_startup_{stamp}.txt"

    lines: list[str] = []
    lines.append("RTL-Windows / RTP-Windows long Dump1090 startup wait test")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append(f"Max wait seconds: {MAX_WAIT_SECONDS}")
    lines.append("")

    if not (repo / "web" / "app.js").exists():
        lines.append("FAIL: web/app.js not found. Run from repo root.")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: not run from repo root. Output saved to: {out_path}")
        return 2

    package = find_package(repo)
    if not package:
        lines.append("FAIL: could not find service package Dump1090 runtime.")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: package not found. Output saved to: {out_path}")
        return 3

    dump_dir = package / "dist" / "third_party" / "dump1090"
    dump_exe = dump_dir / "dump1090.exe"
    cfg = dump_dir / "dump1090.cfg"
    sqlite_db = dump_dir / "aircraft-database.csv.sqlite"
    csv_db = dump_dir / "aircraft-database.csv"

    lines.append("=" * 90)
    lines.append("Runtime files")
    lines.append("=" * 90)
    for p in [package, dump_dir, dump_exe, cfg, csv_db, sqlite_db]:
        if p.exists():
            try:
                stat = p.stat()
                lines.append(f"PASS: {p} size={stat.st_size} modified={dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')}")
            except Exception:
                lines.append(f"PASS: {p}")
        else:
            lines.append(f"FAIL: {p} missing")

    if not dump_exe.exists() or not cfg.exists():
        lines.append("")
        lines.append("FAIL: dump1090.exe or dump1090.cfg is missing. Re-run repair_and_test_dump1090_package.py first.")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: runtime files missing. Output saved to: {out_path}")
        return 4

    command = [
        str(dump_exe),
        "--config", str(cfg),
        "--device", EXPECTED_ADSB_DEVICE_INDEX,
        "--net",
    ]

    lines.append("")
    lines.append("=" * 90)
    lines.append("Startup command")
    lines.append("=" * 90)
    lines.append(" ".join(command))
    lines.append(f"Working directory: {dump_dir}")

    proc = subprocess.Popen(
        command,
        cwd=str(dump_dir),
        env=make_env(package, dump_dir),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    out_q: queue.Queue[str] = queue.Queue()
    output_lines: list[str] = []
    t = threading.Thread(target=reader_thread, args=(proc.stdout, out_q), daemon=True)
    t.start()

    start = time.time()
    success = False
    first_success_detail = ""
    last_status = ""

    lines.append("")
    lines.append("=" * 90)
    lines.append("Polling")
    lines.append("=" * 90)

    while True:
        elapsed = int(time.time() - start)
        new_out = drain_output(out_q, output_lines)
        for line in new_out[-12:]:
            if line:
                lines.append(f"[dump1090 +{elapsed}s] {line}")

        rc = proc.poll()
        if rc is not None:
            drain_output(out_q, output_lines)
            lines.append(f"FAIL: dump1090 exited after {elapsed}s with code {rc}.")
            break

        open_ports = [(port, label) for port, label in PORTS_TO_CHECK if port_open(port)]
        json_ok = []
        for url in JSON_URLS:
            ok, detail = http_get(url, timeout=1)
            if ok:
                json_ok.append((url, detail))

        if json_ok:
            success = True
            first_success_detail = "Aircraft JSON responded: " + "; ".join(f"{u} -> {d}" for u, d in json_ok)
            lines.append(f"PASS: {first_success_detail}")
            break

        if open_ports:
            success = True
            first_success_detail = "Network ports opened: " + ", ".join(f"{port} {label}" for port, label in open_ports)
            lines.append(f"PASS: {first_success_detail}")
            break

        # Write periodic concise status.
        current_status = f"+{elapsed}s running; no expected ports/json yet"
        if current_status != last_status and (elapsed == 0 or elapsed % 30 == 0):
            lines.append(current_status)
            last_status = current_status

        if elapsed >= MAX_WAIT_SECONDS:
            lines.append(f"FAIL: dump1090 was still running after {MAX_WAIT_SECONDS}s, but no expected ports or aircraft JSON responded.")
            break

        time.sleep(POLL_SECONDS)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Final port checks")
    lines.append("=" * 90)
    for port, label in PORTS_TO_CHECK:
        ok = port_open(port)
        lines.append(f"{'PASS' if ok else 'FAIL'}: port {port} {label}")

    lines.append("")
    lines.append("Final aircraft JSON checks:")
    for url in JSON_URLS:
        ok, detail = http_get(url, timeout=2)
        lines.append(f"{'PASS' if ok else 'FAIL'}: {url} -> {detail}")

    lines.append("")
    lines.append("Stopping dump1090...")
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    drain_output(out_q, output_lines)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Captured dump1090 output tail")
    lines.append("=" * 90)
    for line in output_lines[-250:]:
        lines.append(line)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)
    if success:
        lines.append("PASS: dump1090 completed enough startup to expose network/http output.")
        lines.append(first_success_detail)
        lines.append("")
        lines.append("Next step: restart/reinstall the Windows service and retest /api/aircraft.json.")
        rc = 0
    else:
        lines.append("FAIL: dump1090 did not expose expected ports/http output within the wait window.")
        lines.append("")
        lines.append("Upload this file to ChatGPT.")
        rc = 1

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'PASS' if rc == 0 else 'FAIL'}: Long Dump1090 startup test complete.")
    print("Output saved to:")
    print(f"  {out_path}")
    print("Windows path:")
    print(f"  {str(out_path).replace('/', '\\\\')}")
    print("Upload this .txt file if FAIL, or restart/reinstall service if PASS.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
