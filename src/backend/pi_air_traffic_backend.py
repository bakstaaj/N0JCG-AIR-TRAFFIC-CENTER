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
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any
from urllib.error import URLError

import rtl_windows_backend as win_backend

ADSB_SERIAL = os.environ.get("PI_AIR_TRAFFIC_ADSB_SERIAL", "00001090")
AUDIO_SERIAL = os.environ.get("PI_AIR_TRAFFIC_AUDIO_SERIAL", "00000162")
UAT_SERIAL = os.environ.get("PI_AIR_TRAFFIC_UAT_SERIAL", "00000978")

LOG = logging.getLogger("pi_air_traffic_backend")
RTL_TEST_DEVICE_RE = re.compile(r"^\s*(\d+):\s*([^,]+),\s*([^,]+),\s*SN:\s*(\S+)\s*$")


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
        if self.process is not None and self.process.poll() is None:
            return True
        try:
            payload = self.query_aircraft(timeout=0.75)
            return isinstance(payload, dict) and isinstance(payload.get("aircraft"), list)
        except Exception:
            return False

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


def main() -> int:
    # Import after patching rtl_windows_backend globals so the Pi port module gets
    # the Pi serial constants and Linux path handler in its module-level imports.
    import rtl_windows_pi_port_backend as pi_port

    pi_port.DecoderManager = PiSerialDecoderManager
    pi_port.ADSB_SERIAL = ADSB_SERIAL
    pi_port.AUDIO_SERIAL = AUDIO_SERIAL
    pi_port.windows_path = linux_path
    patch_pi_port_handler_status(pi_port)
    return pi_port.main()


if __name__ == "__main__":
    raise SystemExit(main())
