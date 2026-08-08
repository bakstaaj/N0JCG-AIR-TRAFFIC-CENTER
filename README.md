# N0JCG AIR TRAFFIC CENTER

**N0JCG Air Traffic Center** is an Open Radio Platform application for Raspberry Pi 5 aircraft tracking, aviation monitoring, weather radar, and receive-only aviation audio.

It is part of the N0JCG product family and follows the shared N0JCG interface system: Engineering Navy, Platform Blue, Signal Cyan, Instrument Slate, Inter body text, Orbitron display accents, and explicit operator state.

The standalone repository is published as `N0JCG-AIR-TRAFFIC-CENTER`. It is the Raspberry Pi port of `bakstaaj/RTL-WINDOWS-ADS-B-TRACKER`, adapted for a Pi-native Linux runtime. Existing `PI-AIR-TRAFFIC-TRACKER` checkout paths and runtime identifiers remain supported for compatibility.

## Project boundary

This repository is the standalone source of truth for the Air Traffic Center application. The N0JCG ROC repository may host a namespaced deployment for testing, but it does not replace this source repository or its API/runtime compatibility identifiers.

The public product name is **N0JCG Air Traffic Center**. The canonical GitHub repository is [bakstaaj/N0JCG-AIR-TRAFFIC-CENTER](https://github.com/bakstaaj/N0JCG-AIR-TRAFFIC-CENTER). Internal names such as `PI-AIR-TRAFFIC-TRACKER`, `pi-air-traffic-tracker.service`, and the existing API routes remain stable for compatibility.

## Documentation and validation

- [Air Traffic Center user guide](docs/PI_AIR_TRAFFIC_TRACKER_USER_GUIDE.md)
- [Branded end-user guide (DOCX)](docs/publications/N0JCG_Air_Traffic_Center_User_Guide_v1.0.docx)
- [Branded end-user guide (PDF)](docs/publications/N0JCG_Air_Traffic_Center_User_Guide_v1.0.pdf)
- [Release and acceptance scope](docs/RELEASE_V1_0_0.md)
- [Development guardrails](docs/DEV_GUARDRAILS.md)
- [Repository structure and contribution workflow](docs/REPOSITORY_STRUCTURE.md)

The minimum source validation is:

```bash
node --check web/app.js
python3 -m py_compile src/backend/pi_air_traffic_backend.py
find tools deploy -type f -name '*.sh' -print0 | xargs -0 -r -n1 bash -n
```

Hardware-dependent validation must run on the target Raspberry Pi. Local browser checks do not prove receiver, antenna, decoder, or live audio behavior.

<!-- V1_0_RELEASE_BEGIN -->
## v1.0.0 production release

N0JCG AIR TRAFFIC CENTER v1.0.0 is the first full production release of the Raspberry Pi 5 aviation receiver application.

| Production area | Status |
| --- | --- |
| Raspberry Pi 5 / Debian Trixie service | PASS |
| FlyCatcher ADS-B 1090 reception | PASS |
| Optional FlyCatcher UAT 978 source integration | PASS |
| Seven-channel NOAA RF-first selection | PASS |
| NOAA clear live browser audio | PASS |
| Airband Fast Spectrum scanner | PASS |
| Airband validated AM receiver profile | PASS |
| Concurrent RTL-SDR USBFS provisioning | PASS |
| Aircraft map, trails, history, and weather radar | PASS |
| Release hardware acceptance suite | PASS |

Validated NOAA and Airband receiver settings use a 240 kHz RF input rate, 24 kHz audio, 49.6 dB RF gain, 0 PPM correction, offset tuning, and DC removal. NOAA adds FM deemphasis; Airband AM deliberately does not.

See [`docs/RELEASE_V1_0_0.md`](docs/RELEASE_V1_0_0.md) for the complete release scope and acceptance baseline.
<!-- V1_0_RELEASE_END -->

## Historical V0.1 initial Pi port checkpoint

The V0.1 checkpoint has validated the initial Raspberry Pi 5 + Nooelec FlyCatcher/NESDR runtime path:

| Area | Status |
| --- | --- |
| Raspberry Pi 5 / Debian Trixie runtime | PASS |
| FlyCatcher ADS-B 1090 receiver mapping | PASS |
| NESDR Nano2+ NOAA/Airband receiver mapping | PASS |
| App-owned RTL-SDR-enabled `readsb` | PASS |
| ADS-B stale JSON startup guard | PASS |
| ADS-B live message growth | PASS |
| Browser UI and API smoke tests | PASS |
| systemd service install/validation | PASS |
| NOAA capture and live audio | PASS |
| Airband fast-spectrum scanner control | PASS |
| FAA catalog import | Optional, not required for fast-spectrum scanning |
| FlyCatcher UAT 978 | Reserved for later milestone |

## Hardware target

| Role | Hardware | Serial | Purpose |
| --- | --- | --- | --- |
| ADS-B 1090 | Nooelec FlyCatcher ADS-B side | `00001090` | Continuous ADS-B aircraft tracking via app-owned `readsb` |
| NOAA/Airband | Nooelec NESDR Nano2+ | `00000162` | NOAA Weather Radio and civil airband AM audio |
| UAT 978 | Nooelec FlyCatcher UAT side | `00000978` | Detected and reserved for later application integration |

The application resolves Linux RTL-SDR runtime indexes from EEPROM serials at startup. Do not hard-code runtime indexes; USB enumeration order can change.

## Runtime architecture

The Pi service runs the ported web/API backend through `src/backend/pi_air_traffic_backend.py`. That shim keeps the shared browser API surface while replacing Windows-only receiver probing and decoder startup with Pi-native serial ownership and app-owned `readsb`.

The default systemd service is:

```text
pi-air-traffic-tracker.service
```

The default browser URL is:

```text
http://<pi-lan-ip>:8090
```

For the v1.0.0 hardware acceptance Pi used during release validation:

```text
http://192.168.68.110:8090
```

## Fresh Pi setup flow

From the Pi repo root:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_no_hardware_preflight.sh
./tools/pi5_install_runtime_dependencies.sh
./tools/pi5_flycatcher_preflight.sh
./tools/pi5_install_app_owned_readsb.sh
sudo ./tools/pi5_install_systemd_service.sh
```

Then validate the service and browser/API path:

```bash
./tools/pi5_validate_systemd_service.sh
./tools/pi5_validate_ui_api_smoke.sh
./tools/pi5_validate_backend_serial_startup.sh
./tools/pi5_validate_readsb_fresh_start.sh
./tools/pi5_validate_live_functional.sh
./tools/pi5_validate_active_noaa_airband.sh
```

Expected final state for the V0.1 checkpoint is `FINAL: PASS` on the listed validators. Airband live-hit audio may warn if no live AM transmission is present during the test window; scanner control should still pass.

## FAA Airband catalog

The FAA NASR FRQ catalog is runtime data and is not committed to Git. Traditional catalog-based scanning and nearby channel listings require importing the FAA FRQ CSV ZIP:

```bash
./tools/pi5_import_faa_airband_catalog.sh /path/to/FAA_NASR_*_FRQ_CSV.zip
./tools/pi5_validate_airband_catalog.sh
```

Fast-spectrum Airband scanning does not require the FAA catalog and can scan unlisted 120-130 MHz channels.

## Development workflow

The repo workflow is script-first:

- Patch scripts are run from Windows MSYS2 UCRT64.
- Pi validation scripts are run on the Raspberry Pi.
- Patch scripts stage explicit files only.
- Validation, commit, push, and tag operations are gated by PASS/FAIL checks.
- Local report/backup artifacts are ignored by Git and should not block explicit-path patches.

See `docs/DEV_GUARDRAILS.md` for project workflow rules.

## Key documents

- `docs/RELEASE_V1_0_0.md`

- `docs/RELEASE_V0_1_INITIAL_PI_PORT.md`
- `docs/PI_INITIAL_PORT_VALIDATION_CHECKLIST.md`
- `docs/PI_SERVICE_AND_SMOKE_TEST.md`
- `docs/PI_LIVE_FUNCTIONAL_VALIDATION.md`
- `docs/PI_ACTIVE_NOAA_AIRBAND_VALIDATION.md`
- `docs/PI_AIRBAND_CATALOG_IMPORT.md`
- `docs/PI_READSB_STALE_JSON_STARTUP_FIX.md`
- `docs/DEV_GUARDRAILS.md`

## V0.1 validated Pi initial-port checkpoint

The Raspberry Pi 5 initial port has been validated against live hardware. See `docs/PI_V0_1_VALIDATION_EVIDENCE.md` for the validation evidence and closed issues.

<!-- PI_V0_1_ACCEPTANCE_BEGIN -->
## V0.1 Pi acceptance validation

Run the full hardware acceptance suite on the Raspberry Pi after pulling the latest branch/tag:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
git pull --ff-only --tags
./tools/pi5_validate_v0_1_acceptance.sh
```

The acceptance bundle runs the systemd, ADS-B fresh-start, live functional, and active NOAA/Airband validators and writes one summary report under `runtime/preflight/`.

FAA Airband catalog data is optional for V0.1 fast-spectrum scanning. Traditional nearby-channel scanning requires importing the FAA NASR FRQ CSV ZIP with `tools/pi5_import_faa_airband_catalog.sh`.

See `docs/PI_V0_1_ACCEPTANCE_SUITE.md` for the full acceptance contract.
<!-- PI_V0_1_ACCEPTANCE_END -->

## V0.2 UAT 978 MHz development

V0.2 starts UAT support in gated steps. The UAT receiver serial is `00000978` and remains disabled in the persistent runtime until decoder tooling and backend integration are validated. Hardware probing is handled by `tools/pi5_probe_uat_978_capability.sh`; app-owned decoder tooling is handled by `tools/pi5_install_app_owned_dump978.sh` and `tools/pi5_validate_uat_decoder_tooling.sh`.

### V0.2 UAT 978 manual backend controls

UAT 978 MHz development now includes manual backend API controls for the app-owned `dump978-fa` decoder. Persistent UAT autostart remains disabled. Validate with `./tools/pi5_validate_uat_backend_api.sh` after installing `runtime/bin/dump978-fa`.

### V0.2 Traffic Source Controls

The Configuration menu includes source switches for 1090 MHz ADS-B and 978 MHz UAT. Enabled sources are merged into the existing `/api/aircraft.json` feed so aircraft continue to appear in the same map, active aircraft list, trail history, and detail UI. ADS-B 1090 defaults to on; UAT 978 defaults to off until enabled by the operator.
