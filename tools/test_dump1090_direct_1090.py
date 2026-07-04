#!/usr/bin/env python3
r"""
Direct Dump1090 startup test for RTL-Windows / RTP-Windows.

Run from MSYS2 UCRT64 repo root:
  python3 tools/test_dump1090_direct_1090.py

Output:
  C:/Users/jim/Downloads/rtl_windows_dump1090_direct_test_YYYYMMDD_HHMMSS.txt

What it checks:
  - Uses the visible ADS-B dongle at device index 1 / serial 00001090.
  - Starts the packaged dump1090.exe directly, outside the app/service.
  - Prepends MSYS2 UCRT64 bin to PATH so required DLLs can be found.
  - Checks whether dump1090 stays running.
  - Checks common Dump1090 ports and aircraft JSON URLs.
  - Saves all output to Downloads.

It does NOT call cmd.exe, PowerShell, or WSL.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


EXPECTED_ADSB_SERIAL = "00001090"
EXPECTED_DEVICE_INDEX = "1"
TEST_SECONDS = 22

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

COMMAND_VARIANTS = [
    ["--device", EXPECTED_DEVICE_INDEX, "--net"],
    ["--device", EXPECTED_ADSB_SERIAL, "--net"],
    ["--device", EXPECTED_DEVICE_INDEX, "--net", "--interactive"],
]


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def path_excluded(path: Path, repo: Path) -> bool:
    try:
        rel = path.relative_to(repo)
    except ValueError:
        return True
    return any(part in {".git", "__pycache__", ".venv", "venv", "env", "test_output"} for part in rel.parts)


def find_dump1090(repo: Path) -> list[Path]:
    preferred = [
        repo / "runtime/build/windows-service/RTL-ADS-B-Tracker-Windows-Service-v1.1.0/dist/third_party/dump1090/dump1090.exe",
        repo / "dist/third_party/dump1090/dump1090.exe",
        repo / "build/third_party/dump1090/Dump1090-src/dump1090.exe",
    ]

    found = [p for p in preferred if p.exists()]
    for p in repo.rglob("dump1090.exe"):
        if not path_excluded(p, repo) and p.is_file():
            found.append(p)

    result = []
    seen = set()
    for p in found:
        key = str(p).lower()
        if key not in seen:
            result.append(p)
            seen.add(key)
    return result


def find_msys2_bin() -> Path | None:
    candidates = [
        Path("C:/msys64/ucrt64/bin"),
        Path("/ucrt64/bin"),
    ]

    for c in candidates:
        if c.exists():
            return c

    python_path = Path(sys.executable)
    if python_path.parent.exists():
        return python_path.parent

    return None


def find_dlls(repo: Path, names: list[str]) -> dict[str, list[Path]]:
    found = {name: [] for name in names}
    search_roots = [repo]
    msys_bin = find_msys2_bin()
    if msys_bin:
        search_roots.insert(0, msys_bin)

    for root in search_roots:
        if root.is_file():
            continue
        if not root.exists():
            continue
        for name in names:
            if root == msys_bin:
                p = root / name
                if p.exists():
                    found[name].append(p)
            else:
                for p in root.rglob(name):
                    if not path_excluded(p, repo) and p.is_file():
                        found[name].append(p)

    return found


def make_env(dump_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    msys_bin = find_msys2_bin()

    path_parts = [str(dump_dir)]
    if msys_bin:
        path_parts.append(str(msys_bin))
    path_parts.append(env.get("PATH", ""))

    env["PATH"] = os.pathsep.join(path_parts)
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


def run_help(dump: Path, repo: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            [str(dump), "--help"],
            cwd=str(dump.parent),
            env=make_env(dump.parent),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
        )
        return proc.returncode, proc.stdout
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def start_and_probe(dump: Path, args: list[str], lines: list[str]) -> tuple[bool, bool, str]:
    command = [str(dump)] + args
    lines.append(f"Command: {' '.join(command)}")
    lines.append(f"Working directory: {dump.parent}")
    lines.append(f"Test duration: {TEST_SECONDS} seconds")

    proc = subprocess.Popen(
        command,
        cwd=str(dump.parent),
        env=make_env(dump.parent),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    time.sleep(5)
    early_rc = proc.poll()
    if early_rc is not None:
        out = ""
        try:
            out = proc.stdout.read() if proc.stdout else ""
        except Exception:
            pass
        lines.append(f"FAIL: dump1090 exited early with code {early_rc}.")
        lines.append("Output:")
        lines.append((out or "").rstrip())
        return False, False, out or ""

    lines.append("PASS: dump1090 stayed running for initial startup window.")

    any_port = False
    lines.append("")
    lines.append("Port checks while dump1090 is running:")
    for port, label in PORTS_TO_CHECK:
        ok = port_open(port)
        any_port = any_port or ok
        lines.append(f"  {'PASS' if ok else 'FAIL'}: port {port} {label}")

    any_json = False
    lines.append("")
    lines.append("Aircraft JSON checks while dump1090 is running:")
    for url in JSON_URLS:
        ok, detail = http_get(url, timeout=2)
        any_json = any_json or ok
        lines.append(f"  {'PASS' if ok else 'FAIL'}: {url} -> {detail}")

    remaining = max(0, TEST_SECONDS - 5)
    if remaining:
        time.sleep(remaining)

    still_running = proc.poll() is None
    if still_running:
        lines.append("")
        lines.append("PASS: dump1090 was still running at the end of the test window.")
    else:
        lines.append("")
        lines.append(f"FAIL: dump1090 exited during the test window with code {proc.returncode}.")

    lines.append("")
    lines.append("Stopping dump1090 test process...")
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    out = ""
    try:
        if proc.stdout:
            out = proc.stdout.read() or ""
    except Exception:
        pass

    lines.append("")
    lines.append("dump1090 process output:")
    lines.append(out.rstrip())

    return still_running, any_port or any_json, out


def main() -> int:
    repo = Path.cwd()
    downloads = downloads_dir()
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = downloads / f"rtl_windows_dump1090_direct_test_{stamp}.txt"

    lines: list[str] = []
    lines.append("RTL-Windows / RTP-Windows direct Dump1090 test")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append(f"Expected ADS-B serial: {EXPECTED_ADSB_SERIAL}")
    lines.append(f"Expected device index: {EXPECTED_DEVICE_INDEX}")
    lines.append("")

    if not (repo / "web" / "app.js").exists():
        lines.append("FAIL: web/app.js was not found. Run from repo root.")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: not run from repo root. Output saved to: {out_path}")
        return 2

    dumps = find_dump1090(repo)
    lines.append("=" * 90)
    lines.append("Dump1090 discovery")
    lines.append("=" * 90)
    if not dumps:
        lines.append("FAIL: no dump1090.exe was found.")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: no dump1090.exe found. Output saved to: {out_path}")
        return 3

    for p in dumps:
        lines.append(f"  - {p}")

    dump = dumps[0]
    lines.append("")
    lines.append(f"Selected dump1090: {dump}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("DLL discovery")
    lines.append("=" * 90)
    dlls = find_dlls(repo, ["rtlsdr.dll", "librtlsdr.dll", "libusb-1.0.dll", "pthreadGC2.dll", "libwinpthread-1.dll"])
    for name, paths in dlls.items():
        if paths:
            lines.append(f"PASS: {name} found:")
            for p in paths[:12]:
                lines.append(f"  - {p}")
        else:
            lines.append(f"WARN: {name} not found in MSYS2 bin or repo.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Dump1090 help/version sanity check")
    lines.append("=" * 90)
    rc_help, out_help = run_help(dump, repo)
    lines.append(f"Return code: {rc_help}")
    lines.append(out_help[:3000].rstrip())

    help_text = out_help.lower()
    variants = COMMAND_VARIANTS[:]
    # Keep variants that mention supported options when possible.
    if "--interactive" not in help_text:
        variants = [v for v in variants if "--interactive" not in v]

    overall_ok = False
    started_but_no_ports = False

    for i, args in enumerate(variants, 1):
        lines.append("")
        lines.append("=" * 90)
        lines.append(f"Direct startup attempt {i}")
        lines.append("=" * 90)

        ok_running, ok_service, out = start_and_probe(dump, args, lines)

        if ok_running and ok_service:
            overall_ok = True
            lines.append("")
            lines.append("PASS: this dump1090 command started and exposed a network/http service.")
            break
        if ok_running and not ok_service:
            started_but_no_ports = True
            lines.append("")
            lines.append("WARN: dump1090 stayed running, but expected ports/JSON were not reachable.")
        else:
            lower = out.lower()
            if "usb_open error" in lower or "failed to open" in lower or "no supported devices found" in lower:
                lines.append("Finding: dump1090 could not open the RTL-SDR device.")
            if "not recognized" in lower or "unknown option" in lower or "invalid option" in lower:
                lines.append("Finding: dump1090 rejected one or more command-line options.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)

    if overall_ok:
        lines.append("PASS: Direct dump1090 startup works with the visible 1090 dongle.")
        lines.append("")
        lines.append("Next likely issue if the service still fails:")
        lines.append("  The service/backend runtime is not launching dump1090 with the same PATH/device settings used by this test.")
        rc = 0
    elif started_but_no_ports:
        lines.append("FAIL: dump1090 starts but did not expose expected network/http outputs.")
        lines.append("Upload this file to ChatGPT so we can adjust the dump1090 command/config.")
        rc = 1
    else:
        lines.append("FAIL: direct dump1090 startup did not work.")
        lines.append("")
        lines.append("Likely causes:")
        lines.append("  - dump1090 cannot open device index 1 / serial 00001090.")
        lines.append("  - dump1090 is missing DLLs when not run with the same environment as rtl_test.")
        lines.append("  - dump1090 command-line options differ from the backend expectation.")
        lines.append("")
        lines.append("Upload this full file to ChatGPT.")
        rc = 1

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'PASS' if rc == 0 else 'FAIL'}: Direct dump1090 test complete.")
    print("Output saved to:")
    print(f"  {out_path}")
    print("Windows path:")
    print(f"  {str(out_path).replace('/', '\\\\')}")
    print("Upload this .txt file if the result is FAIL or if the service still says ADS-B decoder is not running.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
