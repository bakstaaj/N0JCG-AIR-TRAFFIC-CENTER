#!/usr/bin/env python3
r"""
Safe V2 full-stack discovery for RTL-Windows / RTP-Windows.

Run from MSYS2 UCRT64 repo root:
  python3 tools/discover_v2_fullstack_safe.py

Output:
  C:/Users/jim/Downloads/rtl_windows_v2_fullstack_discovery_YYYYMMDD_HHMMSS.txt

This version:
  - writes all output to Downloads using UTF-8
  - avoids audio/capture endpoints
  - avoids endpoint probes that can start hardware/audio work
  - focuses on finding the installed-service/full-stack launcher commands
  - returns PASS/FAIL on console and gives the exact output file path
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


PORT = 8090
BASE_URLS = [
    f"http://127.0.0.1:{PORT}",
    f"http://localhost:{PORT}",
]

SAFE_ENDPOINTS = [
    "/api/status",
    "/api/aircraft.json",
    "/api/airband/scan/status",
    "/api/airband/test/status",
    "/api/diagnostics/airlabs/status",
]

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "test_output",
}


def windows_downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def path_excluded(path: Path, repo: Path) -> bool:
    try:
        rel = path.relative_to(repo)
    except ValueError:
        return True
    return any(part in EXCLUDE_DIRS for part in rel.parts)


def http_probe(url: str, timeout: int = 4) -> tuple[bool, str, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(1200).decode("utf-8", errors="replace")
            return True, f"HTTP {response.status}", body
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read(1200).decode("utf-8", errors="replace")
        except Exception:
            pass
        return False, f"HTTP {exc.code}", body
    except URLError as exc:
        return False, f"URL error: {exc.reason}", ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", ""


def summarize_body(body: str) -> str:
    if not body:
        return ""
    try:
        payload = json.loads(body)
    except Exception:
        return " ".join(body.split())[:300]
    if isinstance(payload, dict):
        if isinstance(payload.get("aircraft"), list):
            return f"JSON aircraft_count={len(payload['aircraft'])}"
        keys = ", ".join(list(payload.keys())[:16])
        err = payload.get("error") or payload.get("message") or payload.get("detail")
        if err:
            return f"JSON error={err!r}; keys={keys}"
        compact = {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                compact[key] = value
        if compact:
            return json.dumps(compact, ensure_ascii=True)[:500]
        return f"JSON keys={keys}"
    if isinstance(payload, list):
        return f"JSON list_count={len(payload)}"
    return f"JSON {type(payload).__name__}"


def port_open(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.75)
    try:
        sock.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        sock.close()


def find_files(repo: Path) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "decoder_executables": [],
        "service_install_scripts": [],
        "service_package_scripts": [],
        "dev_or_run_scripts": [],
        "adsb_build_test_scripts": [],
        "config_files": [],
    }

    for path in repo.rglob("*"):
        if path_excluded(path, repo) or not path.is_file():
            continue

        rel = path.relative_to(repo).as_posix()
        lower = rel.lower()
        suffix = path.suffix.lower()
        text = ""
        if suffix in {".py", ".sh", ".bat", ".cmd", ".ps1", ".xml", ".json", ".yml", ".yaml", ".ini", ".cfg", ".md", ".txt"}:
            text = read_text(path).lower()

        haystack = lower + "\n" + text

        if suffix in {".exe", ".com"} and any(t in lower for t in ("dump1090", "readsb", "rtl_adsb", "adsb", "1090")):
            groups["decoder_executables"].append(rel)

        if suffix in {".py", ".sh", ".bat", ".cmd", ".ps1"}:
            if any(t in haystack for t in ("install", "uninstall", "winsw", "service")) and any(t in haystack for t in ("rtl", "ads-b", "adsb", "tracker")):
                groups["service_install_scripts"].append(rel)
            if any(t in haystack for t in ("package", "pyinstaller", "winsw", "release")) and any(t in haystack for t in ("service", "rtl", "ads-b", "adsb")):
                groups["service_package_scripts"].append(rel)
            if any(t in haystack for t in ("run", "start", "serve", "flask", "waitress", "uvicorn")) and any(t in haystack for t in ("8090", "api/status", "web", "ads-b", "adsb")):
                groups["dev_or_run_scripts"].append(rel)
            if any(t in haystack for t in ("dump1090", "readsb", "rtl_adsb", "1090", "aircraft.json")):
                if not any(skip in lower for skip in ("patch_", "validate_", "diagnose_", "discover_", "capture_")):
                    groups["adsb_build_test_scripts"].append(rel)

        if suffix in {".xml", ".json", ".yml", ".yaml", ".ini", ".cfg", ".txt", ".md"}:
            if any(t in haystack for t in ("winsw", "service", "programdata", "dump1090", "readsb", "aircraft.json", "30005", "30003")):
                groups["config_files"].append(rel)

    for key in groups:
        groups[key] = sorted(set(groups[key]))[:100]
    return groups


def extract_clue_lines(repo: Path, rels: list[str]) -> list[str]:
    needles = (
        "winsw", "service", "programdata", "pyinstaller", "dump1090", "readsb",
        "rtl_adsb", "aircraft.json", "30005", "30003", "8090", "waitress",
        "flask", "uvicorn", "subprocess", "popen", "create_process"
    )
    output: list[str] = []
    for rel in rels[:40]:
        path = repo / rel
        text = read_text(path)
        lines = []
        for i, line in enumerate(text.splitlines(), 1):
            ll = line.lower()
            if any(n in ll for n in needles):
                clean = line.strip()
                if clean:
                    lines.append(f"L{i}: {clean[:220]}")
            if len(lines) >= 14:
                break
        if lines:
            output.append(f"- {rel}")
            output.extend([f"    {line}" for line in lines])
    return output


def run_existing_test(repo: Path, rel: str, timeout: int = 45) -> tuple[int, str]:
    path = repo / rel
    if not path.exists():
        return 127, f"SKIP: {rel} not found."
    try:
        proc = subprocess.run(
            ["bash", rel] if rel.endswith(".sh") else [sys.executable, rel],
            cwd=str(repo),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout[-4000:]
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        return 124, out[-4000:] + f"\nFAIL: {rel} timed out after {timeout}s."
    except Exception as exc:
        return 1, f"FAIL: Could not run {rel}: {type(exc).__name__}: {exc}"


def main() -> int:
    repo = Path.cwd()
    downloads = windows_downloads_dir()
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = downloads / f"rtl_windows_v2_fullstack_discovery_{stamp}.txt"

    lines: list[str] = []
    lines.append("RTL-Windows / RTP-Windows V2 safe full-stack discovery")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append(f"Downloads target: {downloads}")
    lines.append("")

    if not (repo / "web" / "app.js").exists():
        lines.append("FAIL: web/app.js not found. Run from repo root.")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: output saved to {out_path}")
        return 2

    lines.append("=" * 90)
    lines.append("Backend safe endpoint checks")
    lines.append("=" * 90)
    reachable_base = None
    for base in BASE_URLS:
        ok, status, body = http_probe(base + "/", timeout=3)
        lines.append(f"{'PASS' if ok else 'FAIL'}: {base}/ -> {status}; {summarize_body(body)}")
        if ok and reachable_base is None:
            reachable_base = base

    if reachable_base:
        for ep in SAFE_ENDPOINTS:
            ok, status, body = http_probe(reachable_base + ep, timeout=5)
            lines.append(f"{'PASS' if ok else 'FAIL'}: {ep} -> {status}; {summarize_body(body)}")
    else:
        lines.append("FAIL: no backend reachable on port 8090")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Common ADS-B decoder port checks")
    lines.append("=" * 90)
    for port, label in [(30003, "SBS/BaseStation"), (30005, "Beast output"), (30001, "raw input"), (30002, "raw output"), (30104, "Beast input")]:
        lines.append(f"{'PASS' if port_open(port) else 'FAIL'}: port {port} {label}")

    groups = find_files(repo)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Discovered files")
    lines.append("=" * 90)
    for key, values in groups.items():
        lines.append(f"{key}: {'PASS' if values else 'FAIL'} count={len(values)}")
        for value in values[:80]:
            lines.append(f"  - {value}")
        lines.append("")

    clue_rels = []
    for key in ("service_install_scripts", "service_package_scripts", "dev_or_run_scripts", "adsb_build_test_scripts", "config_files"):
        clue_rels.extend(groups[key])

    lines.append("=" * 90)
    lines.append("Command/config clue lines")
    lines.append("=" * 90)
    clue_lines = extract_clue_lines(repo, sorted(set(clue_rels)))
    if clue_lines:
        lines.extend(clue_lines)
    else:
        lines.append("FAIL: no command/config clue lines found.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Existing ADS-B test script quick runs")
    lines.append("=" * 90)
    for rel in ["tools/test_backend_adsb_api.sh", "tools/test_dump1090_adsb_json.sh"]:
        rc, output = run_existing_test(repo, rel, timeout=45)
        lines.append(f"{rel}: {'PASS' if rc == 0 else 'FAIL'} rc={rc}")
        lines.append(output.rstrip())
        lines.append("")

    # Overall guidance
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)
    has_decoder = bool(groups["decoder_executables"])
    has_build = any("build_dump1090_windows" in x for x in groups["adsb_build_test_scripts"])
    has_service_clues = bool(groups["service_install_scripts"] or groups["service_package_scripts"] or groups["config_files"])

    if has_decoder:
        lines.append("PASS: decoder executable exists in repo.")
    else:
        lines.append("FAIL: decoder executable was not found in repo.")

    if has_build:
        lines.append("PASS: build_dump1090_windows script exists.")
    else:
        lines.append("FAIL: build_dump1090_windows script was not found.")

    if has_service_clues:
        lines.append("PASS: service/package clues found.")
    else:
        lines.append("FAIL: no service/package clues found.")

    if has_decoder or has_build or has_service_clues:
        lines.append("NEXT: Upload this file to ChatGPT so the correct full-stack dev/start or rebuild instructions can be generated.")
        rc = 0
    else:
        lines.append("NEXT: Upload this file; repository may be missing decoder/service artifacts after uninstall.")
        rc = 1

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'PASS' if rc == 0 else 'FAIL'}: Safe full-stack discovery complete.")
    print("Output saved to:")
    print(f"  {out_path}")
    print("Windows path:")
    print(f"  {str(out_path).replace('/', '\\\\')}")
    print("Upload this .txt file to ChatGPT.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
