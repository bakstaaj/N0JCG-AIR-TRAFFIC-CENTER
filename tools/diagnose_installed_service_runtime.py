#!/usr/bin/env python3
r"""
Diagnose the actual installed RTLADSBTracker Windows service runtime.

Run from MSYS2 UCRT64 repo root:
  python3 tools/diagnose_installed_service_runtime.py

Output:
  C:/Users/jim/Downloads/rtl_windows_installed_service_runtime_YYYYMMDD_HHMMSS.txt

Checks:
  - Windows service ImagePath from registry/sc.exe
  - Actual service executable folder
  - Whether actual installed runtime has repaired dump1090.cfg and DLLs
  - Whether actual installed runtime has patched web/app.js
  - Backend API /api/status and /api/aircraft.json
  - Dump1090 ports

This script does NOT call cmd.exe, PowerShell, or WSL. It may call sc.exe directly
and may read the Windows registry if available.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shlex
import socket
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


SERVICE_ID = "RTLADSBTracker"
BASE = "http://127.0.0.1:8090"

PATCH_MARKERS = [
    "function rtpV33StopAircraftMarkerDblclick",
    "function rtpV33OpenAircraftDetailsFromMap",
    "function rtpV33BindAircraftMarkerDblclick",
    'addEventListener("dblclick"',
    "rtpV33BindAircraftMarkerDblclick(m,hex,a)",
]

REQUIRED_DUMP_DLLS = [
    "librtlsdr.dll",
    "libusb-1.0.dll",
    "libwinpthread-1.dll",
]

PORTS = [
    (8090, "RTL ADS-B Tracker backend/UI"),
    (30003, "Dump1090 SBS/BaseStation"),
    (30002, "Dump1090 raw output"),
    (30005, "Dump1090 Beast output"),
    (8080, "Dump1090 HTTP"),
]


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def run_direct(args: list[str], timeout: int = 8) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout
    except FileNotFoundError:
        return 127, f"FAIL: executable not found: {args[0]}"
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        return 124, out + f"\nFAIL: {' '.join(args)} timed out after {timeout}s."
    except Exception as exc:
        return 1, f"FAIL: {type(exc).__name__}: {exc}"


def get_service_imagepath_registry() -> tuple[str | None, str]:
    try:
        import winreg  # type: ignore
    except Exception as exc:
        return None, f"winreg unavailable: {type(exc).__name__}: {exc}"

    try:
        key_path = rf"SYSTEM\CurrentControlSet\Services\{SERVICE_ID}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "ImagePath")
            return str(value), "PASS: read ImagePath from registry"
    except Exception as exc:
        return None, f"registry read failed: {type(exc).__name__}: {exc}"


def get_service_imagepath_sc() -> tuple[str | None, str]:
    rc, out = run_direct(["sc.exe", "qc", SERVICE_ID], timeout=8)
    if rc != 0:
        return None, f"sc.exe qc failed rc={rc}: {out.strip()}"

    image = None
    for line in out.splitlines():
        if "BINARY_PATH_NAME" in line:
            image = line.split(":", 1)[1].strip()
            break
    return image, out


def parse_exe_from_imagepath(imagepath: str) -> Path | None:
    if not imagepath:
        return None

    s = imagepath.strip()

    # Registry service ImagePath can include quotes and args.
    if s.startswith('"'):
        end = s.find('"', 1)
        if end > 1:
            return Path(s[1:end])

    # Fall back to first token that ends in .exe.
    m = re.search(r"([A-Za-z]:\\.*?\.exe|/[^\s]+?\.exe)", s, re.I)
    if m:
        return Path(m.group(1))

    try:
        parts = shlex.split(s, posix=False)
        if parts:
            return Path(parts[0].strip('"'))
    except Exception:
        pass

    return Path(s)


def port_open(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.8)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        sock.close()


def http_get(url: str, timeout: int = 6) -> tuple[bool, int | None, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(8000).decode("utf-8", errors="replace")
            return True, response.status, body
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read(4000).decode("utf-8", errors="replace")
        except Exception:
            pass
        return False, exc.code, body
    except URLError as exc:
        return False, None, f"URL error: {exc.reason}"
    except Exception as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


def json_summary(body: str) -> tuple[object | None, str]:
    try:
        payload = json.loads(body)
    except Exception:
        return None, "non-JSON: " + " ".join(body.split())[:300]

    if isinstance(payload, dict):
        if isinstance(payload.get("aircraft"), list):
            return payload, f"aircraft_count={len(payload['aircraft'])}, messages={payload.get('messages', 'unknown')}, keys={','.join(list(payload.keys())[:10])}"
        err = payload.get("error") or payload.get("message") or payload.get("detail")
        if err:
            return payload, f"error={err!r}, keys={','.join(list(payload.keys())[:10])}"
        compact = {k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool)) or v is None}
        return payload, json.dumps(compact, ensure_ascii=True)[:800]

    return payload, f"JSON {type(payload).__name__}"


def find_dump_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []

    candidates: list[Path] = []

    preferred = [
        root / "dist" / "third_party" / "dump1090",
        root / "app" / "dist" / "third_party" / "dump1090",
        root / "third_party" / "dump1090",
        root / "app" / "third_party" / "dump1090",
    ]

    for p in preferred:
        if (p / "dump1090.exe").exists():
            candidates.append(p)

    try:
        for exe in root.rglob("dump1090.exe"):
            if exe.is_file():
                candidates.append(exe.parent)
    except Exception:
        pass

    result: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p).lower()
        if key not in seen:
            result.append(p)
            seen.add(key)
    return result


def find_web_app_js(root: Path) -> list[Path]:
    candidates = [
        root / "web" / "app.js",
        root / "app" / "web" / "app.js",
    ]

    found = [p for p in candidates if p.exists()]
    try:
        for p in root.rglob("app.js"):
            if p.is_file() and "web" in [part.lower() for part in p.parts]:
                found.append(p)
    except Exception:
        pass

    result: list[Path] = []
    seen: set[str] = set()
    for p in found:
        key = str(p).lower()
        if key not in seen:
            result.append(p)
            seen.add(key)
    return result


def validate_patch(path: Path) -> list[str]:
    if not path.exists():
        return ["app.js missing"]
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [m for m in PATCH_MARKERS if m not in text]
    if '.on("dblclick",event=>rtpV33OpenAircraftDetailsFromMap(hex,a,event))' in text:
        missing.append("old inline dblclick hook still present")
    return missing


def summarize_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        st = path.stat()
        return f"exists size={st.st_size} modified={dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')}"
    except Exception:
        return "exists"


def main() -> int:
    repo = Path.cwd()
    downloads = downloads_dir()
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = downloads / f"rtl_windows_installed_service_runtime_{stamp}.txt"

    lines: list[str] = []
    failures: list[str] = []

    lines.append("RTL-Windows / RTP-Windows installed service runtime diagnosis")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append(f"Service ID: {SERVICE_ID}")
    lines.append("")

    lines.append("=" * 90)
    lines.append("Service ImagePath")
    lines.append("=" * 90)

    reg_image, reg_msg = get_service_imagepath_registry()
    sc_image, sc_msg = get_service_imagepath_sc()

    lines.append(f"Registry: {reg_msg}")
    if reg_image:
        lines.append(f"Registry ImagePath: {reg_image}")

    lines.append("")
    lines.append("sc.exe qc output/result:")
    lines.append(sc_msg.strip())
    if sc_image:
        lines.append(f"Parsed sc.exe ImagePath: {sc_image}")

    image = reg_image or sc_image
    if not image:
        failures.append("Could not determine installed service ImagePath.")
        service_exe = None
        service_root = None
    else:
        service_exe = parse_exe_from_imagepath(image)
        service_root = service_exe.parent if service_exe else None
        lines.append("")
        lines.append(f"Parsed service executable: {service_exe}")
        lines.append(f"Parsed service root: {service_root}")
        if service_exe and not service_exe.exists():
            failures.append(f"Service executable does not exist at parsed path: {service_exe}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Port checks")
    lines.append("=" * 90)
    for port, label in PORTS:
        ok = port_open(port)
        lines.append(f"{'PASS' if ok else 'FAIL'}: port {port} {label}")
    if not port_open(8090):
        failures.append("Port 8090 is not open; service/backend is not reachable.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Backend endpoint checks")
    lines.append("=" * 90)

    ok, status, body = http_get(BASE + "/api/status", timeout=6)
    payload, summary = json_summary(body)
    lines.append(f"{'PASS' if ok else 'FAIL'}: /api/status -> HTTP {status}; {summary}")
    if not ok:
        failures.append("/api/status is not returning HTTP 200.")

    ok, status, body = http_get(BASE + "/api/aircraft.json", timeout=8)
    payload, summary = json_summary(body)
    lines.append(f"{'PASS' if ok else 'FAIL'}: /api/aircraft.json -> HTTP {status}; {summary}")
    if not ok:
        failures.append(f"/api/aircraft.json failed: HTTP {status}; {summary}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Actual installed runtime file checks")
    lines.append("=" * 90)

    if service_root:
        roots_to_check = [service_root]
        if service_root.name.lower() == "app":
            roots_to_check.append(service_root.parent)
        else:
            roots_to_check.append(service_root / "app")

        # Deduplicate roots.
        dedup_roots: list[Path] = []
        seen_roots: set[str] = set()
        for r in roots_to_check:
            key = str(r).lower()
            if key not in seen_roots:
                dedup_roots.append(r)
                seen_roots.add(key)

        for r in dedup_roots:
            lines.append(f"Runtime root candidate: {r} -> {summarize_file(r)}")

        dump_dirs: list[Path] = []
        app_js_files: list[Path] = []
        for r in dedup_roots:
            dump_dirs.extend(find_dump_dirs(r))
            app_js_files.extend(find_web_app_js(r))

        # Dedup lists.
        dump_dirs = list(dict.fromkeys(dump_dirs))
        app_js_files = list(dict.fromkeys(app_js_files))

        lines.append("")
        lines.append("Dump1090 runtime directories:")
        if not dump_dirs:
            lines.append("FAIL: no dump1090.exe found under actual installed service runtime root candidates.")
            failures.append("No dump1090.exe found under installed service runtime.")
        else:
            for d in dump_dirs:
                lines.append(f"Directory: {d}")
                lines.append(f"  dump1090.exe: {summarize_file(d / 'dump1090.exe')}")
                lines.append(f"  dump1090.cfg: {summarize_file(d / 'dump1090.cfg')}")
                if not (d / "dump1090.cfg").exists():
                    failures.append(f"Installed dump1090.cfg missing: {d / 'dump1090.cfg'}")
                for dll in REQUIRED_DUMP_DLLS:
                    p = d / dll
                    lines.append(f"  {dll}: {summarize_file(p)}")
                    if not p.exists():
                        failures.append(f"Installed Dump1090 DLL missing: {p}")

        lines.append("")
        lines.append("Installed web/app.js files:")
        if not app_js_files:
            lines.append("FAIL: no web/app.js found under actual installed service runtime root candidates.")
            failures.append("No installed web/app.js found under service runtime.")
        else:
            for p in app_js_files:
                missing = validate_patch(p)
                lines.append(f"File: {p} -> {summarize_file(p)}")
                if missing:
                    lines.append("  FAIL: V2 double-click patch missing/problem:")
                    for item in missing:
                        lines.append(f"    - {item}")
                    failures.append(f"Installed app.js is not patched: {p}")
                else:
                    lines.append("  PASS: V2 double-click patch markers present.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Repo repaired package reference checks")
    lines.append("=" * 90)
    repo_pkg = repo / "runtime" / "build" / "windows-service" / "RTL-ADS-B-Tracker-Windows-Service-v1.1.0"
    repo_dump = repo_pkg / "dist" / "third_party" / "dump1090"
    repo_app_candidates = [repo_pkg / "app" / "web" / "app.js", repo_pkg / "web" / "app.js", repo / "web" / "app.js"]
    lines.append(f"Repo package: {repo_pkg} -> {summarize_file(repo_pkg)}")
    lines.append(f"Repo package dump1090.cfg: {summarize_file(repo_dump / 'dump1090.cfg')}")
    for dll in REQUIRED_DUMP_DLLS:
        lines.append(f"Repo package {dll}: {summarize_file(repo_dump / dll)}")
    for p in repo_app_candidates:
        if p.exists():
            missing = validate_patch(p)
            lines.append(f"Repo app candidate: {p} -> {'PASS patched' if not missing else 'FAIL not patched: ' + ', '.join(missing)}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)

    if failures:
        lines.append("FAIL: Installed service runtime diagnosis found problems.")
        lines.append("")
        lines.append("Failure details:")
        for f in failures:
            lines.append(f"  - {f}")
        lines.append("")
        lines.append("Upload this full file to ChatGPT.")
        rc = 1
    else:
        lines.append("PASS: Installed service runtime has repaired Dump1090 files, patched app.js, and /api/aircraft.json is reachable.")
        lines.append("")
        lines.append("Browser test:")
        lines.append("  Open http://localhost:8090")
        lines.append("  Press Ctrl+F5")
        lines.append("  Double-click an airplane icon.")
        rc = 0

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'PASS' if rc == 0 else 'FAIL'}: Installed service runtime diagnosis complete.")
    print("Output saved to:")
    print(f"  {out_path}")
    print("Windows path:")
    print(f"  {str(out_path).replace('/', '\\\\')}")
    print("Upload this .txt file if FAIL.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
