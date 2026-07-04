#!/usr/bin/env python3
"""Raspberry Pi 5 FlyCatcher/NESDR backend entry point.

This shim keeps the Windows/Pi-port HTTP API surface intact while replacing
Windows-only receiver probing and Dump1090 startup with Pi-native RTL serial
resolution and readsb startup.

Receiver serial ownership for the initial Pi 5 hardware target:
  * 00001090 -> FlyCatcher ADS-B 1090 MHz
  * 00000162 -> NESDR Nano2+ NOAA/Airband
  * 00000978 -> FlyCatcher UAT 978 MHz, detected but disabled for now

Do not hard-code runtime device indexes. They are resolved from EEPROM serials
at each backend startup because Linux RTL order can change across USB changes.
"""

from __future__ import annotations

import json
import logging
import os
from http import HTTPStatus
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import time
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse

import rtl_windows_backend as win_backend

ADSB_SERIAL = os.environ.get("PI_AIR_TRAFFIC_ADSB_SERIAL", "00001090")
AUDIO_SERIAL = os.environ.get("PI_AIR_TRAFFIC_AUDIO_SERIAL", "00000162")
UAT_SERIAL = os.environ.get("PI_AIR_TRAFFIC_UAT_SERIAL", "00000978")
UAT_FREQUENCY_HZ = int(os.environ.get("PI_AIR_TRAFFIC_UAT_FREQUENCY_HZ", "978000000"))
UAT_GAIN_DB = float(os.environ.get("PI_AIR_TRAFFIC_UAT_GAIN_DB", "49.6"))
UAT_JSON_PORT = int(os.environ.get("PI_AIR_TRAFFIC_UAT_JSON_PORT", "30978"))
UAT_RAW_PORT = int(os.environ.get("PI_AIR_TRAFFIC_UAT_RAW_PORT", "30979"))

TRAFFIC_SOURCE_SETTINGS_FILENAME = "traffic_sources.json"
DEFAULT_TRAFFIC_SOURCES = {"adsb_1090_enabled": True, "uat_978_enabled": False}
UAT_AIRCRAFT_STALE_SECONDS = float(os.environ.get("PI_AIR_TRAFFIC_UAT_STALE_SECONDS", "90"))

LOG = logging.getLogger("pi_air_traffic_backend")
RTL_TEST_DEVICE_RE = re.compile(r"^\s*(\d+):\s*([^,]+),\s*([^,]+),\s*SN:\s*(\S+)\s*$")


def pi_runtime_root(root: Path) -> Path:
    return Path(os.environ.get("RTL_ADSB_TRACKER_RUNTIME", str(root / "runtime"))).resolve()


def traffic_source_settings_path(root: Path) -> Path:
    return pi_runtime_root(root) / "settings" / TRAFFIC_SOURCE_SETTINGS_FILENAME


def load_traffic_source_settings(root: Path) -> dict[str, bool]:
    payload = dict(DEFAULT_TRAFFIC_SOURCES)
    path = traffic_source_settings_path(root)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            for key in payload:
                if key in loaded:
                    payload[key] = bool(loaded[key])
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        pass
    return payload


def save_traffic_source_settings(root: Path, settings: dict[str, bool]) -> dict[str, bool]:
    payload = dict(DEFAULT_TRAFFIC_SOURCES)
    for key in payload:
        if key in settings:
            payload[key] = bool(settings[key])
    path = traffic_source_settings_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)
    return payload


def pi_adsb_source_enabled(root: Path) -> bool:
    return bool(load_traffic_source_settings(root).get("adsb_1090_enabled", True))


def linux_path(path: Path) -> str:
    """Return native Linux paths for Pi runtime subprocesses."""
    return str(path)


# Patch the shared Windows baseline module before importing the Pi-port module.
# The imported AudioManager methods resolve these globals at runtime.
win_backend.ADSB_SERIAL = ADSB_SERIAL
win_backend.AUDIO_SERIAL = AUDIO_SERIAL
win_backend.windows_path = linux_path


