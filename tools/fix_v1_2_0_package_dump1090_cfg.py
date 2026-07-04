#!/usr/bin/env python3
r"""
Finalize/fix RTL ADS-B Tracker Windows Service deployment package v1.2.0.

Fixes the current v1.2.0 package by copying the required Dump1090 config file:
  build/third_party/dump1090/Dump1090-src/dump1090.cfg
to:
  runtime/build/windows-service/RTL-ADS-B-Tracker-Windows-Service-v1.2.0/dist/third_party/dump1090/dump1090.cfg

Then rebuilds:
  runtime/build/windows-service/RTL-ADS-B-Tracker-Windows-Service-v1.2.0.zip

This is a targeted fix for a package that already built successfully except
for the missing dump1090.cfg validation failure.

Run from MSYS2 UCRT64 repo root:
  cd ~/sdrdev/RTL-Windows-ADS-B-Tracker
  python3 tools/fix_v1_2_0_package_dump1090_cfg.py
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


VERSION = "v1.2.0"
PACKAGE_NAME = f"RTL-ADS-B-Tracker-Windows-Service-{VERSION}"


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def run_cmd(args: list[str], cwd: Path, lines: list[str], timeout: int = 120) -> bool:
    lines.append("")
    lines.append(f"$ {' '.join(args)}")
    try:
        proc = subprocess.run(args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except Exception as exc:
        lines.append(f"{type(exc).__name__}: {exc}")
        return False

    lines.append(f"returncode={proc.returncode}")
    if proc.stdout.strip():
        lines.append(proc.stdout.rstrip())
    return proc.returncode == 0


def zip_package(package_dir: Path, zip_path: Path, lines: list[str]) -> bool:
    if zip_path.exists():
        old = zip_path.with_name(f"{zip_path.name}.old_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        zip_path.rename(old)
        lines.append(f"Renamed old zip: {zip_path} -> {old}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                arc = path.relative_to(package_dir.parent).as_posix()
                zf.write(path, arc)

    size = zip_path.stat().st_size
    lines.append(f"PASS: rebuilt zip: {zip_path} ({size:,} bytes)")
    return size > 1024 * 1024


def main() -> int:
    repo = Path.cwd()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = downloads_dir() / f"rtl_windows_v1_2_0_package_finalize_{stamp}.txt"
    report.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("RTL-Windows v1.2.0 deployment package finalize/fix")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append("")

    ok = True

    build_root = repo / "runtime" / "build" / "windows-service"
    package_dir = build_root / PACKAGE_NAME
    zip_path = build_root / f"{PACKAGE_NAME}.zip"

    dump_dir = package_dir / "dist" / "third_party" / "dump1090"
    target_cfg = dump_dir / "dump1090.cfg"

    source_candidates = [
        repo / "build" / "third_party" / "dump1090" / "Dump1090-src" / "dump1090.cfg",
        build_root / "RTL-ADS-B-Tracker-Windows-Service-v1.1.0" / "dist" / "third_party" / "dump1090" / "dump1090.cfg",
        build_root / "RTL-ADS-B-Tracker-Windows-Service-v0.1.0-rc1" / "dist" / "third_party" / "dump1090" / "dump1090.cfg",
    ]

    lines.append("=" * 90)
    lines.append("Input package checks")
    lines.append("=" * 90)

    if not package_dir.exists():
        lines.append(f"FAIL: package folder missing: {package_dir}")
        ok = False
    else:
        lines.append(f"PASS: package folder exists: {package_dir}")

    if not dump_dir.exists():
        lines.append(f"FAIL: dump1090 folder missing: {dump_dir}")
        ok = False
    else:
        lines.append(f"PASS: dump1090 folder exists: {dump_dir}")

    source_cfg = None
    lines.append("")
    lines.append("Source candidates:")
    for candidate in source_candidates:
        exists = candidate.exists()
        size = candidate.stat().st_size if exists else 0
        lines.append(f"  {'PASS' if exists else 'MISS'}: {candidate} size={size}")
        if source_cfg is None and exists and size > 1000:
            source_cfg = candidate

    if source_cfg is None:
        lines.append("FAIL: no usable dump1090.cfg source found.")
        ok = False

    if ok:
        lines.append("")
        lines.append("=" * 90)
        lines.append("Copy dump1090.cfg")
        lines.append("=" * 90)
        if target_cfg.exists():
            backup = target_cfg.with_name(f"dump1090.cfg.bak_finalize_{stamp}")
            shutil.copy2(target_cfg, backup)
            lines.append(f"Existing target backed up: {backup}")

        shutil.copy2(source_cfg, target_cfg)
        lines.append(f"PASS: copied {source_cfg} -> {target_cfg}")
        lines.append(f"Target size: {target_cfg.stat().st_size:,} bytes")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Package file validation")
    lines.append("=" * 90)

    required = [
        package_dir / "RTLADSBTrackerService.exe",
        package_dir / "RTLADSBTrackerService.xml",
        package_dir / "install_service.cmd",
        package_dir / "restart_service.cmd",
        package_dir / "app" / "backend" / "RTLADSBTrackerBackend.exe",
        package_dir / "web" / "index.html",
        package_dir / "web" / "app.css",
        package_dir / "web" / "app.js",
        package_dir / "dist" / "third_party" / "dump1090" / "dump1090.exe",
        package_dir / "dist" / "third_party" / "dump1090" / "dump1090.cfg",
    ]

    for path in required:
        exists = path.exists()
        size = path.stat().st_size if exists and path.is_file() else 0
        lines.append(f"{'PASS' if exists else 'FAIL'}: {path} size={size}")
        ok = ok and exists

    if (package_dir / "web" / "app.js").exists():
        app_text = (package_dir / "web" / "app.js").read_text(encoding="utf-8", errors="replace")
        checks = [
            ("package app.js has V9 fix", "__rtpV39DomAircraftMarkerDblclickInstalled" in app_text),
            ("package app.js does not include V8 logger", "__rtpV38DblclickEventLoggerInstalled" not in app_text),
        ]
        for name, passed in checks:
            lines.append(f"{'PASS' if passed else 'FAIL'}: {name}")
            ok = ok and passed

    lines.append("")
    lines.append("=" * 90)
    lines.append("Optional syntax checks")
    lines.append("=" * 90)
    if (package_dir / "web" / "app.js").exists():
        ok = run_cmd(["node", "--check", str(package_dir / "web" / "app.js")], repo, lines) and ok

    lines.append("")
    lines.append("=" * 90)
    lines.append("Rebuild zip")
    lines.append("=" * 90)
    if ok:
        ok = zip_package(package_dir, zip_path, lines) and ok
    else:
        lines.append("SKIP: zip rebuild skipped because validation failed before zip step.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Zip content validation")
    lines.append("=" * 90)
    if zip_path.exists():
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = set(zf.namelist())
            expected = [
                f"{PACKAGE_NAME}/dist/third_party/dump1090/dump1090.cfg",
                f"{PACKAGE_NAME}/dist/third_party/dump1090/dump1090.exe",
                f"{PACKAGE_NAME}/app/backend/RTLADSBTrackerBackend.exe",
                f"{PACKAGE_NAME}/web/index.html",
                f"{PACKAGE_NAME}/web/app.css",
                f"{PACKAGE_NAME}/web/app.js",
            ]
            for name in expected:
                present = name in names
                lines.append(f"{'PASS' if present else 'FAIL'}: zip contains {name}")
                ok = ok and present
        except Exception as exc:
            lines.append(f"FAIL: could not inspect zip: {type(exc).__name__}: {exc}")
            ok = False
    else:
        lines.append(f"FAIL: zip missing: {zip_path}")
        ok = False

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)
    if ok:
        lines.append("PASS: v1.2.0 deployment package finalized successfully.")
        lines.append(f"Package folder: {package_dir}")
        lines.append(f"Package zip:    {zip_path}")
    else:
        lines.append("FAIL: v1.2.0 package finalize failed. Upload this report to ChatGPT.")

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(("PASS" if ok else "FAIL") + ": v1.2.0 package finalize complete.")
    print("Report saved to:")
    print(f"  {report}")
    print("Windows path:")
    print(f"  {str(report).replace('/', '\\\\')}")
    if ok:
        print("Package zip:")
        print(f"  {zip_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
