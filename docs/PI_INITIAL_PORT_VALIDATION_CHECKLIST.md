# Pi Initial Port Validation Checklist

Use this checklist to confirm a fresh Raspberry Pi 5 installation has reached the V0.1 initial-port baseline.

## Hardware

- [ ] Raspberry Pi 5 running Raspberry Pi OS / Debian Trixie Full.
- [ ] Nooelec FlyCatcher HAT connected.
- [ ] Nooelec NESDR Nano2+ connected.
- [ ] ADS-B antenna attached to FlyCatcher ADS-B side.
- [ ] NOAA/Airband antenna attached to NESDR Nano2+.

## Expected RTL serial map

| Role | Expected serial |
| --- | --- |
| ADS-B 1090 | `00001090` |
| NOAA/Airband | `00000162` |
| UAT 978 | `00000978` |

Run:

```bash
./tools/pi5_flycatcher_preflight.sh
```

Expected result: `FINAL: PASS`.

## Runtime dependency setup

Run:

```bash
./tools/pi5_install_runtime_dependencies.sh
./tools/pi5_install_app_owned_readsb.sh
```

Expected result: app-owned `runtime/bin/readsb` exists and supports `--device-type rtlsdr`.

## Service setup

Run:

```bash
sudo ./tools/pi5_install_systemd_service.sh
./tools/pi5_validate_systemd_service.sh
```

Expected result: service active, LAN URL displayed, and `FINAL: PASS`.

## ADS-B validation

Run:

```bash
./tools/pi5_validate_backend_serial_startup.sh
./tools/pi5_validate_readsb_fresh_start.sh
./tools/pi5_validate_live_functional.sh
```

Expected results:

- `/api/status` reports `receiver_roles.adsb.serial = 00001090`.
- Decoder reports running.
- `readsb` command path points to `runtime/bin/readsb`.
- ADS-B messages increase during the observation window.

## UI and API validation

Run:

```bash
./tools/pi5_validate_ui_api_smoke.sh
```

Expected results:

- UI root loads.
- `/app.js` loads.
- `/app.css` loads.
- `/api/status` and `/api/aircraft.json` respond.

## NOAA and Airband validation

Run:

```bash
./tools/pi5_validate_active_noaa_airband.sh
```

Expected results:

- NOAA live start succeeds.
- NOAA live audio endpoint returns a WAV payload.
- NOAA live stop succeeds.
- Airband fast-spectrum scanner starts and stops cleanly.

Warnings about no live Airband transmission are acceptable if no AM traffic is captured during the test window.

## Optional FAA catalog validation

Copy the FAA NASR FRQ CSV ZIP to the Pi and run:

```bash
./tools/pi5_import_faa_airband_catalog.sh /path/to/FAA_NASR_*_FRQ_CSV.zip
./tools/pi5_validate_airband_catalog.sh
```

Expected result: nearby Airband channel list is populated for the configured receiver location/radius.

## Browser access

Open from another LAN machine:

```text
http://<pi-lan-ip>:8090
```

For the current validated bench address:

```text
http://192.168.254.63:8090
```
