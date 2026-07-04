#!/usr/bin/env python3
"""
Discover RTP/RTL-Windows development full-stack paths.

Run from MSYS2 UCRT64 repo root:
  python3 tools/discover_v2_dev_fullstack.py

This script returns clear PASS/FAIL sections and uploadable output:
  - Which backend is currently serving port 8090, if reachable
  - Which aircraft/API endpoints the UI actually references
  - Which referenced endpoints respond
  - Which decoder executables exist, including build/dist/release folders
  - Which scripts appear to build/start/test the ADS-B decoder
  - Which service packaging files mention the runtime command

It does not use grep/diff commands.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


PORT = 8090
BASE_URLS = [
    f"http://127.0.0.1:{PORT}",
    f"http://localhost:{PORT}",
]

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "test_output",
}

COMMON_ENDPOINTS = [
    "/api/status",
    "/api/aircraft",
    "/api/aircraft.json",
    "/api/adsb",
    "/api/adsb/aircraft",
    "/api/adsb/aircraft.json",
    "/api/readsb/aircraft",
    "/api/readsb/aircraft.json",
    "/data/aircraft.json",
    "/aircraft.json",
    "/readsb/aircraft.json",
    "/dump1090/data/aircraft.json",
    "/tar1090/data/aircraft.json",
]


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


def http_probe(url: str, timeout: int = 3) -> tuple[bool, str, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(800).decode("utf-8", errors="replace")
            return True, f"HTTP {response.status}", body
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read(800).decode("utf-8", errors="replace")
        except Exception:
            pass
        return False, f"HTTP {exc.code}", body
    except URLError as exc:
        return False, f"URL error: {exc.reason}", ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", ""


def summarize_jsonish(body: str) -> str:
    if not body:
        return ""
    try:
        payload = json.loads(body)
    except Exception:
        one = " ".join(body.split())
        return one[:220]
    if isinstance(payload, dict):
        if isinstance(payload.get("aircraft"), list):
            return f"JSON aircraft_count={len(payload['aircraft'])}"
        keys = ", ".join(list(payload.keys())[:12])
        err = payload.get("error") or payload.get("message") or payload.get("detail")
        if err:
            return f"JSON error={err!r}; keys={keys}"
        return f"JSON keys={keys}"
    if isinstance(payload, list):
        return f"JSON list_count={len(payload)}"
    return f"JSON {type(payload).__name__}"


def discover_ui_endpoints(repo: Path) -> list[str]:
    endpoints: set[str] = set(COMMON_ENDPOINTS)

    for rel in ["web/app.js", "web/index.html"]:
        text = read_text(repo / rel)
        if not text:
            continue

        # Direct string paths used in fetch/XHR/EventSource.
        for m in re.finditer(r"""['"](/(?:api|data|readsb|dump1090|tar1090|aircraft)[^'"]*)['"]""", text):
            raw = m.group(1)
            # Strip string concatenation fragments and query-only dynamic tails.
            raw = raw.split("${", 1)[0]
            if raw and not raw.endswith("+"):
                endpoints.add(raw)

        # Fetch calls with simple template strings.
        for m in re.finditer(r"""fetch\s*\(\s*`([^`]+)`""", text):
            raw = m.group(1)
            raw = raw.split("${", 1)[0]
            if raw.startswith("/"):
                endpoints.add(raw)

    cleaned = []
    for ep in sorted(endpoints):
        if len(ep) > 120:
            continue
        if ep.endswith("/"):
            ep = ep[:-1]
        if ep and ep not in cleaned:
            cleaned.append(ep)
    return cleaned


def find_executables(repo: Path) -> list[str]:
    terms = ("dump1090", "readsb", "rtl_adsb", "rtl-adsb", "adsb", "1090")
    found: list[str] = []
    for path in repo.rglob("*"):
        if path_excluded(path, repo) or not path.is_file():
            continue
        lower = path.name.lower()
        rel = path.relative_to(repo).as_posix()
        if path.suffix.lower() in {".exe", ".com"} and any(t in rel.lower() for t in terms):
            found.append(rel)
    return sorted(set(found))[:80]


def find_scripts(repo: Path) -> list[tuple[str, str]]:
    terms = ("dump1090", "readsb", "rtl_adsb", "rtl-adsb", "adsb", "1090")
    skip_terms = ("patch_", "validate_", "diagnose_", "discover_")
    found: list[tuple[str, str]] = []

    for path in repo.rglob("*"):
        if path_excluded(path, repo) or not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".sh", ".bat", ".cmd", ".ps1"}:
            continue
        rel = path.relative_to(repo).as_posix()
        lower = rel.lower()
        if any(skip in lower for skip in skip_terms):
            continue
        text = read_text(path)
        haystack = lower + "\n" + text.lower()
        if not any(t in haystack for t in terms):
            continue

        purpose = []
        if "dump1090" in haystack:
            purpose.append("dump1090")
        if "readsb" in haystack:
            purpose.append("readsb")
        if "rtl" in haystack:
            purpose.append("rtl")
        if "30005" in haystack or "30003" in haystack:
            purpose.append("network ports")
        if "aircraft.json" in haystack:
            purpose.append("aircraft.json")
        if "build" in lower or "gcc" in haystack or "make" in haystack:
            purpose.append("build")
        if "test" in lower:
            purpose.append("test")

        found.append((rel, ", ".join(purpose) if purpose else "ADS-B-related"))
    return sorted(set(found))[:80]


def find_service_files(repo: Path) -> list[tuple[str, list[str]]]:
    interesting_ext = {".xml", ".json", ".yml", ".yaml", ".ini", ".cfg", ".service", ".txt", ".md", ".py", ".sh", ".bat", ".cmd"}
    found: list[tuple[str, list[str]]] = []
    needles = ("winsw", "service", "programdata", "dump1090", "readsb", "aircraft.json", "30005", "30003")

    for path in repo.rglob("*"):
        if path_excluded(path, repo) or not path.is_file():
            continue
        if path.suffix.lower() not in interesting_ext:
            continue
        rel = path.relative_to(repo).as_posix()
        text = read_text(path)
        lower = (rel + "\n" + text).lower()
        if not any(n in lower for n in needles):
            continue

        lines = []
        for line in text.splitlines():
            ll = line.lower()
            if any(n in ll for n in needles):
                clean = line.strip()
                if clean and len(clean) <= 240:
                    lines.append(clean)
            if len(lines) >= 8:
                break
        if lines:
            found.append((rel, lines))
    return found[:80]


def main() -> int:
    repo = Path.cwd()
    print("RTP/RTL-Windows V2 development full-stack discovery")
    print(f"Repo: {repo}")

    if not (repo / "web" / "app.js").exists():
        print("")
        print("FAIL: web/app.js was not found.")
        print("Run from the repository root:")
        print("  cd ~/sdrdev/RTL-Windows-ADS-B-Tracker")
        return 2

    print("")
    print("1) Backend reachability:")
    reachable_base = None
    for base in BASE_URLS:
        ok, status, body = http_probe(base + "/", timeout=3)
        print(f"  {'PASS' if ok else 'FAIL'}: {base}/ -> {status}; {summarize_jsonish(body)}")
        if ok and reachable_base is None:
            reachable_base = base

    if reachable_base is None:
        print("")
        print("FAIL: No development backend is reachable on port 8090.")
        print("Start the dev backend first, then rerun this script.")
        return 1

    print("")
    print("2) UI-referenced and common aircraft/API endpoints:")
    endpoints = discover_ui_endpoints(repo)
    responding = []
    aircraft_like = []
    for ep in endpoints:
        ok, status, body = http_probe(reachable_base + ep, timeout=4)
        summary = summarize_jsonish(body)
        label = "PASS" if ok else "FAIL"
        print(f"  {label}: {ep} -> {status}; {summary}")
        if ok:
            responding.append(ep)
        if ok and ("aircraft_count=" in summary or "aircraft" in summary.lower()):
            aircraft_like.append((ep, summary))

    print("")
    if aircraft_like:
        print("PASS: At least one aircraft-like endpoint responded:")
        for ep, summary in aircraft_like:
            print(f"  - {ep}: {summary}")
    else:
        print("FAIL: No responding endpoint returned aircraft-like JSON.")

    print("")
    print("3) Decoder executable candidates in repo, including build/dist/release:")
    executables = find_executables(repo)
    if executables:
        print("PASS: decoder executable candidates found:")
        for rel in executables:
            print(f"  - {rel}")
    else:
        print("FAIL: no obvious decoder executable candidates were found in the repo.")

    print("")
    print("4) ADS-B build/start/test script candidates:")
    scripts = find_scripts(repo)
    if scripts:
        print("PASS: ADS-B-related scripts found:")
        for rel, purpose in scripts:
            print(f"  - {rel} [{purpose}]")
    else:
        print("FAIL: no ADS-B-related scripts were found.")

    print("")
    print("5) Service/package configuration clues:")
    service_files = find_service_files(repo)
    if service_files:
        print("PASS: service/package clues found:")
        for rel, lines in service_files:
            print(f"  - {rel}")
            for line in lines:
                print(f"      {line}")
    else:
        print("FAIL: no service/package configuration clues found.")

    print("")
    if aircraft_like and executables:
        print("PASS: Discovery found both aircraft API clues and decoder executable candidates.")
        print("Next step: use this output to create a full-stack dev launcher.")
        return 0

    print("FAIL: Discovery did not find enough information to start the full ADS-B stack automatically.")
    print("")
    print("Upload/paste this full output back to ChatGPT.")
    print("It contains the concrete endpoints, executables, and service/package clues needed for the next patch.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
