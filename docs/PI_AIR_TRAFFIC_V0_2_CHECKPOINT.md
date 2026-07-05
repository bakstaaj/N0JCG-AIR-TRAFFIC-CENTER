# PI Air Traffic Tracker — V0.2 Validated Checkpoint

Date: 2026-07-04
Branch: `feature/initial-windows-to-pi-port`
Checkpoint tag target: `v0.2.0`
Checkpoint source head at doc generation: `0a1e7ba2d96d75133558cc25faac3ea90a6ec92d`
Acceptance report: `runtime/preflight/pi5_v0_2_acceptance_20260704_172324.txt`
Acceptance result: `39 PASS, 2 WARN, 0 FAIL`, `FINAL: PASS`

## Scope

V0.2 validates the 978 MHz UAT capability path and integrates it into the existing PI Air Traffic Tracker aircraft experience. The design keeps 1090 ADS-B and 978 UAT as traffic sources feeding one aircraft map, one aircraft list, and the same aircraft detail workflow.

## Hardware contract

| Source | Use | RTL serial | V0.2 state |
|---|---|---:|---|
| 1090 ADS-B | 1090 MHz traffic | `00001090` | enabled by default |
| NOAA/Airband | audio/scanner receiver | `00000162` | retained from V0.1 |
| 978 UAT | 978 MHz traffic | `00000978` | optional source switch |

Linux RTL indexes are not authoritative. The app must continue to use stable RTL EEPROM serial ownership.

## Validated functionality

- App-owned `dump978-fa` decoder tooling is available under `runtime/bin`.
- 978 UAT receiver capability validates against serial `00000978`.
- Manual UAT API controls are available at `/api/uat/status`, `/api/uat/start`, and `/api/uat/stop`.
- Traffic-source settings are available at `/api/settings/traffic-sources`.
- The Configuration menu provides switches for 1090 ADS-B and 978 UAT.
- The existing `/api/aircraft.json` endpoint is the unified aircraft feed.
- Aircraft from enabled sources are presented in the same map, table, and aircraft-detail UI.
- UI refresh/polling pauses while the configuration menu is open, preventing switch interaction from being disrupted.
- Idle UAT collector socket timeouts are non-fatal and should not be surfaced as `cannot read from timed out object`.
- Zero 978 UAT aircraft is acceptable when no local UAT traffic is present.

## Final acceptance evidence

`tools/pi5_validate_v0_2_acceptance.sh` passed on the Pi:

```text
Summary: 39 PASS, 2 WARN, 0 FAIL
Report path: runtime/preflight/pi5_v0_2_acceptance_20260704_172324.txt
Work dir: runtime/preflight/v0_2_acceptance_20260704_172324
FINAL: PASS
```

## Validation commands

Run from the Pi repository root:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
git pull --ff-only --tags
sudo systemctl restart pi-air-traffic-tracker.service
./tools/pi5_validate_v0_2_acceptance.sh
```

Optional V0.1 baseline inside the V0.2 chain:

```bash
RUN_V0_1_BASELINE=1 ./tools/pi5_validate_v0_2_acceptance.sh
```

## Checkpoint policy

This checkpoint should be tagged as `v0.2.0` after the docs are committed. If the tag already exists, do not delete or rewrite it without explicit operator approval.
