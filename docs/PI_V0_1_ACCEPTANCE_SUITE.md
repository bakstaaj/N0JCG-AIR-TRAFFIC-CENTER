# Pi V0.1 Acceptance Suite

`tools/pi5_validate_v0_1_acceptance.sh` is the one-command hardware acceptance runner for the V0.1 Pi initial-port checkpoint.

It runs the required validators that proved the current Raspberry Pi 5 + FlyCatcher/NESDR runtime:

1. `tools/pi5_validate_systemd_service.sh`
2. `tools/pi5_validate_readsb_fresh_start.sh`
3. `tools/pi5_validate_live_functional.sh`
4. `tools/pi5_validate_active_noaa_airband.sh`

The suite writes a single top-level report under `runtime/preflight/` and stores each child validator output in a timestamped work directory.

## Required V0.1 behavior

The suite requires all of these paths to return `FINAL: PASS`:

- systemd service starts and serves the UI/API on port 8090;
- ADS-B launches app-owned `runtime/bin/readsb` from serial `00001090`;
- stale `aircraft.json` does not suppress decoder startup;
- `/api/status`, `/api/aircraft.json`, `/app.js`, `/app.css`, NOAA capture, and passive Airband endpoints work;
- NOAA live start/stop and WAV chunk streaming work;
- Airband active scan starts, reaches an active/searching state, stops cleanly, and restores tuning.

## Optional FAA catalog

The FAA NASR FRQ catalog is optional for V0.1 because fast-spectrum Airband scanning can validate unlisted frequencies without catalog data. If `runtime/settings/faa_airband_catalog.json` exists, the acceptance runner also executes `tools/pi5_validate_airband_catalog.sh`. If it is absent, the suite emits a warning instead of failing.

Traditional nearby-channel scanning still requires importing the FAA FRQ CSV ZIP with:

```bash
./tools/pi5_import_faa_airband_catalog.sh /path/to/FAA_NASR_*_FRQ_CSV.zip
```

## Usage on the Pi

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
git pull --ff-only --tags
./tools/pi5_validate_v0_1_acceptance.sh
```

A clean V0.1 acceptance run ends with:

```text
FINAL: PASS
```
