# Pi Live Functional Validation

This milestone validates the running Raspberry Pi 5 FlyCatcher/NESDR service after the backend, app-owned readsb, and systemd service are installed.

## Purpose

The validator checks the live service without changing receiver settings or starting long-running scans. It confirms that the UI loads, the Pi-specific `/api/status` contract is present, ADS-B JSON is readable, NOAA capture works, and passive Airband API endpoints respond.

## Run on the Pi

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_validate_live_functional.sh
```

## Run against a remote Pi

From another machine that has the repository checked out and can reach the Pi:

```bash
PI_AIR_TRAFFIC_HOST=192.168.254.63 ./tools/pi5_validate_live_functional.sh
```

Optional environment variables:

```bash
PI_AIR_TRAFFIC_PORT=8090
PI_AIR_TRAFFIC_OBSERVE_SECONDS=30
PI_AIR_TRAFFIC_NOAA_SECONDS=2
```

## PASS/WARN interpretation

Hard service, API, receiver-role, decoder-running, asset, aircraft JSON, NOAA capture, and passive Airband endpoint failures are reported as `FAIL`.

ADS-B message growth is reported as `WARN` instead of `FAIL` when the decoder is running and JSON is available but RF conditions are quiet during the observation window. This prevents a healthy bench or indoor test from blocking the milestone while still surfacing RF-performance evidence.

Reports are written under `runtime/preflight/`.
