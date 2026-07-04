#!/usr/bin/env python3
r"""
Build RTL ADS-B Tracker Windows Service deployment package v1.2.0.

This script is intended to run from MSYS2 UCRT64 repo root:

  cd ~/sdrdev/RTL-Windows-ADS-B-Tracker
  python3 tools/build_v1_2_0_deployment_package.py

What it does:
  - validates the v1.2.0 source cleanup state
  - uses the existing v1.1.0 service package folder as a layout template
  - stages a new v1.2.0 service package folder
  - rebuilds app/backend/RTLADSBTrackerBackend.exe from current source
  - copies current web/index.html, web/app.css, web/app.js
  - preserves the existing WinSW service wrapper, scripts, native binaries, and third-party runtime files
  - writes RELEASE_NOTES_v1.2.0.txt into the package
  - creates RTL-ADS-B-Tracker-Windows-Service-v1.2.0.zip
  - writes a detailed report to C:/Users/jim/Downloads

Notes:
  - This does not install or restart the Windows service.
  - Stop local dev backend/service before running if any package files are locked.
  - Prefer native Windows Python launcher `py -3` for PyInstaller, but the script
    can fall back to MSYS2 python3 if needed.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


VERSION = "v1.2.0"
PACKAGE_BASENAME = "RTL-ADS-B-Tracker-Windows-Service"
TEMPLATE_VERSION = "v1.1.0"
BACKEND_EXE = "RTLADSBTrackerBackend.exe"


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def run_cmd(args: list[str], cwd: Path, lines: list[str], timeout: int = 300, env: dict[str, str] | None = None) -> tuple[bool, str]:
    lines.append("")
    lines.append(f"$ {' '.join(args)}")
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        msg = f"FileNotFoundError: {exc}"
        lines.append(msg)
        return False, msg
    except subprocess.TimeoutExpired as exc:
        msg = f"TimeoutExpired after {timeout}s"
        lines.append(msg)
        if exc.stdout:
            lines.append(str(exc.stdout))
        return False, msg
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        lines.append(msg)
        return False, msg

    lines.append(f"returncode={proc.returncode}")
    if proc.stdout.strip():
        lines.append(proc.stdout.rstrip())
    return proc.returncode == 0, proc.stdout


def safe_rename_existing(path: Path, stamp: str, lines: list[str]) -> None:
    if not path.exists():
        return
    target = path.with_name(f"{path.name}.old_{stamp}")
    if target.exists():
        shutil.rmtree(target)
    path.rename(target)
    lines.append(f"Renamed existing package folder:")
    lines.append(f"  {path}")
    lines.append(f"  -> {target}")


def copytree_template(src: Path, dst: Path, lines: list[str]) -> None:
    ignore_names = {
        "__pycache__",
    }

    def ignore_func(directory: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if name in ignore_names:
                ignored.add(name)
            if name.endswith(".pyc") or name.endswith(".pyo"):
                ignored.add(name)
        return ignored

    shutil.copytree(src, dst, ignore=ignore_func)
    lines.append(f"Copied template package:")
    lines.append(f"  {src}")
    lines.append(f"  -> {dst}")


def find_template(build_root: Path, lines: list[str]) -> Path | None:
    exact = build_root / f"{PACKAGE_BASENAME}-{TEMPLATE_VERSION}"
    if exact.exists():
        lines.append(f"Using exact template package: {exact}")
        return exact

    candidates = sorted(
        [p for p in build_root.glob(f"{PACKAGE_BASENAME}-v*") if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        lines.append(f"Exact template {exact} not found; using newest package folder: {candidates[0]}")
        return candidates[0]

    lines.append(f"FAIL: no existing package template found under {build_root}")
    return None


def find_python_launcher(repo: Path, lines: list[str]) -> list[str] | None:
    candidates: list[list[str]] = [
        ["py", "-3"],
        [sys.executable],
        ["python3"],
        ["python"],
    ]
    for cmd in candidates:
        ok, out = run_cmd(cmd + ["-c", "import sys; print(sys.executable); print(sys.version)"], repo, lines, timeout=30)
        if not ok:
            continue
        # Check PyInstaller in that interpreter.
        ok_pi, _ = run_cmd(cmd + ["-m", "PyInstaller", "--version"], repo, lines, timeout=60)
        if ok_pi:
            lines.append(f"Selected Python/PyInstaller launcher: {' '.join(cmd)}")
            return cmd
        lines.append(f"Python works but PyInstaller is unavailable for: {' '.join(cmd)}")

    lines.append("FAIL: No usable Python interpreter with PyInstaller found.")
    return None


def validate_source(repo: Path, lines: list[str]) -> bool:
    ok = True
    index = repo / "web" / "index.html"
    app_css = repo / "web" / "app.css"
    app_js = repo / "web" / "app.js"
    backend = repo / "src" / "backend" / "rtl_windows_pi_port_backend.py"
    backend2 = repo / "src" / "backend" / "rtl_windows_backend.py"

    for path in [index, app_css, app_js, backend, backend2]:
        exists = path.exists()
        lines.append(f"{'PASS' if exists else 'FAIL'}: required file exists: {path}")
        ok = ok and exists

    if not ok:
        return False

    index_text = index.read_text(encoding="utf-8", errors="replace")
    app_text = app_js.read_text(encoding="utf-8", errors="replace")
    backend_text = backend.read_text(encoding="utf-8", errors="replace")

    checks = [
        ("index references app.css", 'href="app.css' in index_text or "href='app.css" in index_text),
        ("index references app.js", 'src="app.js' in index_text or "src='app.js" in index_text),
        ("index has no inline style blocks", "<style" not in index_text.lower()),
        ("index has no non-empty inline script blocks", not re.search(r"<script\b(?![^>]*\bsrc\s*=)[^>]*>\s*\S", index_text, flags=re.I | re.S)),
        ("app.js V9 DOM double-click fix installed", "__rtpV39DomAircraftMarkerDblclickInstalled" in app_text),
        ("app.js V8 diagnostic logger removed", "__rtpV38DblclickEventLoggerInstalled" not in app_text),
        ("backend serves app.css/app.js", 'request.path in ("/app.css", "/app.js")' in backend_text),
        ("backend V8 debug endpoint removed", '"/api/debug/ui-event"' not in backend_text),
    ]

    for name, passed in checks:
        lines.append(f"{'PASS' if passed else 'FAIL'}: {name}")
        ok = ok and passed

    cmd_ok, _ = run_cmd(["node", "--check", "web/app.js"], repo, lines, timeout=60)
    ok = ok and cmd_ok

    cmd_ok, _ = run_cmd([sys.executable, "-m", "py_compile", "src/backend/rtl_windows_pi_port_backend.py"], repo, lines, timeout=60)
    ok = ok and cmd_ok

    cmd_ok, _ = run_cmd([sys.executable, "-m", "py_compile", "src/backend/rtl_windows_backend.py"], repo, lines, timeout=60)
    ok = ok and cmd_ok

    return ok


def build_backend_exe(repo: Path, package_dir: Path, py_cmd: list[str], lines: list[str]) -> bool:
    dist_dir = package_dir / "app" / "backend"
    work_dir = repo / "runtime" / "build" / "pyinstaller-work-v1.2.0"
    spec_dir = repo / "runtime" / "build" / "pyinstaller-spec-v1.2.0"

    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    exe_path = dist_dir / BACKEND_EXE
    if exe_path.exists():
        exe_path.unlink()
        lines.append(f"Removed old backend exe from staged package: {exe_path}")

    # Clean previous PyInstaller work for this release to avoid stale imports.
    if work_dir.exists():
        shutil.rmtree(work_dir)
    if spec_dir.exists():
        shutil.rmtree(spec_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    src_backend = str((repo / "src" / "backend").resolve())
    src_root = str((repo / "src").resolve())
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_backend + os.pathsep + src_root + (os.pathsep + existing if existing else "")

    cmd = py_cmd + [
        "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--name", "RTLADSBTrackerBackend",
        "--distpath", str(dist_dir.resolve()),
        "--workpath", str(work_dir.resolve()),
        "--specpath", str(spec_dir.resolve()),
        "--paths", src_backend,
        "--paths", src_root,
        "--hidden-import", "rtl_windows_backend",
        "--hidden-import", "rtl_windows_pi_port_backend",
        str((repo / "src" / "backend" / "rtl_windows_pi_port_backend.py").resolve()),
    ]

    ok, _ = run_cmd(cmd, repo, lines, timeout=900, env=env)
    if not ok:
        lines.append("FAIL: PyInstaller backend build failed.")
        return False

    if not exe_path.exists():
        # PyInstaller may append .exe only on Windows; try without.
        alt = dist_dir / "RTLADSBTrackerBackend"
        if alt.exists():
            alt.rename(exe_path)
        else:
            lines.append(f"FAIL: expected backend executable not found: {exe_path}")
            return False

    size = exe_path.stat().st_size
    lines.append(f"PASS: built backend executable: {exe_path} ({size:,} bytes)")
    return size > 1024 * 1024


def copy_web_assets(repo: Path, package_dir: Path, lines: list[str]) -> bool:
    web_dst = package_dir / "web"
    web_dst.mkdir(parents=True, exist_ok=True)

    ok = True
    for name in ["index.html", "app.css", "app.js"]:
        src = repo / "web" / name
        dst = web_dst / name
        if not src.exists():
            lines.append(f"FAIL: missing web asset: {src}")
            ok = False
            continue
        shutil.copy2(src, dst)
        lines.append(f"Copied web asset: {src} -> {dst}")

    return ok


def update_package_metadata(package_dir: Path, lines: list[str]) -> None:
    notes = f"""RTL ADS-B Tracker Windows Service {VERSION}

