#!/usr/bin/env python3
r"""
Deep diagnose RTLADSBTracker service backend launch path.

Run from MSYS2 UCRT64 repo root while the Windows service is running:
  python3 tools/diagnose_service_backend_launch.py

Output:
  C:/Users/jim/Downloads/rtl_windows_service_backend_launch_YYYYMMDD_HHMMSS.txt

What it captures:
  - Service wrapper XML/config files.
  - Recent service/backend logs.
  - Backend source route list and Dump1090/readsb launch snippets.
  - Packaged runtime file layout.
  - Safe backend endpoint probes.
  - Current port status.

It does not call cmd.exe, PowerShell, or WSL.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


SERVICE_ID = "RTLADSBTracker"
BASE = "http://127.0.0.1:8090"

SAFE_ENDPOINTS = [
    "/api/status",
    "/api/aircraft.json",
    "/api/airband/scan/status",
    "/api/airband/test/status",
    "/api/diagnostics/airlabs/status",
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


def get_service_imagepath() -> tuple[str | None, list[str]]:
    lines: list[str] = []
    image = None

    try:
        import winreg  # type: ignore
        key_path = rf"SYSTEM\CurrentControlSet\Services\{SERVICE_ID}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "ImagePath")
            image = str(value)
            lines.append(f"PASS: registry ImagePath: {image}")
    except Exception as exc:
        lines.append(f"WARN: registry ImagePath read failed: {type(exc).__name__}: {exc}")

    rc, out = run_direct(["sc.exe", "qc", SERVICE_ID], timeout=8)
    lines.append(f"sc.exe qc rc={rc}")
    lines.append(out.strip())
    if not image:
        for line in out.splitlines():
            if "BINARY_PATH_NAME" in line:
                image = line.split(":", 1)[1].strip()

    return image, lines


def parse_exe_from_imagepath(imagepath: str | None) -> Path | None:
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


def read_text(path: Path, max_chars: int = 60000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[read failed: {type(exc).__name__}: {exc}]"
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


def stat_line(path: Path) -> str:
    if not path.exists():
        return f"FAIL missing: {path}"
    try:
        st = path.stat()
        return f"PASS exists: {path} size={st.st_size} modified={dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')}"
    except Exception:
        return f"PASS exists: {path}"


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


def summarize_body(body: str) -> str:
    try:
        payload = json.loads(body)
    except Exception:
        return "non-JSON: " + " ".join(body.split())[:400]
    if isinstance(payload, dict):
        if isinstance(payload.get("aircraft"), list):
            return f"aircraft_count={len(payload['aircraft'])}, messages={payload.get('messages', 'unknown')}, keys={','.join(list(payload.keys())[:12])}"
        err = payload.get("error") or payload.get("message") or payload.get("detail")
        if err:
            return f"error={err!r}, keys={','.join(list(payload.keys())[:12])}"
        compact = {k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool)) or v is None}
        return json.dumps(compact, ensure_ascii=True)[:1000]
    return f"JSON {type(payload).__name__}"


def list_recent_files(root: Path, patterns: list[str], limit: int = 80) -> list[Path]:
    found: list[Path] = []
    if not root.exists():
        return []
    for pat in patterns:
        try:
            found.extend([p for p in root.rglob(pat) if p.is_file()])
        except Exception:
            pass
    found = list(dict.fromkeys(found))
    found.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return found[:limit]


def extract_routes(source: str) -> list[str]:
    routes: list[str] = []
    patterns = [
        r"@app\.route\(\s*['\"]([^'\"]+)['\"]",
        r"@APP\.route\(\s*['\"]([^'\"]+)['\"]",
        r"add_url_rule\(\s*['\"]([^'\"]+)['\"]",
    ]
    for pat in patterns:
        for m in re.finditer(pat, source):
            routes.append(m.group(1))
    return sorted(set(routes))


def extract_snippets(source: str, keywords: list[str], context: int = 8) -> list[str]:
    lines = source.splitlines()
    hits: list[str] = []
    for i, line in enumerate(lines):
        ll = line.lower()
        if any(k.lower() in ll for k in keywords):
            start = max(0, i - context)
            end = min(len(lines), i + context + 1)
            snippet = []
            snippet.append(f"--- source lines {start+1}-{end} around keyword hit line {i+1} ---")
            for j in range(start, end):
                snippet.append(f"{j+1:5d}: {lines[j]}")
            hits.append("\n".join(snippet))
            if len(hits) >= 25:
                break
    return hits


def source_candidates(repo: Path, service_root: Path | None) -> list[Path]:
    candidates = [
        repo / "src" / "backend" / "rtl_windows_pi_port_backend.py",
        repo / "src" / "backend" / "rtl_windows_backend.py",
    ]
    if service_root:
        candidates.extend([
            service_root / "app" / "backend" / "rtl_windows_pi_port_backend.py",
            service_root / "app" / "backend" / "rtl_windows_backend.py",
        ])
        try:
            candidates.extend([p for p in service_root.rglob("*.py") if "backend" in p.name.lower()])
        except Exception:
            pass
    result: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p).lower()
        if key not in seen and p.exists():
            result.append(p)
            seen.add(key)
    return result


def find_xml_configs(service_root: Path) -> list[Path]:
    candidates = [
        service_root / "RTLADSBTrackerService.xml",
        service_root / "RTLADSBTracker.xml",
    ]
    try:
        candidates.extend([p for p in service_root.glob("*.xml") if p.is_file()])
    except Exception:
        pass
    result = []
    seen = set()
    for p in candidates:
        key = str(p).lower()
        if p.exists() and key not in seen:
            result.append(p)
            seen.add(key)
    return result


def main() -> int:
    repo = Path.cwd()
    downloads = downloads_dir()
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = downloads / f"rtl_windows_service_backend_launch_{stamp}.txt"

    lines: list[str] = []
    lines.append("RTL-Windows / RTP-Windows service backend launch diagnosis")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append("")

    image, service_lines = get_service_imagepath()
    service_exe = parse_exe_from_imagepath(image)
    service_root = service_exe.parent if service_exe else None

    lines.append("=" * 90)
    lines.append("Service configuration")
    lines.append("=" * 90)
    lines.extend(service_lines)
    lines.append(f"Parsed service executable: {service_exe}")
    lines.append(f"Parsed service root: {service_root}")
    if service_exe:
        lines.append(stat_line(service_exe))

    lines.append("")
    lines.append("=" * 90)
    lines.append("Service wrapper XML/config files")
    lines.append("=" * 90)
    if service_root:
        xmls = find_xml_configs(service_root)
        if xmls:
            for xml in xmls:
                lines.append(stat_line(xml))
                lines.append("----- file content begin -----")
                lines.append(read_text(xml, max_chars=20000))
                lines.append("----- file content end -----")
        else:
            lines.append("FAIL: no XML config files found beside service wrapper.")
    else:
        lines.append("FAIL: service root unknown.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Runtime layout checks")
    lines.append("=" * 90)
    if service_root:
        paths = [
            service_root / "RTLADSBTrackerService.exe",
            service_root / "app" / "backend" / "RTLADSBTrackerBackend.exe",
            service_root / "app" / "backend" / "rtl_windows_pi_port_backend.py",
            service_root / "app" / "backend" / "rtl_windows_backend.py",
            service_root / "web" / "app.js",
            service_root / "app" / "web" / "app.js",
            service_root / "dist" / "third_party" / "dump1090" / "dump1090.exe",
            service_root / "dist" / "third_party" / "dump1090" / "dump1090.cfg",
            service_root / "dist" / "third_party" / "dump1090" / "librtlsdr.dll",
            service_root / "dist" / "third_party" / "dump1090" / "libusb-1.0.dll",
            service_root / "dist" / "third_party" / "dump1090" / "libwinpthread-1.dll",
            service_root / "bin" / "librtlsdr.dll",
            service_root / "bin" / "libusb-1.0.dll",
            service_root / "bin" / "libwinpthread-1.dll",
        ]
        for p in paths:
            lines.append(stat_line(p))
    else:
        lines.append("FAIL: service root unknown.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Port checks")
    lines.append("=" * 90)
    for port, label in PORTS:
        lines.append(f"{'PASS' if port_open(port) else 'FAIL'}: port {port} {label}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Safe endpoint checks")
    lines.append("=" * 90)
    for ep in SAFE_ENDPOINTS:
        ok, status, body = http_get(BASE + ep, timeout=8)
        lines.append(f"{'PASS' if ok else 'FAIL'}: {ep} -> HTTP {status}; {summarize_body(body)}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Recent service/backend logs")
    lines.append("=" * 90)
    log_roots = []
    if service_root:
        log_roots.extend([
            service_root,
            service_root / "logs",
            service_root / "app",
            service_root / "app" / "logs",
            service_root / "runtime",
            service_root / "runtime" / "logs",
        ])
    log_patterns = ["*.log", "*.out", "*.err", "*.txt"]
    log_files: list[Path] = []
    for root in log_roots:
        log_files.extend(list_recent_files(root, log_patterns, limit=30))
    log_files = list(dict.fromkeys(log_files))
    log_files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

    if not log_files:
        lines.append("WARN: no log files found under service runtime roots.")
    else:
        for log in log_files[:30]:
            lines.append(stat_line(log))
            text = read_text(log, max_chars=20000)
            # Keep only useful tail and avoid embedding huge HTML/JS.
            lines.append("----- log tail begin -----")
            lines.append(text)
            lines.append("----- log tail end -----")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Backend source route and launch snippets")
    lines.append("=" * 90)
    srcs = source_candidates(repo, service_root)
    if not srcs:
        lines.append("FAIL: no backend source candidates found in repo/service runtime.")
    else:
        for src in srcs:
            lines.append(stat_line(src))
            text = read_text(src, max_chars=300000)
            routes = extract_routes(text)
            if routes:
                lines.append("Routes:")
                for r in routes:
                    if any(k in r.lower() for k in ("aircraft", "adsb", "readsb", "decoder", "status", "dump1090", "airband", "noaa")):
                        lines.append(f"  - {r}")
            else:
                lines.append("No Flask route decorators found in this source.")

            lines.append("")
            lines.append("Snippets around Dump1090/readsb/aircraft/decoder/process keywords:")
            snippets = extract_snippets(
                text,
                [
                    "dump1090",
                    "readsb",
                    "aircraft.json",
                    "subprocess",
                    "Popen",
                    "decoder",
                    "adsb",
                    "readsb_json",
                    "30003",
                    "8080",
                ],
                context=7,
            )
            if snippets:
                for snip in snippets:
                    lines.append(snip)
            else:
                lines.append("No snippets found.")
            lines.append("")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall finding")
    lines.append("=" * 90)
    lines.append("This report is diagnostic only.")
    lines.append("Upload it to ChatGPT if /api/aircraft.json still says ADS-B decoder is not running.")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("PASS: Service backend launch diagnosis captured.")
    print("Output saved to:")
    print(f"  {out_path}")
    print("Windows path:")
    print(f"  {str(out_path).replace('/', '\\\\')}")
    print("Upload this .txt file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
