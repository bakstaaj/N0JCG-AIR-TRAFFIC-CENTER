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


## Menu refresh pause

The Configuration drawer is an operator edit surface. Browser status, aircraft, and operations polling pauses while the menu drawer is open, then refreshes once after the drawer closes. This prevents the 2-second refresh loop from fighting checkbox changes while enabling or disabling 1090 ADS-B and 978 UAT.

## UAT idle collector timeout handling

The dump978 JSON collector treats idle socket/readline timeouts, including Python's `cannot read from timed out object`, as no-data-yet rather than a collector error. Live 978 traffic may be absent, but an idle collector should stay healthy and show zero UAT aircraft instead of surfacing timeout noise.
