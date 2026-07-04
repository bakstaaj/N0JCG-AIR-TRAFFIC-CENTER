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
                    status = self.status()
                    status.update({"started": True, "startup_verified": True})
                    return status
                time.sleep(0.25)
            if not self.is_running():
                self.last_error = f"dump978-fa did not remain running; see {self.log_path}"
                self._close_log_handle()
                raise RuntimeError(self.last_error)
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
    return pi_port.main()


if __name__ == "__main__":
    raise SystemExit(main())
