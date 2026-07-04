# V0.1 Pi Initial Port Validation Evidence

This checkpoint records the validated Raspberry Pi 5 initial port state after live hardware testing on the Pi service.

## Validated hardware/runtime

- Raspberry Pi 5 running Raspberry Pi OS / Debian Trixie full.
- Nooelec FlyCatcher HAT ADS-B receiver on RTL serial `00001090`.
- Nooelec NESDR Nano2+ NOAA/Airband receiver on RTL serial `00000162`.
- FlyCatcher UAT side on RTL serial `00000978`, detected and reserved for a later milestone.
- App-owned `runtime/bin/readsb` launched by `pi-air-traffic-tracker.service`.
- Web/API service listening on port `8090`.

## Validation results captured on 2026-07-04

| Validator | Result | Evidence summary |
| --- | --- | --- |
| `tools/pi5_validate_readsb_fresh_start.sh` | PASS | `17 PASS, 0 WARN, 0 FAIL`; stale `aircraft.json` sentinel was replaced and ADS-B messages increased from `0 -> 281`. |
| `tools/pi5_validate_live_functional.sh` | PASS | `21 PASS, 0 WARN, 0 FAIL`; UI assets loaded, `/api/status` contract passed, ADS-B aircraft list returned, messages increased, NOAA capture returned WAV audio, Airband passive endpoints responded. |
| `tools/pi5_validate_active_noaa_airband.sh` | PASS | `22 PASS, 2 WARN, 0 FAIL`; NOAA live start/stop and WAV chunks passed; Airband fast-spectrum scanner started, held a live channel, returned live WAV audio, skip worked, best-audio returned WAV, and the final state returned to idle. |

## Closed issues in this checkpoint

- The backend no longer treats a stale readable `aircraft.json` as proof that ADS-B decoding is running.
- `/api/status` readiness checks are hardened against service startup races.
- Active NOAA and Airband validation waits for the service to be ready before exercising endpoints.
- Airband fast-spectrum validation no longer requires the optional FAA catalog.
- Recoverable Airband candidate-capture misses are reported as warnings instead of fatal scanner errors.
- Release/tag finalization must not force-move existing tags; if a primary release tag already points elsewhere, create a successor validated tag.

## Known warnings / optional follow-up

- The FAA NASR FRQ catalog remains optional for fast-spectrum scanning. Importing the catalog enables nearby-channel listing and traditional catalog-guided scanning.
- Live Airband detection depends on RF activity during the validation window; no-hit cases should warn, not fail, when scanner start/stop and final idle cleanup pass.
