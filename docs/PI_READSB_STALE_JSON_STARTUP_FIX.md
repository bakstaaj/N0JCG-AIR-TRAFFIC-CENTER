# Pi readsb stale JSON startup fix

## Problem

The Pi service can leave `runtime/settings/readsb-json/aircraft.json` behind after a stop or restart. The backend previously treated any readable `aircraft.json` as proof that the decoder was running. That allowed `/api/status` to report a running decoder even though no backend-owned `readsb` process had been launched, leaving ADS-B message counts frozen.

## Evidence

A direct `rtl_adsb -d 2` probe showed live ADS-B frames from FlyCatcher serial `00001090`. Direct app-owned `readsb` probes using serial `00001090` also produced hundreds of messages and aircraft in short runs. The service runtime JSON, however, remained at the old message count, which pointed to stale JSON startup gating rather than RF or hardware failure.

## Fix

`PiSerialDecoderManager.is_running()` now reports liveness only when the backend-owned child process exists and is still alive. Status code may still read `aircraft.json` for telemetry, but startup logic must not skip `readsb` launch because a stale JSON file exists.

## Validation

Run:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
git pull --ff-only
./tools/pi5_validate_readsb_fresh_start.sh
./tools/pi5_validate_live_functional.sh
```

The fresh-start validator stops the service, writes a stale JSON sentinel, restarts the service, and confirms that app-owned `runtime/bin/readsb` starts for serial `00001090`.
