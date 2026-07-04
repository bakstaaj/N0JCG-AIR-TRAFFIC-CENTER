# V0.2 Traffic Source UI and Unified Aircraft Feed

This milestone adds operator-visible traffic source controls while keeping the main aircraft experience unified.

## Controls

The Configuration menu now includes Traffic Sources:

- 1090 MHz ADS-B
- 978 MHz UAT

The switch state persists in `runtime/settings/traffic_sources.json`.

## Unified display contract

The browser continues to poll `/api/aircraft.json`. The backend now merges enabled aircraft sources into that same payload instead of requiring a separate UAT map or list.

Merge rules:

- ADS-B 1090 and UAT 978 records are deduplicated primarily by ICAO hex.
- The freshest positioned record wins for map position fields.
- Source attribution is preserved with `source`, `source_label`, and `sources` fields.
- The existing map, active aircraft list, trail history, and aircraft detail dialog remain the primary UI.

## Runtime policy

- ADS-B 1090 remains enabled by default.
- UAT 978 remains disabled by default until the operator turns it on.
- UAT still uses app-owned `runtime/bin/dump978-fa`.
- No separate persistent systemd service is introduced for UAT in this milestone.
