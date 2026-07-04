# V0.1 Initial Raspberry Pi Port Checkpoint

## Release purpose

This checkpoint captures the first working Raspberry Pi 5 port of the air traffic tracker application. The goal of this checkpoint is not feature-complete parity with every future Pi capability; it is a stable baseline proving that the Windows UI/API surface can run on Raspberry Pi 5 with Pi-native SDR ownership, decoder startup, systemd service management, ADS-B live data, NOAA audio, and Airband scanner control.

## Validated hardware

| Role | Hardware | Serial | Status |
| --- | --- | --- | --- |
| ADS-B 1090 | Nooelec FlyCatcher ADS-B side | `00001090` | Validated |
| NOAA/Airband | Nooelec NESDR Nano2+ | `00000162` | Validated |
| UAT 978 | Nooelec FlyCatcher UAT side | `00000978` | Detected, reserved |

## Validated runtime behavior

- Linux RTL-SDR runtime indexes are resolved from EEPROM serials at backend startup.
- App-owned RTL-SDR-enabled `readsb` is used instead of trusting distro `readsb`.
- `readsb` launches through the Pi backend and writes `runtime/settings/readsb-json/aircraft.json`.
- Stale `aircraft.json` no longer prevents `readsb` from launching after service restart.
- `/api/status` exposes receiver roles, decoder state, and app-owned `readsb` command path.
- Browser UI loads from the systemd service on port 8090.
- ADS-B aircraft JSON is served through `/api/aircraft.json`.
- ADS-B messages increase during live validation.
- NOAA capture and live WAV chunk endpoints work through the shared audio receiver.
- Airband fast-spectrum scanner starts, transitions into active scanning, and stops cleanly.

## Validated service

The validated service unit is:

```text
pi-air-traffic-tracker.service
```

The service runs:

```text
src/backend/pi_air_traffic_backend.py --host 0.0.0.0 --port 8090 --autostart
```

## Required validation commands

Run from the Pi repo root:

```bash
./tools/pi5_validate_systemd_service.sh
./tools/pi5_validate_ui_api_smoke.sh
./tools/pi5_validate_backend_serial_startup.sh
./tools/pi5_validate_readsb_fresh_start.sh
./tools/pi5_validate_live_functional.sh
./tools/pi5_validate_active_noaa_airband.sh
```

Expected result: each command ends with `FINAL: PASS`. Airband live-hit warnings are acceptable when no civil AM transmission is captured during the test window.

## Optional FAA catalog flow

Traditional nearby-channel Airband scanning depends on the runtime FAA catalog:

```bash
./tools/pi5_import_faa_airband_catalog.sh /path/to/FAA_NASR_*_FRQ_CSV.zip
./tools/pi5_validate_airband_catalog.sh
```

The generated file is runtime data:

```text
runtime/settings/faa_airband_catalog.json
```

It is intentionally not tracked in Git.

## Known follow-on milestones

- Import or update FAA NASR FRQ catalog automatically or document a stable download source.
- Validate traditional catalog-based Airband scanning after catalog import.
- Improve UI messages when the FAA catalog is missing but fast-spectrum scanning is still available.
- Add UAT 978 support using FlyCatcher UAT radio.
- Rename inherited `rtl_windows_*` service labels/log text where appropriate for final Pi branding.
- Continue porting any remaining Windows-specific baseline diagnostics to Pi-native equivalents.
