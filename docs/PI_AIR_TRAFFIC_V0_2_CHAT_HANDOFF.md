# PI Air Traffic Tracker — V0.2 Chat Handoff

Date: 2026-07-04
Project: `PI-AIR-TRAFFIC-TRACKER`
Branch: `feature/initial-windows-to-pi-port`
Validated checkpoint target: `v0.2.0`
Last known validated Git head from Pi acceptance: `c0c44ab777ca7a8aaf29b9b964baed31b17749ca`
Acceptance report: `runtime/preflight/pi5_v0_2_acceptance_20260704_172324.txt`
Acceptance result: `39 PASS, 2 WARN, 0 FAIL`, `FINAL: PASS`

## Hardware and runtime context

The Pi target is a Raspberry Pi 5 running the PI Air Traffic Tracker backend and UI on port `8090`. The current Pi host used during validation was `192.168.254.63`, with local service checks using `http://127.0.0.1:8090`.

Stable SDR serial ownership:

| Purpose | Frequency/use | RTL serial | State |
|---|---:|---:|---|
| 1090 ADS-B | 1090 MHz | `00001090` | enabled by default |
| NOAA/Airband | NOAA + airband audio/scanning | `00000162` | active support retained |
| 978 UAT | 978 MHz | `00000978` | V0.2 optional traffic source |

Receiver location currently used by the app:

```text
Name: Gilbert receiver
Latitude: 33.257494
Longitude: -111.753273
Airband radius: 100 miles
NOAA frequency: 162.500 MHz
Airband default mode: fast_spectrum
```

## V0.2 validated capabilities

V0.2 adds the 978 MHz UAT capability path and unifies traffic presentation with the existing 1090 ADS-B aircraft UI.

Validated features:

- App-owned `dump978-fa` tooling installed under `runtime/bin/dump978-fa`.
- UAT 978 hardware path validates against RTL serial `00000978`.
- Manual UAT backend API controls are available:
  - `GET /api/uat/status`
  - `POST /api/uat/start`
  - `POST /api/uat/stop`
- Traffic source settings are available:
  - `GET /api/settings/traffic-sources`
  - `POST /api/settings/traffic-sources`
- Configuration menu includes traffic source switches:
  - `1090 MHz ADS-B`
  - `978 MHz UAT`
- Unified aircraft feed is exposed through the existing endpoint:
  - `GET /api/aircraft.json`
- Enabled traffic sources merge into the same aircraft map, table, and aircraft detail workflow.
- UI refresh pauses while the configuration drawer/menu is open so switches are easier to operate.
- UAT collector idle socket timeouts are treated as non-fatal idle/no-data behavior.
- Zero live 978 UAT aircraft is acceptable when no local 978 traffic is present.

## Acceptance result

The V0.2 top-level acceptance validator passed on the Pi:

```text
Summary: 39 PASS, 2 WARN, 0 FAIL
Report path: runtime/preflight/pi5_v0_2_acceptance_20260704_172324.txt
Work dir: runtime/preflight/v0_2_acceptance_20260704_172324
FINAL: PASS
```

The two warnings were acceptable for the milestone. The important result is zero failures and a confirmed `FINAL: PASS`.

## Important operational note

With `1090 ADS-B` off and `978 UAT` on, the unified feed may show zero aircraft if no 978 MHz UAT aircraft are being received. That is valid. The pass condition is that UAT is running, the collector remains healthy, and `/api/aircraft.json` stays valid.

Known good UI status pattern for quiet UAT:

```text
Unified aircraft feed: 1090 off · UAT on / running
UAT aircraft count: 0 accepted when no live UAT traffic is present
No collector error: cannot read from timed out object
```

## Validation scripts available

Run from the Pi repo root:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
sudo systemctl restart pi-air-traffic-tracker.service
./tools/pi5_validate_v0_2_acceptance.sh
```

Supporting validators:

```text
tools/pi5_validate_v0_1_acceptance.sh
tools/pi5_validate_uat_978_capability.sh
tools/pi5_validate_uat_decoder_tooling.sh
tools/pi5_validate_uat_backend_api.sh
tools/pi5_validate_traffic_source_ui_merge.sh
tools/pi5_validate_v0_2_acceptance.sh
```

Optional full baseline chain:

```bash
RUN_V0_1_BASELINE=1 ./tools/pi5_validate_v0_2_acceptance.sh
```

## Current Git workflow expectations

Development machine:

```text
Windows 11
MSYS2 UCRT64
Workspace: ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
Preferred handoff: single downloadable .sh scripts
```

Use scripts instead of long manual command sequences. Scripts should validate with PASS/WARN/FAIL and avoid treating unrelated untracked report files as fatal.

## Suggested next steps

1. Create and push the V0.2 checkpoint/tag if not already done.
2. Start the next chat from this handoff file.
3. In the next chat, continue from validated V0.2 and decide whether V0.3 should focus on:
   - richer UAT display metadata,
   - UAT persistence/autostart policy,
   - better map source labeling,
   - release cleanup/documentation,
   - or field testing near live 978 UAT traffic.

## Do not regress these V0.2 guardrails

- Do not split 1090 and 978 aircraft into separate UIs.
- Keep `/api/aircraft.json` as the unified aircraft feed.
- Keep traffic source switches in the Configuration menu.
- Pause UI polling/refresh while the menu is open.
- Treat idle UAT collector socket/read timeouts as non-fatal.
- Accept zero 978 aircraft when no live UAT traffic exists.
- Use RTL serials, not Linux RTL index numbers, for receiver ownership.
