#!/usr/bin/env python3
r"""
Repair/check backend DecoderManager prerequisites for RTLADSBTracker service.

Run from MSYS2 UCRT64 repo root:
  python3 tools/repair_backend_decoder_prereqs.py

What it checks/repairs:
  - Actual installed service root from Windows registry/sc.exe.
  - dist/native-windows/rtl_dual_device_probe.exe
  - dist/third_party/dump1090/airport-codes.csv
  - dist/third_party/dump1090/dump1090.exe/cfg/DLLs
  - ProgramData backend logs and runtime config
  - Port 18080, which is the service-configured Dump1090 HTTP port
  - Current /api/aircraft.json status

It copies missing files from repo candidates when it can find them.
It does NOT call cmd.exe, PowerShell, WSL, or restart the service.
After PASS/repair, restart the service manually with restart_service.cmd.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


SERVICE_ID = "RTLADSBTracker"
BASE_URL = "http://127.0.0.1:8090"

DUMP_DLLS = [
    "librtlsdr.dll",
    "libusb-1.0.dll",
    "libwinpthread-1.dll",
]


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def programdata_dir() -> Path:
    return Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))


def run_direct(args: list[str], timeout: int = 10, cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=env,
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


def get_service_imagepath() -> str | None:
    try:
        import winreg  # type: ignore
        key_path = rf"SYSTEM\CurrentControlSet\Services\{SERVICE_ID}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "ImagePath")
            return str(value)
    except Exception:
        pass

    rc, out = run_direct(["sc.exe", "qc", SERVICE_ID], timeout=8)
    if rc != 0:
        return None
    for line in out.splitlines():
        if "BINARY_PATH_NAME" in line:
            return line.split(":", 1)[1].strip()
    return None


def parse_exe(imagepath: str | None) -> Path | None:
    if not imagepath:
        return None
    s = imagepath.strip()
    if s.startswith('"'):
        end = s.find('"', 1)
        if end > 1:
            return Path(s[1:end])
    m = re.search(r"([A-Za-z]:\\.*?\.exe|/[^\s]+?\.exe)", s, re.I)
    if m:
        return Path(m.group(1))
    return Path(s.split()[0].strip('"')) if s.split() else None


def file_status(path: Path) -> str:
    if not path.exists():
        return f"FAIL missing: {path}"
    try:
        st = path.stat()
        return f"PASS exists: {path} size={st.st_size} modified={dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')}"
    except Exception:
        return f"PASS exists: {path}"


def read_text(path: Path, max_chars: int = 50000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[read failed: {type(exc).__name__}: {exc}]"
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


def path_excluded(path: Path, repo: Path) -> bool:
    try:
        rel = path.relative_to(repo)
    except Exception:
        return False
    excluded = {".git", "__pycache__", ".venv", "venv", "env", "test_output"}
    return any(part in excluded for part in rel.parts)


def find_candidates(repo: Path, filename: str) -> list[Path]:
    preferred: list[Path] = []

    if filename == "rtl_dual_device_probe.exe":
        preferred = [
            repo / "dist" / "native-windows" / filename,
            repo / "runtime" / "build" / "windows-service" / "RTL-ADS-B-Tracker-Windows-Service-v1.1.0" / "dist" / "native-windows" / filename,
        ]
    elif filename == "airport-codes.csv":
        preferred = [
            repo / "build" / "third_party" / "dump1090" / "Dump1090-src" / filename,
            repo / "dist" / "third_party" / "dump1090" / filename,
            repo / "runtime" / "build" / "windows-service" / "RTL-ADS-B-Tracker-Windows-Service-v1.1.0" / "dist" / "third_party" / "dump1090" / filename,
        ]
    elif filename in DUMP_DLLS:
        preferred = [
            repo / "runtime" / "build" / "windows-service" / "RTL-ADS-B-Tracker-Windows-Service-v1.1.0" / "bin" / filename,
            repo / "bin" / filename,
            Path("C:/msys64/ucrt64/bin") / filename,
        ]
    elif filename == "dump1090.cfg":
        preferred = [
            repo / "build" / "third_party" / "dump1090" / "Dump1090-src" / filename,
            repo / "dist" / "third_party" / "dump1090" / filename,
        ]

    found = [p for p in preferred if p.exists()]

    try:
        for p in repo.rglob(filename):
            if p.is_file() and not path_excluded(p, repo):
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


def copy_candidate(repo: Path, filename: str, dest: Path, lines: list[str], stamp: str) -> bool:
    if dest.exists():
        lines.append(f"PASS: target already exists: {dest}")
        return True

    candidates = find_candidates(repo, filename)
    lines.append(f"Candidate search for {filename}: {len(candidates)} found")
    for c in candidates[:20]:
        lines.append(f"  - {c}")

    src = None
    for c in candidates:
        try:
            if c.resolve() != dest.resolve():
                src = c
                break
        except Exception:
            src = c
            break

    if not src:
        lines.append(f"FAIL: could not find source candidate for missing {dest}")
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    lines.append(f"PASS: copied {src} -> {dest}")
    return True


def backup_and_copy(src: Path, dest: Path, lines: list[str], stamp: str) -> bool:
    if not src.exists():
        lines.append(f"FAIL: source missing: {src}")
        return False
    if dest.exists():
        backup = dest.with_name(f"{dest.name}.bak_decoder_prereq_{stamp}")
        try:
            shutil.copy2(dest, backup)
            lines.append(f"PASS: backed up {dest} -> {backup}")
        except Exception as exc:
            lines.append(f"WARN: backup failed for {dest}: {type(exc).__name__}: {exc}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    lines.append(f"PASS: copied {src} -> {dest}")
    return True


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


def http_get(url: str, timeout: int = 5) -> tuple[bool, int | None, str]:
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


def summarize_json_or_text(body: str) -> str:
    try:
        payload = json.loads(body)
    except Exception:
        return " ".join(body.split())[:800]
    if isinstance(payload, dict):
        if isinstance(payload.get("aircraft"), list):
            return f"aircraft_count={len(payload['aircraft'])}, messages={payload.get('messages', 'unknown')}, keys={','.join(list(payload.keys())[:12])}"
        err = payload.get("error") or payload.get("message") or payload.get("detail")
        if err:
            return f"error={err!r}, keys={','.join(list(payload.keys())[:12])}"
        compact = {k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool)) or v is None}
        return json.dumps(compact, ensure_ascii=True)[:1000]
    return f"JSON {type(payload).__name__}"


def make_probe_env(service_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["RTL_ADSB_TRACKER_ROOT"] = str(service_root)
    env["RTL_ADSB_TRACKER_RUNTIME"] = str(programdata_dir() / "RTL ADS-B Tracker" / "runtime")
    env["PATH"] = os.pathsep.join([
        str(service_root / "bin"),
        str(service_root / "dist" / "native-windows"),
        str(service_root / "dist" / "third_party" / "dump1090"),
        str(service_root / "dist" / "third_party" / "dump1090"),
        "C:/msys64/ucrt64/bin",
        env.get("PATH", ""),
    ])
    return env


def main() -> int:
    repo = Path.cwd()
    downloads = downloads_dir()
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = downloads / f"rtl_windows_decoder_prereq_repair_{stamp}.txt"

    lines: list[str] = []
    failures: list[str] = []

    lines.append("RTL-Windows / RTP-Windows backend DecoderManager prereq repair/check")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append("")

    if not (repo / "web" / "app.js").exists():
        lines.append("FAIL: web/app.js not found. Run from repo root.")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: run from repo root. Output saved to: {out_path}")
        return 2

    image = get_service_imagepath()
    service_exe = parse_exe(image)
    if not service_exe:
        lines.append("FAIL: could not determine RTLADSBTracker service executable path.")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: service path unknown. Output saved to: {out_path}")
        return 3

    service_root = service_exe.parent
    native_dir = service_root / "dist" / "native-windows"
    dump_dir = service_root / "dist" / "third_party" / "dump1090"
    programdata_root = programdata_dir() / "RTL ADS-B Tracker"
    runtime_settings = programdata_root / "runtime" / "settings"

    prereq_paths = {
        "service_exe": service_exe,
        "backend_exe": service_root / "app" / "backend" / "RTLADSBTrackerBackend.exe",
        "role_probe": native_dir / "rtl_dual_device_probe.exe",
        "dump1090": dump_dir / "dump1090.exe",
        "airport_db": dump_dir / "airport-codes.csv",
        "dump_cfg": dump_dir / "dump1090.cfg",
        "librtlsdr": dump_dir / "librtlsdr.dll",
        "libusb": dump_dir / "libusb-1.0.dll",
        "libwinpthread": dump_dir / "libwinpthread-1.dll",
    }

    lines.append("=" * 90)
    lines.append("Service/runtime paths")
    lines.append("=" * 90)
    lines.append(f"Service ImagePath: {image}")
    lines.append(f"Service root: {service_root}")
    lines.append(f"ProgramData app root: {programdata_root}")
    lines.append(f"ProgramData runtime settings: {runtime_settings}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Pre-repair prerequisite file status")
    lines.append("=" * 90)
    for key, path in prereq_paths.items():
        lines.append(f"{key}: {file_status(path)}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Repair actions")
    lines.append("=" * 90)

    # These are required by DecoderManager.check_runtime_files().
    if not copy_candidate(repo, "rtl_dual_device_probe.exe", prereq_paths["role_probe"], lines, stamp):
        failures.append("Missing required role probe: rtl_dual_device_probe.exe")

    if not copy_candidate(repo, "airport-codes.csv", prereq_paths["airport_db"], lines, stamp):
        failures.append("Missing required Dump1090 airport-codes.csv")

    if not copy_candidate(repo, "dump1090.cfg", prereq_paths["dump_cfg"], lines, stamp):
        failures.append("Missing Dump1090 config dump1090.cfg")

    for dll in DUMP_DLLS:
        if not copy_candidate(repo, dll, dump_dir / dll, lines, stamp):
            failures.append(f"Missing required/support DLL: {dll}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Post-repair prerequisite file status")
    lines.append("=" * 90)
    for key, path in prereq_paths.items():
        lines.append(f"{key}: {file_status(path)}")
        if key in {"role_probe", "dump1090", "airport_db", "dump_cfg"} and not path.exists():
            failures.append(f"Still missing required file: {path}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Role probe test as current user with service-like PATH")
    lines.append("=" * 90)
    role_probe = prereq_paths["role_probe"]
    if role_probe.exists():
        rc, out = run_direct([str(role_probe), "--json"], timeout=15, cwd=service_root, env=make_probe_env(service_root))
        lines.append(f"Command rc={rc}: {role_probe} --json")
        lines.append(out.strip())
        if rc != 0:
            failures.append("Role probe failed when run directly as current user.")
        else:
            try:
                payload = json.loads(out.strip())
                adsb = payload.get("adsb", {})
                audio = payload.get("audio", {})
                lines.append(f"Parsed adsb serial/index: {adsb.get('serial')} / {adsb.get('index')}")
                lines.append(f"Parsed audio serial/index: {audio.get('serial')} / {audio.get('index')}")
                if adsb.get("serial") != "00001090":
                    failures.append("Role probe did not resolve ADS-B serial 00001090.")
            except Exception as exc:
                failures.append(f"Role probe output was not parseable JSON: {type(exc).__name__}: {exc}")
    else:
        lines.append("FAIL: role probe missing; skipped direct probe test.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("ProgramData backend/runtime files")
    lines.append("=" * 90)
    pdata_files = [
        programdata_root / "logs" / "backend.log",
        runtime_settings / "dump1090_backend.log",
        runtime_settings / "dump1090_backend_runtime.cfg",
        runtime_settings / "application_settings.json",
    ]
    service_log_dir = programdata_root / "logs" / "service"
    if service_log_dir.exists():
        try:
            pdata_files.extend(sorted(service_log_dir.glob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:8])
        except Exception:
            pass

    for p in pdata_files:
        lines.append(file_status(p))
        if p.exists() and p.is_file():
            lines.append("----- tail/content begin -----")
            lines.append(read_text(p, max_chars=25000))
            lines.append("----- tail/content end -----")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Current port/API checks")
    lines.append("=" * 90)
    for port, label in [
        (8090, "backend/UI"),
        (18080, "service-configured Dump1090 HTTP"),
        (8080, "direct-test Dump1090 HTTP"),
        (30003, "SBS/BaseStation"),
        (30002, "raw output"),
        (30005, "Beast output"),
    ]:
        lines.append(f"{'PASS' if port_open(port) else 'FAIL'}: port {port} {label}")

    for url in [
        BASE_URL + "/api/status",
        BASE_URL + "/api/aircraft.json",
        "http://127.0.0.1:18080/data/aircraft.json",
        "http://127.0.0.1:8080/data/aircraft.json",
    ]:
        ok, status, body = http_get(url, timeout=6)
        lines.append(f"{'PASS' if ok else 'FAIL'}: {url} -> HTTP {status}; {summarize_json_or_text(body)}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)

    if failures:
        lines.append("FAIL: Backend DecoderManager prerequisite repair/check found unresolved problems.")
        for f in failures:
            lines.append(f"  - {f}")
        lines.append("")
        lines.append("Upload this file to ChatGPT.")
        rc = 1
    else:
        lines.append("PASS: Backend DecoderManager prerequisites are present and role probe works as current user.")
        lines.append("")
        lines.append("Next manual step:")
        lines.append("  Run restart_service.cmd as Administrator, then run validate_service_adsb_runtime.py again.")
        rc = 0

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'PASS' if rc == 0 else 'FAIL'}: Backend DecoderManager prereq repair/check complete.")
    print("Output saved to:")
    print(f"  {out_path}")
    print("Windows path:")
    print(f"  {str(out_path).replace('/', '\\\\')}")
    if rc == 0:
        print("Now restart the service manually with restart_service.cmd, then validate service ADS-B runtime.")
    else:
        print("Upload this .txt file.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
