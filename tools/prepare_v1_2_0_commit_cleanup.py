#!/usr/bin/env python3
r"""
Prepare v1.2.0 commit cleanup for RTL-Windows-ADS-B-Tracker.

Removes temporary development artifacts before committing:
  - V8 backend POST /api/debug/ui-event diagnostic route
  - ui_dblclick_debug.jsonl runtime log
  - patch backup files created under web/ and src/backend/
  - temporary patch/capture scripts copied into tools/

Keeps:
  - web/index.html -> app.css/app.js refactor
  - web/app.css
  - web/app.js V9 working double-click fix
  - backend /app.css and /app.js static asset route
  - backend ADS-B decoder tracking fallback
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path


BACKEND = Path("src/backend/rtl_windows_pi_port_backend.py")


TEMP_TOOL_NAMES = {
    "refactor_inline_ui_assets.py",
    "patch_v2_aircraft_marker_dblclick_details.py",
    "patch_v2_fix_aircraft_marker_dblclick_zoom.py",
    "validate_v2_aircraft_marker_dblclick.py",
    "patch_v3_aircraft_marker_dblclick_capture.py",
    "capture_v3_dblclick_diagnostics.py",
    "patch_v4_inline_index_dblclick_capture.py",
    "patch_v5_appjs_leaflet_marker_dblclick.py",
    "patch_v6_restore_click_safe_dblclick.py",
    "fix_v6_validation_false_negative.py",
    "patch_v7_marker_dblclick_use_list_click.py",
    "patch_v8_dblclick_event_logger.py",
    "capture_v8_dblclick_event_log.py",
    "patch_v9_dom_aircraft_marker_dblclick.py",
}


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def remove_debug_route(text: str, lines: list[str]) -> tuple[str, bool]:
    needle = 'if request.path == "/api/debug/ui-event":'
    idx = text.find(needle)
    if idx < 0:
        lines.append("No V8 debug route found in backend.")
        return text, False

    line_start = text.rfind("\n", 0, idx) + 1
    route_line = text[line_start:text.find("\n", line_start)]
    indent = len(route_line) - len(route_line.lstrip(" "))

    pos = line_start
    next_pos = text.find("\n", pos) + 1
    if next_pos <= 0:
        lines.append("WARN: could not determine route end.")
        return text, False

    end = next_pos
    while end < len(text):
        line_end = text.find("\n", end)
        if line_end < 0:
            line_end = len(text)
        line = text[end:line_end]
        stripped = line.strip()
        current_indent = len(line) - len(line.lstrip(" "))

        if stripped and current_indent <= indent:
            break

        end = line_end + 1
        if end <= 0:
            end = len(text)
            break

    new_text = text[:line_start] + text[end:]
    lines.append(f"Removed backend V8 debug route from offsets {line_start}..{end}.")
    return new_text, True


def run_cmd(args: list[str], cwd: Path, lines: list[str], timeout: int = 60) -> bool:
    try:
        proc = subprocess.run(args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except FileNotFoundError as exc:
        lines.append(f"WARN: command not found: {args[0]} ({exc})")
        return True
    except Exception as exc:
        lines.append(f"FAIL: command exception: {' '.join(args)} -> {type(exc).__name__}: {exc}")
        return False

    lines.append(f"Command: {' '.join(args)}")
    lines.append(f"Return code: {proc.returncode}")
    if proc.stdout.strip():
        lines.append(proc.stdout.rstrip())
    return proc.returncode == 0


def unlink_if_exists(path: Path, lines: list[str]) -> None:
    try:
        if path.exists():
            path.unlink()
            lines.append(f"Removed: {path}")
    except Exception as exc:
        lines.append(f"WARN: could not remove {path}: {type(exc).__name__}: {exc}")


def main() -> int:
    repo = Path.cwd()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = downloads_dir() / f"rtl_windows_v1_2_0_commit_cleanup_{stamp}.txt"
    report.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("RTL-Windows v1.2.0 commit cleanup")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append("")

    ok = True

    lines.append("=" * 90)
    lines.append("Remove V8 backend debug endpoint")
    lines.append("=" * 90)
    if BACKEND.exists():
        backend_text = BACKEND.read_text(encoding="utf-8", errors="replace")
        backup = BACKEND.with_name(f"{BACKEND.name}.bak_v1_2_0_cleanup_{stamp}")
        shutil.copy2(BACKEND, backup)
        lines.append(f"Backup: {backup}")
        new_text, changed = remove_debug_route(backend_text, lines)
        if changed:
            BACKEND.write_text(new_text, encoding="utf-8", newline="\n")
    else:
        lines.append(f"FAIL: missing {BACKEND}")
        ok = False

    lines.append("")
    lines.append("=" * 90)
    lines.append("Remove temporary backup files")
    lines.append("=" * 90)
    for pattern in [
        "web/*.bak_*",
        "src/backend/*.bak_*",
    ]:
        for path in repo.glob(pattern):
            # Keep the cleanup backup while validation runs? No, remove old backups only;
            # leave the new cleanup backup out of the commit by removing it too.
            unlink_if_exists(path, lines)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Remove temporary patch/capture tools")
    lines.append("=" * 90)
    tools_dir = repo / "tools"
    for name in sorted(TEMP_TOOL_NAMES):
        unlink_if_exists(tools_dir / name, lines)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Remove temporary runtime logs")
    lines.append("=" * 90)
    unlink_if_exists(repo / "runtime" / "logs" / "ui_dblclick_debug.jsonl", lines)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Validation")
    lines.append("=" * 90)
    app_js = repo / "web" / "app.js"
    backend = repo / "src" / "backend" / "rtl_windows_pi_port_backend.py"

    final_app = app_js.read_text(encoding="utf-8", errors="replace") if app_js.exists() else ""
    final_backend = backend.read_text(encoding="utf-8", errors="replace") if backend.exists() else ""
    checks = [
        ("app.js V9 installed", "__rtpV39DomAircraftMarkerDblclickInstalled" in final_app),
        ("app.js V8 logger removed", "__rtpV38DblclickEventLoggerInstalled" not in final_app),
        ("app.js V7 bridge removed", "__rtpV37MarkerDblclickUsesListClickInstalled" not in final_app),
        ("backend V8 debug route removed", '"/api/debug/ui-event"' not in final_backend),
        ("backend still serves app.css/app.js", 'request.path in ("/app.css", "/app.js")' in final_backend),
        ("index references app.css", 'href="app.css' in (repo / "web" / "index.html").read_text(encoding="utf-8", errors="replace")),
        ("index references app.js", 'src="app.js' in (repo / "web" / "index.html").read_text(encoding="utf-8", errors="replace")),
    ]

    for name, passed in checks:
        if not passed:
            ok = False
        lines.append(f"{'PASS' if passed else 'FAIL'}: {name}")

    ok = run_cmd(["node", "--check", "web/app.js"], repo, lines) and ok
    ok = run_cmd([sys.executable, "-m", "py_compile", "src/backend/rtl_windows_pi_port_backend.py"], repo, lines) and ok

    lines.append("")
    lines.append("=" * 90)
    lines.append("Git status summary")
    lines.append("=" * 90)
    run_cmd(["git", "status", "--short"], repo, lines)

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)
    if ok:
        lines.append("PASS: repo cleanup is ready for v1.2.0 commit.")
    else:
        lines.append("FAIL: cleanup validation found problems. Upload this report to ChatGPT.")

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(("PASS" if ok else "FAIL") + ": v1.2.0 commit cleanup complete.")
    print("Report saved to:")
    print(f"  {report}")
    print("Windows path:")
    print(f"  {str(report).replace('/', '\\\\')}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
