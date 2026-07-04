#!/usr/bin/env python3
r"""
Prepare the existing Windows service package with the V2 patched web UI.

Run from MSYS2 UCRT64 repo root:
  python3 tools/prepare_v2_service_package.py

What it does:
  - Finds the existing runtime/build/windows-service/RTL-ADS-B-Tracker-Windows-Service-* package
  - Copies repo web/app.js into the package web/app.js
  - Backs up the old package web/app.js
  - Validates that the package copy contains the aircraft double-click fix
  - Writes a report to C:/Users/jim/Downloads
  - Prints the exact install_service.cmd path to run manually from Windows

It does NOT call cmd.exe, PowerShell, or Windows service commands.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_MARKERS = [
    "function rtpV33StopAircraftMarkerDblclick",
    "function rtpV33OpenAircraftDetailsFromMap",
    "function rtpV33BindAircraftMarkerDblclick",
    'addEventListener("dblclick"',
    "rtpV33BindAircraftMarkerDblclick(m,hex,a)",
]


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def find_service_packages(repo: Path) -> list[Path]:
    root = repo / "runtime" / "build" / "windows-service"
    if not root.exists():
        return []

    packages = []
    for p in root.glob("RTL-ADS-B-Tracker-Windows-Service-*"):
        if p.is_dir() and (p / "install_service.cmd").exists():
            packages.append(p)

    packages.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return packages


def find_package_app_js(package: Path) -> list[Path]:
    candidates = [
        package / "app" / "web" / "app.js",
        package / "web" / "app.js",
    ]
    found = [p for p in candidates if p.exists()]

    if found:
        return found

    # Fallback search under package, avoiding large build caches.
    for p in package.rglob("app.js"):
        parts = {part.lower() for part in p.parts}
        if "web" in parts and "__pycache__" not in parts:
            found.append(p)

    # Prefer paths under app/web.
    found.sort(key=lambda p: (0 if "app" in [x.lower() for x in p.parts] and "web" in [x.lower() for x in p.parts] else 1, len(p.parts)))
    return found


def validate_markers(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="replace")
    missing = [marker for marker in REQUIRED_MARKERS if marker not in src]
    if '.on("dblclick",event=>rtpV33OpenAircraftDetailsFromMap(hex,a,event))' in src:
        missing.append("old inline dblclick hook is still present")
    return missing


def node_check(path: Path) -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return True, "WARN: node not found; skipped syntax check."

    proc = subprocess.run(
        [node, "--check", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode == 0:
        return True, "PASS: node --check package web/app.js"
    return False, "FAIL: node --check package web/app.js\n" + proc.stdout


def main() -> int:
    repo = Path.cwd()
    downloads = downloads_dir()
    downloads.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = downloads / f"rtl_windows_v2_service_prepare_{stamp}.txt"

    lines = []
    lines.append("RTL-Windows V2 service package preparation")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append("")

    src_app = repo / "web" / "app.js"
    if not src_app.exists():
        lines.append("FAIL: repo web/app.js was not found. Run from repo root.")
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: repo web/app.js not found. Report: {report}")
        return 2

    missing_dev = validate_markers(src_app)
    if missing_dev:
        lines.append("FAIL: development web/app.js does not contain the V2 marker double-click patch.")
        for item in missing_dev:
            lines.append(f"  - missing/problem: {item}")
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: development web/app.js is not patched. Report: {report}")
        return 3

    packages = find_service_packages(repo)
    lines.append("Service package discovery:")
    if not packages:
        lines.append("FAIL: No existing Windows service package with install_service.cmd was found.")
        lines.append("Expected under: runtime/build/windows-service/RTL-ADS-B-Tracker-Windows-Service-*")
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: no service package found. Report: {report}")
        return 4

    for i, pkg in enumerate(packages[:5], 1):
        lines.append(f"  {i}. {pkg}")

    package = packages[0]
    lines.append("")
    lines.append(f"Selected package: {package}")

    app_js_targets = find_package_app_js(package)
    lines.append("")
    lines.append("Package web/app.js target discovery:")
    if not app_js_targets:
        lines.append("FAIL: Could not find package web/app.js inside selected package.")
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: package web/app.js not found. Report: {report}")
        return 5

    for target in app_js_targets:
        lines.append(f"  - {target}")

    target = app_js_targets[0]
    backup = target.with_name(f"app.js.bak_before_v2_{stamp}")
    shutil.copy2(target, backup)
    shutil.copy2(src_app, target)

    lines.append("")
    lines.append(f"Copied patched web/app.js to: {target}")
    lines.append(f"Backup of package app.js: {backup}")

    missing_pkg = validate_markers(target)
    if missing_pkg:
        lines.append("")
        lines.append("FAIL: package web/app.js validation failed after copy.")
        for item in missing_pkg:
            lines.append(f"  - missing/problem: {item}")
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: package validation failed. Report: {report}")
        return 6

    ok_node, node_msg = node_check(target)
    lines.append("")
    lines.append(node_msg)
    if not ok_node:
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: package JavaScript syntax check failed. Report: {report}")
        return 7

    install_cmd = package / "install_service.cmd"
    status_cmd = package / "status_service.cmd"
    open_cmd = package / "open_tracker.cmd"

    lines.append("")
    lines.append("PASS: Existing Windows service package now contains the V2 patched web UI.")
    lines.append("")
    lines.append("Manual Windows step:")
    lines.append("  Run this file as Administrator from Windows, not from MSYS2:")
    lines.append(f"  {install_cmd}")
    lines.append("")
    lines.append("Optional Windows helper files in the same folder:")
    if status_cmd.exists():
        lines.append(f"  Status: {status_cmd}")
    if open_cmd.exists():
        lines.append(f"  Open UI: {open_cmd}")
    lines.append("")
    lines.append("After install/start:")
    lines.append("  Open http://localhost:8090")
    lines.append("  Press Ctrl+F5")
    lines.append("  Confirm ADS-B aircraft data appears")
    lines.append("  Double-click an airplane icon")
    lines.append("")
    lines.append("Expected runtime result:")
    lines.append("  PASS if the aircraft dialog opens and the map does not zoom.")
    lines.append("  FAIL if the map zooms or no dialog opens.")

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("PASS: Existing Windows service package now contains the V2 patched web UI.")
    print("")
    print("Report saved to:")
    print(f"  {report}")
    print("")
    print("Run this manually from Windows as Administrator:")
    print(f"  {install_cmd}")
    print("")
    print("Then open http://localhost:8090, press Ctrl+F5, and test airplane double-click.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
