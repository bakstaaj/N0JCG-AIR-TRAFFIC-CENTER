#!/usr/bin/env python3
# Patch backend decoder tracking fallback for RTL-Windows / RTP-Windows.
#
# Run from MSYS2 UCRT64 repo root:
#   python3 tools/patch_backend_decoder_tracking_fallback.py
#
# Problem fixed:
#   The service can have Dump1090 alive on the configured HTTP port (18080), but
#   /api/aircraft.json can still return 503 because DecoderManager.is_running()
#   only trusts the Popen child-process object. If that tracking state is stale,
#   the backend refuses to proxy aircraft JSON even though Dump1090 is responding.
#
# Patch:
#   - src/backend/rtl_windows_backend.py:
#       DecoderManager.is_running() now returns True when the child process is
#       alive OR when the configured decoder JSON URL responds with aircraft JSON.
#   - src/backend/rtl_windows_pi_port_backend.py:
#       /api/aircraft.json attempts one on-demand decoder restart before returning
#       503, and then rechecks the decoder.
#
# Notes:
#   - This patches source files only.
#   - The Windows service PyInstaller backend EXE must be rebuilt/repackaged for
#     the installed service to use this change.
#   - Development/source backend runs will use the patch immediately.
#
# Output:
#   C:/Users/jim/Downloads/rtl_windows_backend_decoder_tracking_patch_YYYYMMDD_HHMMSS.txt

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path


BACKEND_REL = Path("src/backend/rtl_windows_backend.py")
PI_PORT_REL = Path("src/backend/rtl_windows_pi_port_backend.py")


OLD_IS_RUNNING = '''    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None
'''

NEW_IS_RUNNING = '''    def is_running(self) -> bool:
        # Return True when the tracked child is alive or its HTTP JSON endpoint is alive.
        #
        # The Windows service can leave Dump1090 serving on the configured HTTP port
        # even when the Python Popen tracking state is stale or has been disrupted by
        # service restarts. The UI should treat the decoder as available when the
        # configured /data/aircraft.json endpoint is responding with valid JSON.
        if self.process is not None and self.process.poll() is None:
            return True
        try:
            with urlopen(self.decoder_json_url, timeout=0.75) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return isinstance(payload, dict) and isinstance(payload.get("aircraft"), list)
        except Exception:
            return False
'''


OLD_AIRCRAFT_ROUTE = '''            elif request.path == "/api/aircraft.json":
                if not self.manager.is_running():
                    self.send_json({"error": "ADS-B decoder is not running."}, HTTPStatus.SERVICE_UNAVAILABLE)
                else:
                    self.send_json(self.normalize_pi_aircraft_payload(self.manager.query_aircraft()))
'''

NEW_AIRCRAFT_ROUTE = '''            elif request.path == "/api/aircraft.json":
                if not self.manager.is_running():
                    try:
                        LOG.info("ADS-B decoder not available by process state; attempting on-demand start before aircraft response.")
                        self.manager.start()
                    except Exception as exc:
                        LOG.warning("On-demand ADS-B decoder start failed before aircraft response: %s", exc)
                if not self.manager.is_running():
                    self.send_json({"error": "ADS-B decoder is not running."}, HTTPStatus.SERVICE_UNAVAILABLE)
                else:
                    self.send_json(self.normalize_pi_aircraft_payload(self.manager.query_aircraft()))
'''


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def backup(path: Path, stamp: str) -> Path:
    backup_path = path.with_name(f"{path.name}.bak_decoder_tracking_{stamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def patch_file(path: Path, old: str, new: str, marker: str, lines: list[str], stamp: str) -> bool:
    if not path.exists():
        lines.append(f"FAIL: missing file: {path}")
        return False

    text = path.read_text(encoding="utf-8", errors="replace")
    if marker in text:
        lines.append(f"PASS: {path} already contains patch marker.")
        return True

    if old not in text:
        lines.append(f"FAIL: expected block was not found in {path}")
        lines.append("Expected block:")
        lines.append(old)
        return False

    backup_path = backup(path, stamp)
    patched = text.replace(old, new, 1)
    path.write_text(patched, encoding="utf-8", newline="\n")
    lines.append(f"PASS: patched {path}")
    lines.append(f"Backup: {backup_path}")
    return True


def py_compile(paths: list[Path], repo: Path, lines: list[str]) -> bool:
    ok = True
    for path in paths:
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            cwd=str(repo),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if proc.returncode == 0:
            lines.append(f"PASS: py_compile {path}")
        else:
            ok = False
            lines.append(f"FAIL: py_compile {path}")
            lines.append(proc.stdout)
    return ok


def main() -> int:
    repo = Path.cwd()
    downloads = downloads_dir()
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = downloads / f"rtl_windows_backend_decoder_tracking_patch_{stamp}.txt"

    lines: list[str] = []
    lines.append("RTL-Windows backend decoder tracking fallback patch")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append("")

    if not (repo / "web" / "app.js").exists():
        lines.append("FAIL: web/app.js not found. Run this from the repo root.")
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: run from repo root. Report: {report}")
        return 2

    backend = repo / BACKEND_REL
    pi_port = repo / PI_PORT_REL

    lines.append("=" * 90)
    lines.append("Patch actions")
    lines.append("=" * 90)

    ok1 = patch_file(
        backend,
        OLD_IS_RUNNING,
        NEW_IS_RUNNING,
        "Return True when the tracked child is alive or its HTTP JSON endpoint is alive",
        lines,
        stamp,
    )
    ok2 = patch_file(
        pi_port,
        OLD_AIRCRAFT_ROUTE,
        NEW_AIRCRAFT_ROUTE,
        "attempting on-demand start before aircraft response",
        lines,
        stamp,
    )

    lines.append("")
    lines.append("=" * 90)
    lines.append("Syntax validation")
    lines.append("=" * 90)
    ok3 = py_compile([backend, pi_port], repo, lines) if ok1 and ok2 else False

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)

    if ok1 and ok2 and ok3:
        lines.append("PASS: backend source patch installed and syntax is valid.")
        lines.append("")
        lines.append("Next required step:")
        lines.append("  Rebuild the Windows service backend/package so the installed PyInstaller EXE includes this source change.")
        lines.append("")
        lines.append("Suggested command from MSYS2 UCRT64 if your Windows Python launcher is working:")
        lines.append("  ./tools/build_windows_service_release.sh")
        lines.append("")
        lines.append("Then reinstall/restart the new service package and rerun validate_service_adsb_runtime.py.")
        rc = 0
    else:
        lines.append("FAIL: patch did not complete cleanly.")
        lines.append("Upload this report to ChatGPT.")
        rc = 1

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'PASS' if rc == 0 else 'FAIL'}: backend decoder tracking fallback patch complete.")
    print("Report saved to:")
    print(f"  {report}")
    print("Windows path:")
    print(f"  {str(report).replace('/', '\\\\')}")
    if rc == 0:
        print("")
        print("Next:")
        print("  ./tools/build_windows_service_release.sh")
        print("Then install/restart the rebuilt service package and rerun validate_service_adsb_runtime.py.")
    else:
        print("Upload the report.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