class PiSerialDecoderManager(win_backend.DecoderManager):
    """Pi-native ADS-B manager using readsb and RTL EEPROM serial ownership."""

    def __init__(self, root: Path, dump_http_port: int, settings: win_backend.SettingsStore) -> None:
        super().__init__(root, dump_http_port, settings)
        runtime_root = Path(os.environ.get("RTL_ADSB_TRACKER_RUNTIME", str(root / "runtime"))).resolve()
        self.runtime_dir = runtime_root / "settings"
        self.json_dir = self.runtime_dir / "readsb-json"
        self.aircraft_json_path = self.json_dir / "aircraft.json"
        self.log_path = runtime_root / "logs" / "readsb_adsb_1090.log"
        self.readsb_command_path: str | None = None
        self.roles: dict[str, Any] = {}

    @property
    def decoder_json_url(self) -> str:
        return "file://" + str(self.aircraft_json_path)

    @staticmethod
    def _run_text(command: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    @classmethod
    def probe_rtl_devices(cls) -> list[dict[str, Any]]:
        rtl_test = shutil.which("rtl_test")
        if not rtl_test:
            raise RuntimeError("rtl_test is not available in PATH.")
        completed = cls._run_text([rtl_test, "-t"], timeout=15.0)
        combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        devices: list[dict[str, Any]] = []
        for line in combined.splitlines():
            match = RTL_TEST_DEVICE_RE.match(line)
            if not match:
                continue
            index, vendor, product, serial = match.groups()
            devices.append({
                "index": int(index),
                "vendor": vendor.strip(),
                "product": product.strip(),
                "serial": serial.strip(),
            })
        if not devices:
            stdout = completed.stdout.strip() or "<empty>"
            stderr = completed.stderr.strip() or "<empty>"
            raise RuntimeError(
                "rtl_test did not report any RTL-SDR device rows; "
                f"returncode={completed.returncode}; stdout={stdout}; stderr={stderr}"
            )
        return devices

    @staticmethod
    def _role_from_serial(devices: list[dict[str, Any]], serial: str, role_name: str, enabled: bool) -> dict[str, Any]:
        matches = [device for device in devices if str(device.get("serial")) == serial]
        if not matches:
            raise RuntimeError(f"Required RTL serial {serial} for role {role_name} was not detected: {devices}")
        if len(matches) > 1:
            raise RuntimeError(f"RTL serial {serial} for role {role_name} is duplicated: {matches}")
        role = dict(matches[0])
        role.update({"role": role_name, "enabled": enabled})
        return role

    def check_runtime_files(self) -> None:
        if not (shutil.which("readsb") or shutil.which("dump1090")):
            raise RuntimeError("Neither readsb nor dump1090 is available in PATH.")
        if not shutil.which("rtl_test"):
            raise RuntimeError("rtl_test is required for serial receiver mapping.")

    def resolve_roles(self) -> dict[str, Any]:
        self.check_runtime_files()
        devices = self.probe_rtl_devices()
        serials = [str(device.get("serial")) for device in devices]
        duplicates = sorted({serial for serial in serials if serials.count(serial) > 1})
        if duplicates:
            raise RuntimeError(f"Duplicate RTL serials are not allowed for Pi receiver ownership: {duplicates}")
        mapping = {
            "ok": True,
            "platform": "raspberry_pi_5_trixie",
            "mapping_policy": "resolve_runtime_indexes_from_rtl_eeprom_serials",
            "expected_serials": {
                "adsb_1090": ADSB_SERIAL,
                "audio_noaa_airband": AUDIO_SERIAL,
                "uat_978": UAT_SERIAL,
            },
            "device_count": len(devices),
            "devices": devices,
            "adsb": self._role_from_serial(devices, ADSB_SERIAL, "adsb_1090", True),
            "audio": self._role_from_serial(devices, AUDIO_SERIAL, "noaa_airband", True),
            "uat": self._role_from_serial(devices, UAT_SERIAL, "uat_978", False),
        }
        self.roles = mapping
        return mapping

    def _readsb_path(self) -> str:
        candidates = [
            self.root / "runtime" / "bin" / "readsb",
            self.root / "bin" / "readsb",
            Path("/opt/rtl-pi-adsb-tracker/bin/readsb"),
        ]
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                self.readsb_command_path = str(candidate)
                return str(candidate)
        if os.environ.get("PI_AIR_TRAFFIC_ALLOW_SYSTEM_READSB", "0") == "1":
            command = shutil.which("readsb") or shutil.which("dump1090")
            if command:
                self.readsb_command_path = command
                return command
        raise RuntimeError(
            "No app-owned RTL-SDR-enabled readsb was found. Run "
            "tools/pi5_install_app_owned_readsb.sh on the Pi. The Debian package "
            "readsb can exist but still reject --device-type rtlsdr."
        )

    def _readsb_command(self, adsb_index: int) -> list[str]:
        del adsb_index
        readsb = self._readsb_path()
        self.json_dir.mkdir(parents=True, exist_ok=True)
        adsb_gain = os.environ.get("PI_AIR_TRAFFIC_ADSB_GAIN", "-10")
        command = [
            readsb,
            "--device-type", "rtlsdr",
            "--device", ADSB_SERIAL,
            "--gain", adsb_gain,
            "--ppm", "0",
            "--net",
            "--net-heartbeat", "60",
            "--net-ri-port", "30001",
            "--net-ro-port", "30002",
            "--net-sbs-port", "30003",
            "--net-bi-port", "30004",
            "--net-bo-port", "30005",
            "--write-json", str(self.json_dir),
            "--write-json-every", "1",
            "--quiet",
        ]
        extra = os.environ.get("PI_AIR_TRAFFIC_READSB_EXTRA_ARGS", "").strip()
        if extra:
            import shlex
            command.extend(shlex.split(extra))
        return command

    def is_running(self) -> bool:
        # Only the child process owned by this backend proves decoder liveness.
        # A readable aircraft.json can be stale after a service restart; treating
        # it as running prevents readsb from being launched and freezes ADS-B data.
        return self.process is not None and self.process.poll() is None

    def query_aircraft(self, timeout: float = 1.5) -> dict[str, Any]:
        del timeout
        if not self.aircraft_json_path.is_file():
            raise FileNotFoundError(f"readsb aircraft JSON is not available yet: {self.aircraft_json_path}")
        payload = json.loads(self.aircraft_json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"readsb aircraft JSON must be an object: {self.aircraft_json_path}")
        aircraft = payload.get("aircraft")
        if aircraft is None:
            payload["aircraft"] = []
        elif not isinstance(aircraft, list):
            raise ValueError("readsb aircraft JSON field 'aircraft' must be a list.")
        return payload

    def start(self) -> dict[str, Any]:
        with self.lock:
            if not pi_adsb_source_enabled(self.root):
                self.last_error = None
                status = self.status()
                decoder = status.setdefault("decoder", {})
                decoder["disabled_by_settings"] = True
                return status
            if self.is_running():
                return self.status()
            self.last_error = None
            try:
                mapping = self.resolve_roles()
                adsb_index = int(mapping["adsb"]["index"])
                self.runtime_dir.mkdir(parents=True, exist_ok=True)
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                self.json_dir.mkdir(parents=True, exist_ok=True)
                try:
                    self.aircraft_json_path.unlink()
                except FileNotFoundError:
                    pass
                command = self._readsb_command(adsb_index)
                self.log_handle = self.log_path.open("a", encoding="utf-8", newline="\n")
                LOG.info(
                    "Starting readsb for ADS-B serial %s at runtime index %s; JSON dir=%s",
                    ADSB_SERIAL,
                    adsb_index,
                    self.json_dir,
                )
                self.process = subprocess.Popen(
                    command,
                    cwd=str(self.root),
                    stdout=self.log_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                self.started_at = time.time()
                # readsb can stay healthy before aircraft.json exists, especially indoors
                # or before the first live 1090 MHz frame is decoded. Do not block the
                # HTTP backend for the full JSON wait during startup; just verify that
                # the child process survives its immediate option/device checks.
                deadline = time.time() + 3.0
                while time.time() < deadline:
                    if self.process.poll() is not None:
                        raise RuntimeError(
                            f"readsb exited during startup with code {self.process.returncode}; see {self.log_path}."
                        )
                    if self.aircraft_json_path.is_file():
                        try:
                            self.query_aircraft()
                            return self.status()
                        except (json.JSONDecodeError, ValueError, URLError):
                            pass
                    time.sleep(0.25)
                LOG.info("readsb is running; aircraft.json is not required before HTTP startup completes")
                return self.status()
            except Exception as exc:
                self.last_error = str(exc)
                self.stop()
                raise

    def status(self) -> dict[str, Any]:
        running = self.is_running()
        decoder: dict[str, Any] = {
            "running": running,
            "profile": {
                "frequency_hz": 1090000000,
                "sample_rate_sps": 2000000,
                "gain_db": 48.0,
                "decoder": self.readsb_command_path or "readsb",
            },
            "json_url_internal": self.decoder_json_url,
            "json_path": str(self.aircraft_json_path),
        }
        if running:
            try:
                aircraft_json = self.query_aircraft()
                decoder["messages"] = int(aircraft_json.get("messages", 0))
                decoder["aircraft_count"] = len(aircraft_json.get("aircraft", []))
                decoder["json_ready"] = True
            except Exception as exc:
                decoder["json_ready"] = False
                decoder["query_error"] = str(exc)
        else:
            decoder["json_ready"] = False
        return {
            "ok": True,
            "service": "PI-AIR-TRAFFIC-TRACKER",
            "receiver_roles": self.roles,
            "receiver_location": self.settings.receiver_location(),
            "decoder": decoder,
            "last_error": self.last_error,
        }




class PiUat978Manager:
    """Manual, disabled-by-default UAT 978 MHz decoder controller.

    V0.2 exposes explicit API control for app-owned dump978-fa without enabling
    automatic startup. This keeps the validated ADS-B/NOAA/Airband V0.1 runtime
    stable while proving the third receiver path can be controlled by serial.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.runtime_root = Path(os.environ.get("RTL_ADSB_TRACKER_RUNTIME", str(self.root / "runtime"))).resolve()
        self.log_path = self.runtime_root / "logs" / "dump978_uat_978.log"
        self.lock = threading.RLock()
        self.process: subprocess.Popen[str] | None = None
        self.log_handle: Any = None
        self.started_at: float | None = None
        self.last_error: str | None = None
        self.command_path: str | None = None
        self.stop_event = threading.Event()
        self.collector_thread: threading.Thread | None = None
        self.collector_error: str | None = None
        self.aircraft_by_hex: dict[str, dict[str, Any]] = {}
        self.aircraft_lock = threading.RLock()
        self.message_count = 0


    @staticmethod
    def _first_value(payload: dict[str, Any], *names: str) -> Any:
        for name in names:
            value = payload.get(name)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if math.isfinite(result) else None

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        try:
            result = int(float(value))
        except (TypeError, ValueError):
            return None
        return result

    @staticmethod
    def _format_address(value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, int):
            return f"{value:06X}"[-6:]
        text = str(value).strip().upper()
        if text.startswith("0X"):
            text = text[2:]
        cleaned = "".join(character for character in text if character in "0123456789ABCDEF")
        if len(cleaned) >= 6:
            return cleaned[-6:]
        return cleaned

    def _normalize_uat_record(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        address = self._format_address(self._first_value(
            payload,
            "address", "addr", "icao", "icao_address", "hex", "aircraft_address", "address_qualifier"
        ))
        callsign = str(self._first_value(payload, "callsign", "flight", "tail", "ident") or "").strip().upper()
        if not address and not callsign:
            return None
        lat = self._float_or_none(self._first_value(payload, "lat", "latitude"))
        lon = self._float_or_none(self._first_value(payload, "lon", "longitude"))
        altitude = self._int_or_none(self._first_value(payload, "alt_baro", "altitude", "alt", "alt_geom"))
        speed = self._float_or_none(self._first_value(payload, "gs", "speed", "ground_speed", "velocity"))
        track = self._float_or_none(self._first_value(payload, "track", "heading", "course"))
        now = time.monotonic()
        row: dict[str, Any] = {
            "hex": address or ("~UAT" + callsign[-4:]),
            "flight": callsign,
            "source": "uat_978",
            "source_label": "978 UAT",
            "receiver_type": "uat_978",
            "seen": 0.0,
            "messages": 1,
            "_last_seen_monotonic": now,
        }
        if lat is not None and lon is not None:
            row["lat"] = lat
            row["lon"] = lon
            row["seen_pos"] = 0.0
        if altitude is not None:
            row["alt_baro"] = altitude
            row["alt_geom"] = altitude
        if speed is not None:
            row["gs"] = round(speed, 1)
        if track is not None:
            row["track"] = round(track, 1)
        return row

    def _collector_loop(self) -> None:
        while not self.stop_event.is_set() and self.is_running():
            try:
                with socket.create_connection(("127.0.0.1", UAT_JSON_PORT), timeout=2.0) as connection:
                    connection.settimeout(1.0)
                    stream = connection.makefile("r", encoding="utf-8", errors="replace")
                    while not self.stop_event.is_set() and self.is_running():
                        try:
                            line = stream.readline()
                        except socket.timeout:
                            continue
                        if not line:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            decoded = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        records = decoded if isinstance(decoded, list) else [decoded]
                        for record in records:
                            normalized = self._normalize_uat_record(record)
                            if not normalized:
                                continue
                            with self.aircraft_lock:
                                existing = self.aircraft_by_hex.get(str(normalized["hex"]).upper())
                                if existing:
                                    normalized["messages"] = int(existing.get("messages", 1)) + 1
                                    for field in ("lat", "lon", "seen_pos", "alt_baro", "alt_geom", "gs", "track", "flight"):
                                        if normalized.get(field) in (None, "") and existing.get(field) not in (None, ""):
                                            normalized[field] = existing[field]
                                self.aircraft_by_hex[str(normalized["hex"]).upper()] = normalized
                                self.message_count += 1
                                self.collector_error = None
            except Exception as exc:
                if not self.stop_event.is_set():
                    self.collector_error = str(exc)
                    time.sleep(0.75)

    def _start_collector(self) -> None:
        if self.collector_thread is not None and self.collector_thread.is_alive():
            return
        self.stop_event.clear()
        self.collector_thread = threading.Thread(target=self._collector_loop, name="uat978-json-collector", daemon=True)
        self.collector_thread.start()

    def _stop_collector(self) -> None:
        self.stop_event.set()
        if self.collector_thread is not None and self.collector_thread.is_alive():
            self.collector_thread.join(timeout=2.0)
        self.collector_thread = None

    def aircraft_payload(self) -> dict[str, Any]:
        now = time.monotonic()
        rows: list[dict[str, Any]] = []
        with self.aircraft_lock:
            for key in list(self.aircraft_by_hex.keys()):
                row = self.aircraft_by_hex[key]
                age = max(0.0, now - float(row.get("_last_seen_monotonic", now)))
                if age > UAT_AIRCRAFT_STALE_SECONDS:
                    self.aircraft_by_hex.pop(key, None)
                    continue
                public = {name: value for name, value in row.items() if not name.startswith("_")}
                public["seen"] = round(age, 1)
                if public.get("lat") is not None and public.get("lon") is not None:
                    public["seen_pos"] = round(age, 1)
                rows.append(public)
        return {
            "now": time.time(),
            "messages": self.message_count,
            "aircraft": rows,
            "source": "uat_978",
            "collector_running": self.collector_thread is not None and self.collector_thread.is_alive(),
            "collector_error": self.collector_error,
        }

    def _binary_candidates(self) -> list[Path]:
        return [
            self.root / "runtime" / "bin" / "dump978-fa",
            self.root / "bin" / "dump978-fa",
        ]

    def _dump978_path(self) -> str:
        for candidate in self._binary_candidates():
            if candidate.is_file() and os.access(candidate, os.X_OK):
                self.command_path = str(candidate)
                return str(candidate)
        raise RuntimeError("App-owned dump978-fa was not found. Run tools/pi5_install_app_owned_dump978.sh on the Pi.")

    @staticmethod
    def _tcp_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _command(self) -> list[str]:
        dump978 = self._dump978_path()
        return [
            dump978,
            "--sdr", f"driver=rtlsdr,serial={UAT_SERIAL}",
            "--sdr-gain", str(UAT_GAIN_DB),
            "--json-port", f"127.0.0.1:{UAT_JSON_PORT}",
            "--raw-port", f"127.0.0.1:{UAT_RAW_PORT}",
        ]

    def start(self) -> dict[str, Any]:
        with self.lock:
            if self.is_running():
                status = self.status()
                status.update({"started": False, "already_running": True})
                return status
            self.last_error = None
            command = self._command()
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_handle = self.log_path.open("a", encoding="utf-8", newline="\n")
            self.log_handle.write("\n--- starting dump978-fa UAT 978 manual API session ---\n")
            self.log_handle.write("command=" + " ".join(command) + "\n")
            self.log_handle.flush()
            self.process = subprocess.Popen(
                command,
                cwd=str(self.root),
                stdout=self.log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.started_at = time.time()
            deadline = time.time() + 6.0
            while time.time() < deadline:
                if self.process.poll() is not None:
                    self.last_error = f"dump978-fa exited during startup with code {self.process.returncode}; see {self.log_path}"
                    self._close_log_handle()
                    raise RuntimeError(self.last_error)
                if self._tcp_port_open("127.0.0.1", UAT_JSON_PORT):
                    self._start_collector()
                    status = self.status()
                    status.update({"started": True, "startup_verified": True})
                    return status
                time.sleep(0.25)
            if not self.is_running():
                self.last_error = f"dump978-fa did not remain running; see {self.log_path}"
                self._close_log_handle()
                raise RuntimeError(self.last_error)
            self._start_collector()
            status = self.status()
            status.update({
                "started": True,
                "startup_verified": False,
                "warning": f"dump978-fa is running but JSON port {UAT_JSON_PORT} did not accept a connection within startup window.",
            })
            return status

    def _close_log_handle(self) -> None:
        if self.log_handle is not None:
            try:
                self.log_handle.flush()
                self.log_handle.close()
            except OSError:
                pass
            self.log_handle = None

    def stop(self) -> dict[str, Any]:
        with self.lock:
            self._stop_collector()
            was_running = self.is_running()
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5.0)
            self.process = None
            self.started_at = None
            self._close_log_handle()
            status = self.status()
            status.update({"stopped": was_running, "already_stopped": not was_running})
            return status

    def status(self) -> dict[str, Any]:
        running = self.is_running()
        binary_available = any(candidate.is_file() and os.access(candidate, os.X_OK) for candidate in self._binary_candidates())
        uptime = int(time.time() - self.started_at) if running and self.started_at else 0
        json_open = self._tcp_port_open("127.0.0.1", UAT_JSON_PORT) if running else False
        raw_open = self._tcp_port_open("127.0.0.1", UAT_RAW_PORT) if running else False
        aircraft_payload = self.aircraft_payload() if running else {"aircraft": [], "messages": self.message_count}
        return {
            "available": binary_available,
            "manual_control_enabled": True,
            "persistent_enabled": False,
            "running": running,
            "serial": UAT_SERIAL,
            "frequency_hz": UAT_FREQUENCY_HZ,
            "gain_db": UAT_GAIN_DB,
            "decoder": self.command_path or str(self.root / "runtime" / "bin" / "dump978-fa"),
            "json_port": UAT_JSON_PORT,
            "raw_port": UAT_RAW_PORT,
            "json_port_open": json_open,
            "raw_port_open": raw_open,
            "uptime_seconds": uptime,
            "last_error": self.last_error,
            "log_path": str(self.log_path),
            "control_policy": "manual_api_only_no_autostart",
            "collector_running": self.collector_thread is not None and self.collector_thread.is_alive(),
            "collector_error": self.collector_error,
            "aircraft_count": len(aircraft_payload.get("aircraft", [])),
            "messages": int(aircraft_payload.get("messages", 0) or 0),
        }



class PiTrafficSourceSettings:
    """Persist operator-visible traffic source switches for the unified aircraft feed."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.path = traffic_source_settings_path(self.root)
        self.lock = threading.RLock()

    def load(self) -> dict[str, bool]:
        with self.lock:
            return load_traffic_source_settings(self.root)

    def save(self, payload: dict[str, Any]) -> dict[str, bool]:
        updates: dict[str, bool] = {}
        for key in DEFAULT_TRAFFIC_SOURCES:
            if key in payload:
                updates[key] = bool(payload[key])
        with self.lock:
            current = self.load()
            current.update(updates)
            return save_traffic_source_settings(self.root, current)

    def status(self) -> dict[str, Any]:
        current = self.load()
        return {
            "settings_path": str(self.path),
            "adsb_1090_enabled": bool(current.get("adsb_1090_enabled", True)),
            "uat_978_enabled": bool(current.get("uat_978_enabled", False)),
            "merge_policy": "enabled_sources_merged_into_api_aircraft_json",
            "ui_policy": "single_map_and_aircraft_list",
        }


def _source_key(aircraft: dict[str, Any]) -> str:
    value = str(aircraft.get("hex") or aircraft.get("flight") or "").strip().upper()
    if value:
        return value
    lat = aircraft.get("lat")
    lon = aircraft.get("lon")
    return f"NOHEX:{lat},{lon}"


def _aircraft_seen_value(aircraft: dict[str, Any]) -> float:
    for key in ("seen", "seen_pos"):
        try:
            return float(aircraft.get(key))
        except (TypeError, ValueError):
            continue
    return 9999.0


def _merge_aircraft_rows(target: dict[str, dict[str, Any]], row: dict[str, Any], source: str) -> None:
    normalized = dict(row)
    normalized["source"] = source
    normalized.setdefault("source_label", "1090 ADS-B" if source == "adsb_1090" else "978 UAT")
    normalized["sources"] = sorted(set([source] + list(normalized.get("sources", []) or [])))
    key = _source_key(normalized)
    if not key:
        return
    existing = target.get(key)
    if existing is None:
        target[key] = normalized
        return
    existing_sources = set(existing.get("sources", []) or [])
    existing_sources.add(source)
    existing["sources"] = sorted(existing_sources)
    existing["source"] = "+".join(existing["sources"])
    for field, value in normalized.items():
        if field in ("sources", "source"):
            continue
        if existing.get(field) in (None, "") and value not in (None, ""):
            existing[field] = value
    new_has_position = normalized.get("lat") is not None and normalized.get("lon") is not None
    old_has_position = existing.get("lat") is not None and existing.get("lon") is not None
    if new_has_position and (not old_has_position or _aircraft_seen_value(normalized) <= _aircraft_seen_value(existing)):
        for field in ("lat", "lon", "seen", "seen_pos", "alt_baro", "alt_geom", "gs", "track"):
            if normalized.get(field) is not None:
                existing[field] = normalized[field]


def patch_pi_traffic_source_handler(pi_port: Any) -> None:
    """Add persisted source switches and merge enabled sources into /api/aircraft.json."""
    handler = pi_port.PiPortHandler
    if getattr(handler, "_pi_air_traffic_source_controls_patched", False):
        return

    def uat_manager_for(request_handler: Any) -> PiUat978Manager:
        existing = getattr(request_handler.server, "uat_978_manager", None)
        if existing is not None:
            return existing
        root = getattr(getattr(request_handler.server, "manager", None), "root", Path.cwd())
        created = PiUat978Manager(Path(root))
        setattr(request_handler.server, "uat_978_manager", created)
        return created

    def traffic_settings_for(request_handler: Any) -> PiTrafficSourceSettings:
        existing = getattr(request_handler.server, "traffic_source_settings", None)
        if existing is not None:
            return existing
        root = getattr(getattr(request_handler.server, "manager", None), "root", Path.cwd())
        created = PiTrafficSourceSettings(Path(root))
        setattr(request_handler.server, "traffic_source_settings", created)
        return created

    original_status = handler.port_status
    original_get = handler.do_GET
    original_post = handler.do_POST

    def merged_aircraft_payload(self: Any) -> dict[str, Any]:
        settings = traffic_settings_for(self).load()
        adsb_enabled = bool(settings.get("adsb_1090_enabled", True))
        uat_enabled = bool(settings.get("uat_978_enabled", False))
        merged: dict[str, dict[str, Any]] = {}
        source_counts = {"adsb_1090": 0, "uat_978": 0}
        source_errors: dict[str, str] = {}
        total_messages = 0

        if adsb_enabled:
            try:
                if not self.manager.is_running():
                    self.manager.start()
                if self.manager.is_running():
                    adsb_payload = self.manager.query_aircraft()
                    total_messages += int(adsb_payload.get("messages", 0) or 0)
                    for row in adsb_payload.get("aircraft", []) or []:
                        if isinstance(row, dict):
                            _merge_aircraft_rows(merged, row, "adsb_1090")
                            source_counts["adsb_1090"] += 1
            except Exception as exc:
                source_errors["adsb_1090"] = str(exc)
        elif self.manager.is_running():
            try:
                self.manager.stop()
            except Exception as exc:
                source_errors["adsb_1090_stop"] = str(exc)

        if uat_enabled:
            uat_manager = uat_manager_for(self)
            try:
                if not uat_manager.is_running():
                    uat_manager.start()
                uat_payload = uat_manager.aircraft_payload()
                total_messages += int(uat_payload.get("messages", 0) or 0)
                for row in uat_payload.get("aircraft", []) or []:
                    if isinstance(row, dict):
                        _merge_aircraft_rows(merged, row, "uat_978")
                        source_counts["uat_978"] += 1
            except Exception as exc:
                source_errors["uat_978"] = str(exc)
        else:
            uat_manager = uat_manager_for(self)
            if uat_manager.is_running():
                try:
                    uat_manager.stop()
                except Exception as exc:
                    source_errors["uat_978_stop"] = str(exc)

        rows = sorted(
            merged.values(),
            key=lambda row: (_aircraft_seen_value(row), str(row.get("flight") or row.get("hex") or "")),
        )
        return {
            "now": time.time(),
            "messages": total_messages,
            "aircraft": rows,
            "source_enabled": {"adsb_1090": adsb_enabled, "uat_978": uat_enabled},
            "source_counts": source_counts,
            "source_errors": source_errors,
            "merge_policy": "enabled_sources_deduplicated_by_hex_prefer_fresh_position",
        }

    def traffic_status_payload(self: Any) -> dict[str, Any]:
        settings = traffic_settings_for(self).status()
        uat = uat_manager_for(self).status()
        adsb_status = {}
        try:
            adsb_status = self.manager.status()
        except Exception as exc:
            adsb_status = {"last_error": str(exc), "decoder": {"running": bool(self.manager.is_running())}}
        return {
            **settings,
            "adsb_1090": {
                "enabled": settings["adsb_1090_enabled"],
                "running": bool(self.manager.is_running()),
                "serial": ADSB_SERIAL,
                "frequency_hz": 1090000000,
                "decoder": adsb_status.get("decoder", {}),
            },
            "uat_978": {**uat, "enabled": settings["uat_978_enabled"]},
        }

    def port_status_with_sources(self: Any) -> dict[str, Any]:
        payload = original_status(self)
        try:
            payload["traffic_sources"] = traffic_status_payload(self)
        except Exception as exc:
            payload["traffic_sources"] = {"error": str(exc)}
        return payload

    def apply_traffic_settings(self: Any, payload: dict[str, Any]) -> dict[str, Any]:
        settings = traffic_settings_for(self).save(payload)
        errors: dict[str, str] = {}
        if bool(settings.get("adsb_1090_enabled", True)):
            try:
                self.manager.start()
            except Exception as exc:
                errors["adsb_1090"] = str(exc)
        else:
            try:
                self.manager.stop()
            except Exception as exc:
                errors["adsb_1090_stop"] = str(exc)
        uat_manager = uat_manager_for(self)
        if bool(settings.get("uat_978_enabled", False)):
            try:
                uat_manager.start()
            except Exception as exc:
                errors["uat_978"] = str(exc)
        else:
            try:
                uat_manager.stop()
            except Exception as exc:
                errors["uat_978_stop"] = str(exc)
        result = traffic_status_payload(self)
        result["saved"] = True
        result["apply_errors"] = errors
        return result

    def do_get_with_sources(self: Any) -> None:
        request = urlparse(self.path)
        if request.path == "/api/settings/traffic-sources":
            self.send_json(traffic_status_payload(self))
            return
        if request.path == "/api/aircraft.json":
            self.send_json(merged_aircraft_payload(self))
            return
        original_get(self)

    def do_post_with_sources(self: Any) -> None:
        request = urlparse(self.path)
        try:
            if request.path == "/api/settings/traffic-sources":
                self.send_json(apply_traffic_settings(self, self.read_json()))
                return
            if request.path == "/api/adsb/start":
                self.send_json(apply_traffic_settings(self, {"adsb_1090_enabled": True}))
                return
            if request.path == "/api/adsb/stop":
                self.send_json(apply_traffic_settings(self, {"adsb_1090_enabled": False}))
                return
        except Exception as exc:
            LOG.exception("Traffic source API request failed")
            self.send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
            return
        original_post(self)

    handler.port_status = port_status_with_sources
    handler.do_GET = do_get_with_sources
    handler.do_POST = do_post_with_sources
    setattr(handler, "_pi_air_traffic_source_controls_patched", True)


def patch_pi_port_handler_status(pi_port: Any) -> None:
    """Expose Pi serial receiver ownership through inherited /api/status.

    The ported Windows/Pi handler owns the /api/status route and returns the
    legacy UI status shape.  The Pi backend shim owns the receiver-role and
    app-owned readsb contract, so enrich the inherited status response here
    instead of modifying the shared port baseline module.
    """
    original_port_status = pi_port.PiPortHandler.port_status
    if getattr(original_port_status, "_pi_air_traffic_roles_enriched", False):
        return

    def pi_air_traffic_port_status(self: Any) -> dict[str, Any]:
        payload = original_port_status(self)
        if not isinstance(payload, dict):
            payload = {}

        roles = getattr(self.manager, "roles", None)
        if not roles:
            try:
                roles = self.manager.resolve_roles()
            except Exception as exc:  # Keep /api/status available for diagnostics.
                roles = {"ok": False, "error": str(exc)}
        payload["receiver_roles"] = roles

        try:
            manager_status = self.manager.status()
            if isinstance(manager_status, dict):
                decoder = manager_status.get("decoder")
                if isinstance(decoder, dict):
                    payload["decoder"] = decoder
                payload["last_error"] = manager_status.get("last_error")
        except Exception as exc:  # Keep the legacy status usable even if enrichment fails.
            payload.setdefault("decoder", {
                "running": bool(self.manager.is_running()),
                "json_ready": bool(payload.get("readsb_json_available")),
                "query_error": str(exc),
            })
            payload.setdefault("last_error", str(exc))

        payload["pi_backend"] = {
            "serial_contract": {
                "adsb_1090": ADSB_SERIAL,
                "noaa_airband": AUDIO_SERIAL,
                "uat_978": UAT_SERIAL,
            },
            "readsb_command": getattr(self.manager, "readsb_command_path", None) or "readsb",
            "status_enrichment": "pi_shim_receiver_roles_decoder",
        }
        return payload

    setattr(pi_air_traffic_port_status, "_pi_air_traffic_roles_enriched", True)
    pi_port.PiPortHandler.port_status = pi_air_traffic_port_status



def patch_pi_uat_handler(pi_port: Any) -> None:
    """Add manual UAT 978 status/start/stop endpoints to the Pi-port handler."""
    handler = pi_port.PiPortHandler
    if getattr(handler, "_pi_air_traffic_uat_controls_patched", False):
        return

    def uat_manager_for(request_handler: Any) -> PiUat978Manager:
        existing = getattr(request_handler.server, "uat_978_manager", None)
        if existing is not None:
            return existing
        root = getattr(getattr(request_handler.server, "manager", None), "root", Path.cwd())
        created = PiUat978Manager(Path(root))
        setattr(request_handler.server, "uat_978_manager", created)
        return created

    original_status = handler.port_status
    original_get = handler.do_GET
    original_post = handler.do_POST

    def port_status_with_uat(self: Any) -> dict[str, Any]:
        payload = original_status(self)
        try:
            payload["uat_978"] = uat_manager_for(self).status()
        except Exception as exc:
            payload["uat_978"] = {
                "available": False,
                "manual_control_enabled": True,
                "persistent_enabled": False,
                "running": False,
                "serial": UAT_SERIAL,
                "frequency_hz": UAT_FREQUENCY_HZ,
                "last_error": str(exc),
            }
        return payload

    def do_get_with_uat(self: Any) -> None:
        request = urlparse(self.path)
        if request.path in ("/api/uat/status", "/api/uat/status.json"):
            self.send_json(uat_manager_for(self).status())
            return
        original_get(self)

    def do_post_with_uat(self: Any) -> None:
        request = urlparse(self.path)
        try:
            if request.path == "/api/uat/start":
                self.send_json(uat_manager_for(self).start())
                return
            if request.path == "/api/uat/stop":
                self.send_json(uat_manager_for(self).stop())
                return
        except Exception as exc:
            LOG.exception("UAT API request failed")
            self.send_json({"error": str(exc), "uat_978": uat_manager_for(self).status()}, HTTPStatus.CONFLICT)
            return
        original_post(self)

    handler.port_status = port_status_with_uat
    handler.do_GET = do_get_with_uat
    handler.do_POST = do_post_with_uat
    setattr(handler, "_pi_air_traffic_uat_controls_patched", True)


def main() -> int:
    # Import after patching rtl_windows_backend globals so the Pi port module gets
    # the Pi serial constants and Linux path handler in its module-level imports.
    import rtl_windows_pi_port_backend as pi_port

    pi_port.DecoderManager = PiSerialDecoderManager
    pi_port.ADSB_SERIAL = ADSB_SERIAL
    pi_port.AUDIO_SERIAL = AUDIO_SERIAL
    pi_port.windows_path = linux_path
    patch_pi_port_handler_status(pi_port)
    patch_pi_uat_handler(pi_port)
    patch_pi_traffic_source_handler(pi_port)
    return pi_port.main()


if __name__ == "__main__":
    raise SystemExit(main())
