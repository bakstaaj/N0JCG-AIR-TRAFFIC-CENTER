# Pi readsb stale JSON startup fix

## Problem

The Pi backend previously treated any readable `runtime/settings/readsb-json/aircraft.json` as evidence that ADS-B decoding was running.
After a restart, stale JSON could remain on disk, causing startup to skip launching app-owned `readsb` while `/api/status` still looked superficially healthy.

## Fix

The Pi backend now treats only its backend-owned child process as decoder liveness for startup gating.
Stale JSON can still be read for telemetry, but it cannot prevent `runtime/bin/readsb` from launching.

## Validation

`tools/pi5_validate_readsb_fresh_start.sh` intentionally stops the service, writes a stale JSON sentinel with `messages=3`, restarts the service, waits until `/api/status` exposes the Pi ADS-B decoder contract, verifies the app-owned `readsb` process is running for serial `00001090`, confirms `aircraft.json` was refreshed, and observes ADS-B message counts.

The validator has a robust `/api/status` readiness loop. It does not parse empty or transient responses as final failures; it retries until the Pi serial-role and decoder contract is available or the timeout expires.
