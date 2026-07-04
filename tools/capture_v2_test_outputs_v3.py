#!/usr/bin/env python3
r"""
Capture V2 test/diagnostic outputs to the Windows Downloads folder.

Run from MSYS2 UCRT64 repo root:
  python3 tools/capture_v2_test_outputs_v3.py

Output file:
  Uses Windows USERPROFILE, normally:
  C:/Users/jim/Downloads/rtl_windows_v2_test_outputs_YYYYMMDD_HHMMSS.txt
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path


SCRIPTS_TO_RUN = [
    ("V2 aircraft marker double-click static validation", "tools/validate_v2_aircraft_marker_dblclick.py"),
    ("Development ADS-B runtime diagnosis", "tools/diagnose_dev_adsb_runtime.py"),
    ("V2 development full-stack discovery", "tools/discover_v2_dev_fullstack.py"),
]


def windows_downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"

    home_drive = os.environ.get("HOMEDRIVE")
    home_path = os.environ.get("HOMEPATH")
    if home_drive and home_path:
        return Path(home_drive + home_path) / "Downloads"

    # Last-resort fallback for this development machine.
    return Path("C:/Users/jim/Downloads")


def run_script(repo: Path, rel_script: str) -> tuple[int, str]:
    script_path = repo / rel_script
    if not script_path.exists():
        return 127, (
            f"FAIL: {rel_script} was not found.\n"
            f"Expected path: {script_path}\n"
            "Install/copy that script into tools/ first, then rerun this capture.\n"
        )

    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(repo),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=90,
        )
        return proc.returncode, proc.stdout
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        return 124, (
            out
            + "\nFAIL: Script timed out after 90 seconds.\n"
            + f"Timed out script: {rel_script}\n"
        )
    except Exception as exc:
        return 1, f"FAIL: Could not run {rel_script}: {type(exc).__name__}: {exc}\n"


def main() -> int:
    repo = Path.cwd()
    downloads = windows_downloads_dir()
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = downloads / f"rtl_windows_v2_test_outputs_{timestamp}.txt"

    downloads.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("RTL-Windows / RTP-Windows V2 test output capture")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append(f"USERPROFILE: {os.environ.get('USERPROFILE', '')}")
    lines.append(f"Downloads target: {downloads}")
    lines.append("")

    if not (repo / "web" / "app.js").exists():
        lines.append("FAIL: web/app.js was not found.")
        lines.append("Run this from the repository root:")
        lines.append("  cd ~/sdrdev/RTL-Windows-ADS-B-Tracker")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: Not run from repo root. Output saved to: {out_path}")
        return 2

    overall_fail = False

    for title, rel_script in SCRIPTS_TO_RUN:
        lines.append("=" * 90)
        lines.append(title)
        lines.append(f"Command: python3 {rel_script}")
        lines.append("=" * 90)

        rc, output = run_script(repo, rel_script)
        lines.append(output.rstrip())
        lines.append("")
        lines.append(f"RESULT: {'PASS' if rc == 0 else 'FAIL'} rc={rc}")
        lines.append("")

        if rc != 0:
            overall_fail = True

    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)
    if overall_fail:
        lines.append("FAIL: One or more checks failed. Upload this full file to ChatGPT.")
    else:
        lines.append("PASS: All captured checks passed.")
    lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'FAIL' if overall_fail else 'PASS'}: Capture complete.")
    print("")
    print("Output saved to:")
    print(f"  {out_path}")
    print("")
    print("Windows path:")
    print(f"  {str(out_path).replace('/', '\\\\')}")
    print("")
    print("Upload this .txt file to ChatGPT.")

    return 1 if overall_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
