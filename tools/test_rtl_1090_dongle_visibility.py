#!/usr/bin/env python3
r"""
RTL-SDR / ADS-B dongle visibility test for RTL-Windows / RTP-Windows.

Run from MSYS2 UCRT64 repo root:
  python3 tools/test_rtl_1090_dongle_visibility.py

Output:
  C:/Users/jim/Downloads/rtl_windows_1090_dongle_test_YYYYMMDD_HHMMSS.txt

What it checks:
  - Whether RTL-SDR command-line tools are available.
  - Whether Windows/libusb can enumerate RTL-SDR devices.
  - Whether expected serials 00001090 and 00000162 are visible.
  - Whether either device can be opened briefly with rtl_test.
  - Whether dump1090.exe exists.

It does NOT call cmd.exe, PowerShell, or WSL.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


EXPECTED_ADSB_SERIAL = "00001090"
EXPECTED_AUDIO_SERIAL = "00000162"

RUN_TIMEOUT_SECONDS = 14

RTL_TOOL_NAMES = [
    "rtl_test.exe",
    "rtl_test",
    "rtl_eeprom.exe",
    "rtl_eeprom",
    "rtl_adsb.exe",
    "rtl_adsb",
]

DUMP1090_NAMES = [
    "dump1090.exe",
]


def downloads_dir() -> Path:
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        return Path(userprofile) / "Downloads"
    return Path("C:/Users/jim/Downloads")


def path_excluded(path: Path, repo: Path) -> bool:
    try:
        rel = path.relative_to(repo)
    except ValueError:
        return True
    excluded = {".git", "__pycache__", ".venv", "venv", "env", "test_output"}
    return any(part in excluded for part in rel.parts)


def find_executable(repo: Path, names: list[str]) -> list[Path]:
    found: list[Path] = []

    for name in names:
        p = shutil.which(name)
        if p:
            found.append(Path(p))

    for path in repo.rglob("*"):
        if path_excluded(path, repo) or not path.is_file():
            continue
        if path.name.lower() in {n.lower() for n in names}:
            found.append(path)

    # Deduplicate while preserving order.
    result: list[Path] = []
    seen: set[str] = set()
    for p in found:
        key = str(p).lower()
        if key not in seen:
            result.append(p)
            seen.add(key)
    return result


def command_env_for(exe: Path) -> dict[str, str]:
    env = os.environ.copy()

    # Put executable folder first so bundled DLLs next to rtl_test/dump1090 are found.
    exe_dir = str(exe.parent)
    old_path = env.get("PATH", "")
    env["PATH"] = exe_dir + os.pathsep + old_path

    return env


def run_command(args: list[str], cwd: Path, timeout: int = RUN_TIMEOUT_SECONDS) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            env=command_env_for(Path(args[0])),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        return 124, out + f"\nFAIL: command timed out after {timeout} seconds.\n"
    except FileNotFoundError:
        return 127, "FAIL: executable not found.\n"
    except Exception as exc:
        return 1, f"FAIL: {type(exc).__name__}: {exc}\n"


def parse_rtl_devices(output: str) -> tuple[int | None, list[dict[str, str]]]:
    found_count = None
    devices: list[dict[str, str]] = []

    m = re.search(r"Found\s+(\d+)\s+device", output, re.I)
    if m:
        try:
            found_count = int(m.group(1))
        except ValueError:
            pass

    # Typical: 0: Realtek, RTL2838UHIDIR, SN: 00001090
    for line in output.splitlines():
        m = re.match(r"\s*(\d+):\s*(.*?)(?:,\s*SN:\s*([A-Za-z0-9_-]+))?\s*$", line)
        if not m:
            continue
        idx, desc, serial = m.group(1), m.group(2), m.group(3) or ""
        if "realtek" in desc.lower() or "rtl" in desc.lower() or serial:
            devices.append({"index": idx, "description": desc.strip(), "serial": serial.strip()})

    return found_count, devices


def summarize_device_visibility(output: str) -> list[str]:
    lines: list[str] = []
    found_count, devices = parse_rtl_devices(output)

    if found_count is None:
        lines.append("FAIL: Could not parse RTL-SDR device count from tool output.")
    elif found_count <= 0:
        lines.append("FAIL: RTL-SDR tool reports 0 devices.")
    else:
        lines.append(f"PASS: RTL-SDR tool reports {found_count} device(s).")

    if devices:
        lines.append("Parsed devices:")
        for dev in devices:
            serial = dev["serial"] or "unknown"
            lines.append(f"  - index={dev['index']} serial={serial} description={dev['description']}")
    else:
        lines.append("FAIL: No individual device lines with serial/index were parsed.")

    seen_serials = {dev["serial"] for dev in devices if dev["serial"]}
    if EXPECTED_ADSB_SERIAL in seen_serials or EXPECTED_ADSB_SERIAL in output:
        lines.append(f"PASS: expected ADS-B serial {EXPECTED_ADSB_SERIAL} is visible.")
    else:
        lines.append(f"FAIL: expected ADS-B serial {EXPECTED_ADSB_SERIAL} is NOT visible.")

    if EXPECTED_AUDIO_SERIAL in seen_serials or EXPECTED_AUDIO_SERIAL in output:
        lines.append(f"PASS: expected audio serial {EXPECTED_AUDIO_SERIAL} is visible.")
    else:
        lines.append(f"WARN: expected audio serial {EXPECTED_AUDIO_SERIAL} is not visible in this output.")

    return lines


def check_adjacent_dlls(exe: Path) -> list[str]:
    dll_names = [
        "rtlsdr.dll",
        "libusb-1.0.dll",
        "pthreadGC2.dll",
        "libwinpthread-1.dll",
    ]
    lines = []
    for dll in dll_names:
        p = exe.parent / dll
        lines.append(f"{'PASS' if p.exists() else 'WARN'}: adjacent {dll} {'found' if p.exists() else 'not found'} at {p}")
    return lines


def main() -> int:
    repo = Path.cwd()
    downloads = downloads_dir()
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = downloads / f"rtl_windows_1090_dongle_test_{stamp}.txt"

    lines: list[str] = []
    lines.append("RTL-Windows / RTP-Windows 1090 dongle visibility test")
    lines.append(f"Timestamp: {dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Repo: {repo}")
    lines.append(f"Python: {sys.executable}")
    lines.append(f"Expected ADS-B serial: {EXPECTED_ADSB_SERIAL}")
    lines.append(f"Expected audio serial: {EXPECTED_AUDIO_SERIAL}")
    lines.append("")

    if not (repo / "web" / "app.js").exists():
        lines.append("FAIL: web/app.js was not found. Run from repo root.")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"FAIL: not run from repo root. Output saved to: {out_path}")
        return 2

    rtl_tools = find_executable(repo, RTL_TOOL_NAMES)
    dump1090s = find_executable(repo, DUMP1090_NAMES)

    lines.append("=" * 90)
    lines.append("Tool discovery")
    lines.append("=" * 90)

    if rtl_tools:
        lines.append(f"PASS: found {len(rtl_tools)} RTL-SDR tool candidate(s):")
        for p in rtl_tools[:60]:
            lines.append(f"  - {p}")
    else:
        lines.append("FAIL: no rtl_test/rtl_eeprom/rtl_adsb tools found in PATH or repo.")

    if dump1090s:
        lines.append(f"PASS: found {len(dump1090s)} dump1090.exe candidate(s):")
        for p in dump1090s[:30]:
            lines.append(f"  - {p}")
    else:
        lines.append("WARN: no dump1090.exe candidate found in PATH or repo.")

    rtl_test_candidates = [p for p in rtl_tools if p.name.lower() in {"rtl_test.exe", "rtl_test"}]
    rtl_eeprom_candidates = [p for p in rtl_tools if p.name.lower() in {"rtl_eeprom.exe", "rtl_eeprom"}]
    rtl_adsb_candidates = [p for p in rtl_tools if p.name.lower() in {"rtl_adsb.exe", "rtl_adsb"}]

    overall_fail = False

    lines.append("")
    lines.append("=" * 90)
    lines.append("DLL checks for first rtl_test candidate")
    lines.append("=" * 90)
    if rtl_test_candidates:
        lines.append(f"Selected rtl_test: {rtl_test_candidates[0]}")
        lines.extend(check_adjacent_dlls(rtl_test_candidates[0]))
    else:
        lines.append("FAIL: no rtl_test candidate available for DLL check.")
        overall_fail = True

    lines.append("")
    lines.append("=" * 90)
    lines.append("rtl_test enumeration")
    lines.append("=" * 90)
    enumeration_output = ""
    if rtl_test_candidates:
        rtl_test = rtl_test_candidates[0]

        for args in ([str(rtl_test), "-t"], [str(rtl_test)]):
            lines.append(f"Command: {' '.join(args)}")
            rc, out = run_command(args, cwd=repo, timeout=RUN_TIMEOUT_SECONDS)
            lines.append(f"Return code: {rc}")
            lines.append("Output:")
            lines.append(out.rstrip())
            lines.append("")
            if out:
                enumeration_output += "\n" + out
            # Stop after first command that clearly enumerates devices.
            if "Found" in out and "device" in out:
                break

        lines.append("Parsed result:")
        parsed_lines = summarize_device_visibility(enumeration_output)
        lines.extend(parsed_lines)
        if any(line.startswith(f"FAIL: expected ADS-B serial {EXPECTED_ADSB_SERIAL}") for line in parsed_lines):
            overall_fail = True
        if any(line == "FAIL: RTL-SDR tool reports 0 devices." for line in parsed_lines):
            overall_fail = True
        if any(line == "FAIL: Could not parse RTL-SDR device count from tool output." for line in parsed_lines):
            overall_fail = True
    else:
        lines.append("FAIL: skipped rtl_test enumeration because rtl_test was not found.")
        overall_fail = True

    lines.append("")
    lines.append("=" * 90)
    lines.append("rtl_eeprom serial visibility")
    lines.append("=" * 90)
    if rtl_eeprom_candidates:
        rtl_eeprom = rtl_eeprom_candidates[0]
        lines.append(f"Selected rtl_eeprom: {rtl_eeprom}")
        rc, out = run_command([str(rtl_eeprom)], cwd=repo, timeout=RUN_TIMEOUT_SECONDS)
        lines.append(f"Return code: {rc}")
        lines.append("Output:")
        lines.append(out.rstrip())
        if EXPECTED_ADSB_SERIAL in out:
            lines.append(f"PASS: rtl_eeprom output includes ADS-B serial {EXPECTED_ADSB_SERIAL}.")
        else:
            lines.append(f"WARN: rtl_eeprom output does not include ADS-B serial {EXPECTED_ADSB_SERIAL}.")
    else:
        lines.append("WARN: rtl_eeprom was not found; skipped serial EEPROM read.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Brief per-index open tests with rtl_test")
    lines.append("=" * 90)
    if rtl_test_candidates:
        rtl_test = rtl_test_candidates[0]
        found_count, devices = parse_rtl_devices(enumeration_output)
        indices = []
        if devices:
            indices = [dev["index"] for dev in devices[:4]]
        elif found_count and found_count > 0:
            indices = [str(i) for i in range(min(found_count, 4))]

        if not indices:
            lines.append("WARN: no indices available for per-device open tests.")
        else:
            for idx in indices:
                args = [str(rtl_test), "-d", str(idx), "-t"]
                lines.append(f"Command: {' '.join(args)}")
                rc, out = run_command(args, cwd=repo, timeout=RUN_TIMEOUT_SECONDS)
                lines.append(f"Return code: {rc}")
                brief = out.rstrip()
                lines.append(brief)
                if "usb_open error" in out.lower() or "failed to open" in out.lower() or "no supported devices found" in out.lower():
                    lines.append(f"FAIL: device index {idx} could not be opened.")
                    overall_fail = True
                elif "Using device" in out or "Found" in out:
                    lines.append(f"PASS: device index {idx} opened/enumerated by rtl_test.")
                else:
                    lines.append(f"WARN: device index {idx} result was inconclusive.")
                lines.append("")
    else:
        lines.append("FAIL: skipped per-device open tests because rtl_test was not found.")
        overall_fail = True

    lines.append("")
    lines.append("=" * 90)
    lines.append("dump1090 availability")
    lines.append("=" * 90)
    if dump1090s:
        selected = dump1090s[0]
        lines.append(f"Selected dump1090: {selected}")
        lines.extend(check_adjacent_dlls(selected))
        for args in ([str(selected), "--help"], [str(selected), "-h"], [str(selected), "--version"]):
            lines.append(f"Command: {' '.join(args)}")
            rc, out = run_command(args, cwd=selected.parent, timeout=8)
            lines.append(f"Return code: {rc}")
            lines.append(out[:1800].rstrip())
            lines.append("")
            if rc in (0, 1) and out.strip():
                break
    else:
        lines.append("WARN: skipped dump1090 check because dump1090.exe was not found.")

    lines.append("")
    lines.append("=" * 90)
    lines.append("Overall result")
    lines.append("=" * 90)

    if overall_fail:
        lines.append("FAIL: Windows/MSYS2 RTL-SDR visibility test did not fully pass.")
        lines.append("")
        lines.append("Most common causes:")
        lines.append("  - The ADS-B dongle is not physically connected or is on a bad USB port/hub.")
        lines.append("  - The dongle still has the default Windows DVB-T driver instead of WinUSB/libusbK.")
        lines.append("  - Another process has the dongle open.")
        lines.append("  - The expected serial 00001090 is not assigned to the ADS-B dongle.")
        lines.append("")
        lines.append("Upload this full file to ChatGPT.")
        rc = 1
    else:
        lines.append("PASS: Windows/MSYS2 can see the expected ADS-B RTL-SDR dongle.")
        lines.append("Next step: test dump1090/backend startup using the visible device.")
        rc = 0

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{'PASS' if rc == 0 else 'FAIL'}: RTL-SDR 1090 dongle visibility test complete.")
    print("Output saved to:")
    print(f"  {out_path}")
    print("Windows path:")
    print(f"  {str(out_path).replace('/', '\\\\')}")
    print("Upload this .txt file if the result is FAIL or inconclusive.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
