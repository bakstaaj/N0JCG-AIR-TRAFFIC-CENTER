# V0.2 UAT Acceptance Validation

This acceptance validator captures the V0.2 UAT and unified traffic-source milestone for the Raspberry Pi 5 FlyCatcher/NESDR target.

## Scope

The validator confirms:

- V0.2 static patch artifacts are present.
- 1090 ADS-B and 978 UAT source switches exist in the Configuration menu.
- The browser UI pauses recurring refresh while the menu drawer is open so source switches remain usable.
- UAT socket/readline idle timeouts are treated as non-fatal no-data conditions.
- The Pi service reaches HTTP readiness at `/api/status` before API checks begin.
- UAT hardware capability validation passes.
- App-owned `dump978-fa` tooling validation passes.
- Manual UAT backend API validation passes.
- Traffic-source UI and unified aircraft feed validation passes.
- The final `/api/aircraft.json` feed remains one merged aircraft source for the existing map, list, and detail UI.

## Running

On the Pi, from the repository root:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
sudo systemctl restart pi-air-traffic-tracker.service
./tools/pi5_validate_v0_2_acceptance.sh
```

The V0.1 full acceptance validator is not run by default because it is a longer baseline regression pass. To include it in the same V0.2 acceptance report:

```bash
RUN_V0_1_BASELINE=1 ./tools/pi5_validate_v0_2_acceptance.sh
```

## Expected UAT Result

Zero live 978 MHz aircraft is acceptable. The acceptance condition is that the UAT decoder and collector are healthy and that idle/no-message operation does not surface `cannot read from timed out object` as an error.


## Optional V0.1 baseline regression

The V0.2 acceptance validator skips the longer V0.1 baseline by default. Run `RUN_V0_1_BASELINE=1 ./tools/pi5_validate_v0_2_acceptance.sh` to include the V0.1 baseline in the same final report. The older `PI_AIR_TRAFFIC_RUN_V0_1_ACCEPTANCE=1` name remains accepted as a backward-compatible alias.

## Recovery notes

- UAT hardware capability compatibility validator: `tools/pi5_validate_uat_978_capability.sh` validates serial `00000978` enumeration and role visibility without stealing the receiver from a running `dump978-fa` session.
- Static source scans do not fail on historical timeout text; the runtime `/api/uat/status` collector state is the acceptance authority for idle UAT behavior.
- The UI must retain the menu refresh pause marker and behavior so traffic-source switches remain operable while the configuration drawer is open.