Release highlights:
- Refactored active UI out of inline index.html into app.css/app.js.
- Backend now serves /app.css and /app.js from the active web directory.
- Fixed aircraft marker double-click behavior using the existing aircraft list details workflow.
- Preserved normal single-click marker popup behavior.
- Includes ADS-B decoder tracking fallback so /api/aircraft.json works when Dump1090 is already running.
- Removed temporary browser double-click diagnostic endpoint/logging before release packaging.

Install:
  1. Extract this folder on the Windows target.
  2. Run install_service.cmd as Administrator for a fresh install.
  3. Run restart_service.cmd as Administrator to restart an existing install.
  4. Open http://<host-ip>:8090 or http://localhost:8090.

Generated: {dt.datetime.now().isoformat(timespec='seconds')}
"""
    notes_path = package_dir / f"RELEASE_NOTES_{VERSION}.txt"
    notes_path.write_text(notes, encoding="utf-8", newline="\r\n")
    lines.append(f"Wrote release notes: {notes_path}")

    version_path = package_dir / "VERSION.txt"
    version_path.write_text(f"{VERSION}\n", encoding="utf-8", newline="\r\n")
    lines.append(f"Wrote version file: {version_path}")


def zip_package(package_dir: Path, zip_path: Path, lines: list[str]) -> bool:
    if zip_path.exists():
        zip_path.unlink()
        lines.append(f"Removed existing zip: {zip_path}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                arc = path.relative_to(package_dir.parent)
                zf.write(path, arc.as_posix())

    size = zip_path.stat().st_size
    lines.append(f"PASS: wrote deployment zip: {zip_path} ({size:,} bytes)")
    return size > 1024 * 1024


def validate_package(package_dir: Path, zip_path: Path, lines: list[str]) -> bool:
    ok = True
    required = [
        package_dir / "RTLADSBTrackerService.exe",
        package_dir / "RTLADSBTrackerService.xml",
        package_dir / "install_service.cmd",
        package_dir / "restart_service.cmd",
        package_dir / "app" / "backend" / BACKEND_EXE,
        package_dir / "web" / "index.html",
        package_dir / "web" / "app.css",
        package_dir / "web" / "app.js",
        package_dir / "dist" / "third_party" / "dump1090" / "dump1090.exe",
        package_dir / "dist" / "third_party" / "dump1090" / "dump1090.cfg",
        zip_path,
    ]

    for path in required:
        exists = path.exists()
        lines.append(f"{'PASS' if exists else 'FAIL'}: package required file exists: {path}")
        ok = ok and exists

    if (package_dir / "web" / "app.js").exists():
        text = (package_dir / "web" / "app.js").read_text(encoding="utf-8", errors="replace")
        checks = [
            ("package app.js has V9 fix", "__rtpV39DomAircraftMarkerDblclickInstalled" in text),
            ("package app.js does not include V8 logger", "__rtpV38DblclickEventLoggerInstalled" not in text),
        ]
        for name, passed in checks:
            lines.append(f"{'PASS' if passed else 'FAIL'}: {name}")
            ok = ok and passed

    if (package_dir / "web" / "index.html").exists():
        text = (package_dir / "web" / "index.html").read_text(encoding="utf-8", errors="replace")
        checks = [
            ("package index references app.css", 'href="app.css' in text or "href='app.css" in text),
            ("package index references app.js", 'src="app.js' in text or "src='app.js" in text),
        ]
        for name, passed in checks:
            lines.append(f"{'PASS' if passed else 'FAIL'}: {name}")
            ok = ok and passed

    return ok


def main() -> int:
    repo = Path.cwd()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = downloads_dir() / f"rtl_windows_v1_2_0_deployment_build_{stamp}.txt"
    report.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("RTL ADS-B Tracker Windows Service v1.2.0 deployment package build")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append("")

    ok = True

    build_root = repo / "runtime" / "build" / "windows-service"
    package_dir = build_root / f"{PACKAGE_BASENAME}-{VERSION}"
    zip_path = build_root / f"{PACKAGE_BASENAME}-{VERSION}.zip"

    lines.append("=" * 90)
    lines.append("Source validation")
    lines.append("=" * 90)
    if not validate_source(repo, lines):
        ok = False

    lines.append("")
    lines.append("=" * 90)
    lines.append("Template package")
    lines.append("=" * 90)
    template = find_template(build_root, lines)
    if template is None:
        ok = False

    lines.append("")
    lines.append("=" * 90)
    lines.append("Python/PyInstaller selection")
    lines.append("=" * 90)
    py_cmd = find_python_launcher(repo, lines)
    if py_cmd is None:
        ok = False

    if ok:
        lines.append("")
        lines.append("=" * 90)
        lines.append("Stage package")
        lines.append("=" * 90)
        build_root.mkdir(parents=True, exist_ok=True)
        safe_rename_existing(package_dir, stamp, lines)
        copytree_template(template, package_dir, lines)

        lines.append("")
        lines.append("=" * 90)
        lines.append("Copy current web assets")
        lines.append("=" * 90)
        ok = copy_web_assets(repo, package_dir, lines) and ok

        lines.append("")
        lines.append("=" * 90)
        lines.append("Build backend executable")
        lines.append("=" * 90)
        ok = build_backend_exe(repo, package_dir, py_cmd, lines) and ok

        lines.append("")
        lines.append("=" * 90)
        lines.append("Package metadata")
        lines.append("=" * 90)
        update_package_metadata(package_dir, lines)

        lines.append("")
        lines.append("=" * 90)
        lines.append("Package validation")
        lines.append("=" * 90)
        ok = validate_package(package_dir, zip_path, lines) and ok

        lines.append("")
        lines.append("=" * 90)
        lines.append("Zip package")
        lines.append("=" * 90)
        ok = zip_package(package_dir, zip_path, lines) and ok

        lines.append("")
        lines.append("=" * 90)
        lines.append("Final package validation")
        lines.append("=" * 90)
        ok = validate_package(package_dir, zip_path, lines) and ok

    lines.append("")
    lines.append("=" * 90)
    lines.append("Git status summary")
    lines.append("=" * 90)
    run_cmd(["git", "status", "--short"], repo, lines, timeout=60)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)
    if ok:
        lines.append("PASS: v1.2.0 deployment package build complete.")
        lines.append(f"Package folder: {package_dir}")
        lines.append(f"Package zip:    {zip_path}")
    else:
        lines.append("FAIL: v1.2.0 deployment package build failed. Upload this report to ChatGPT.")

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(("PASS" if ok else "FAIL") + ": v1.2.0 deployment package build complete.")
    print("Report saved to:")
    print(f"  {report}")
    print("Windows path:")
    print(f"  {str(report).replace('/', '\\\\')}")
    if ok:
        print("Package folder:")
        print(f"  {package_dir}")
        print("Package zip:")
        print(f"  {zip_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
