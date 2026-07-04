#!/usr/bin/env python3
r"""
Update README.md for RTL ADS-B Tracker Windows v1.2.0.

Run from MSYS2 UCRT64 repo root:
  cd ~/sdrdev/RTL-Windows-ADS-B-Tracker
  python3 tools/update_readme_v1_2_0.py

The script:
  - backs up README.md
  - inserts/replaces a managed v1.2.0 release notes section
  - updates the "Current release" line if present, otherwise adds one
  - avoids touching build artifacts or temporary patch files
"""

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path


README = Path("README.md")

START = "<!-- RTL_WINDOWS_V1_2_0_START -->"
END = "<!-- RTL_WINDOWS_V1_2_0_END -->"

SECTION = f"""{START}
## Current Release: v1.2.0

Version 1.2.0 is the current Windows service deployment baseline for the RTL ADS-B Tracker. This release focuses on making the Windows application behave like the working Raspberry Pi tracker while preserving the Windows service packaging model.

### Functional Updates in v1.2.0

- **Aircraft map marker double-click details**  
  Double-clicking an aircraft marker on the map now opens the same aircraft details workflow used by the aircraft list. The implementation reuses the existing list click behavior instead of maintaining a separate details dialog path.

- **Normal marker single-click behavior preserved**  
  Single-clicking an aircraft marker still opens the normal Leaflet marker popup with quick aircraft information.

- **Double-click zoom suppression for aircraft markers**  
  Double-clicking an aircraft marker no longer zooms the map. The handler detects the active `#aircraftMap` container, stops the Leaflet double-click zoom event, extracts the visible aircraft marker token, and dispatches the matching aircraft list click.

- **UI asset refactor**  
  The active web UI has been split out of inline `index.html` blocks into:
  - `web/index.html`
  - `web/app.css`
  - `web/app.js`

  This makes future UI patches safer and easier to review.

- **Backend static asset support**  
  The backend now serves `/app.css` and `/app.js` so the refactored browser UI loads correctly from the Windows service backend.

- **ADS-B decoder runtime fallback**  
  The backend has improved ADS-B decoder tracking. If Dump1090 is already running and serving aircraft JSON, the backend treats it as available instead of reporting a stale process-tracking failure.

### Deployment Package

The v1.2.0 Windows service package is built under:

```text
runtime/build/windows-service/RTL-ADS-B-Tracker-Windows-Service-v1.2.0/
runtime/build/windows-service/RTL-ADS-B-Tracker-Windows-Service-v1.2.0.zip
```

The package includes:

```text
RTLADSBTrackerService.exe
RTLADSBTrackerService.xml
install_service.cmd
restart_service.cmd
app/backend/RTLADSBTrackerBackend.exe
web/index.html
web/app.css
web/app.js
dist/third_party/dump1090/dump1090.exe
dist/third_party/dump1090/dump1090.cfg
```

### Build Notes

The Windows deployment build requires PyInstaller in the MSYS2 UCRT64 environment:

```bash
pacman -S --needed mingw-w64-ucrt-x86_64-pyinstaller
python3 -m PyInstaller --version
```

Then build the deployment package from the repository root using the project packaging workflow. The generated runtime package and zip are release artifacts and should not be committed to the source repository unless intentionally publishing binaries through GitHub Releases.

### User Interface Notes

- Open the UI at `http://localhost:8090` for the installed service.
- Use `http://localhost:8091` for local development runs when avoiding a conflict with the installed service.
- The aircraft list and map use the same details workflow.
- Single-click an aircraft marker for the marker popup.
- Double-click an aircraft marker for the full details dialog.
- Use **Restore History** to reload recent aircraft trail history.
{END}
"""


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def run_cmd(args: list[str], cwd: Path, lines: list[str], timeout: int = 60) -> bool:
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


def update_readme(text: str) -> str:
    if START in text and END in text:
        pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
        return pattern.sub(SECTION.strip(), text)

    # Update an existing Current Release line if present.
    text = re.sub(
        r"(?im)^(\s*(?:\*\*)?Current Release(?:\*\*)?\s*[:\-]\s*)v?[0-9][^\n]*$",
        r"\g<1>v1.2.0",
        text,
        count=1,
    )

    # Insert after top-level title when possible.
    m = re.search(r"(?m)^# .+\n", text)
    if m:
        insert_at = m.end()
        return text[:insert_at] + "\n" + SECTION.strip() + "\n\n" + text[insert_at:].lstrip()

    return SECTION.strip() + "\n\n" + text.lstrip()


def main() -> int:
    repo = Path.cwd()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = downloads_dir() / f"rtl_windows_readme_v1_2_0_update_{stamp}.txt"
    report.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("RTL-Windows README v1.2.0 update")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append("")

    ok = True

    if not README.exists():
        lines.append("README.md was missing; creating a new one.")
        original = "# RTL ADS-B Tracker for Windows\n\n"
    else:
        original = README.read_text(encoding="utf-8", errors="replace")
        backup = README.with_name(f"README.md.bak_v1_2_0_{stamp}")
        backup.write_text(original, encoding="utf-8", newline="\n")
        lines.append(f"Backup: {backup}")

    updated = update_readme(original)
    README.write_text(updated, encoding="utf-8", newline="\n")
    lines.append("Updated README.md with managed v1.2.0 section.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Validation")
    lines.append("=" * 90)
    final = README.read_text(encoding="utf-8", errors="replace")
    checks = [
        ("README contains managed v1.2.0 start marker", START in final),
        ("README contains managed v1.2.0 end marker", END in final),
        ("README mentions marker double-click details", "Double-clicking an aircraft marker" in final),
        ("README mentions app.css/app.js refactor", "web/app.css" in final and "web/app.js" in final),
        ("README mentions deployment zip", "RTL-ADS-B-Tracker-Windows-Service-v1.2.0.zip" in final),
        ("README mentions PyInstaller package", "mingw-w64-ucrt-x86_64-pyinstaller" in final),
    ]

    for name, passed in checks:
        lines.append(f"{'PASS' if passed else 'FAIL'}: {name}")
        ok = ok and passed

    lines.append("")
    lines.append("=" * 90)
    lines.append("Git diff summary")
    lines.append("=" * 90)
    run_cmd(["git", "diff", "--", "README.md"], repo, lines, timeout=60)
    run_cmd(["git", "status", "--short", "--", "README.md"], repo, lines, timeout=60)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)
    if ok:
        lines.append("PASS: README.md updated for v1.2.0.")
    else:
        lines.append("FAIL: README.md update validation failed. Upload this report to ChatGPT.")

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(("PASS" if ok else "FAIL") + ": README v1.2.0 update complete.")
    print("Report saved to:")
    print(f"  {report}")
    print("Windows path:")
    print(f"  {str(report).replace('/', '\\\\')}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
