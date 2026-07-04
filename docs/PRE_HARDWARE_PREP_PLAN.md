# Pre-Hardware Preparation Plan

This checkpoint covers useful work that can be completed before the FlyCatcher HAT and NESDR Nano2+ are physically available.

## Current Port Scope

The first Pi port keeps the Windows tracker feature set as the functional baseline while replacing the Windows runtime and device assumptions with Raspberry Pi 5 / Raspberry Pi OS Trixie behavior.

Initial receiver role mapping:

| Role | Hardware | Initial status |
| --- | --- | --- |
| ADS-B 1090 MHz | FlyCatcher ADS-B side | Active in first milestone |
| NOAA weather radio | NESDR Nano2+ | Active in first milestone |
| Civil airband AM | NESDR Nano2+ | Active in first milestone |
| UAT 978 MHz | FlyCatcher UAT side | Reserved for later milestone |

## Work That Can Be Done Before Hardware Arrives

1. Keep the repo guardrails updated for Pi-specific workflow corrections.
2. Add config templates for hardware roles without locking in RTL index values.
3. Add no-device Pi readiness checks for OS, Python, RTL-SDR tools, readsb/dump1090 availability, audio tools, and network/runtime prerequisites.
4. Prepare a hardware arrival checklist so the first live test captures useful evidence.
5. Avoid backend device-mapping patches until real Pi enumeration output is available.

## Work That Must Wait For Hardware

1. Assigning stable serial numbers or rtl_tcp/index mappings.
2. Confirming FlyCatcher ADS-B vs UAT enumeration order.
3. Confirming the Nano2+ serial/index used for NOAA/Airband.
4. Validating 1090 MHz ADS-B message ingest.
5. Validating NOAA NFM and airband AM audio.
6. Creating any UAT runtime service or UI integration beyond a reserved role.

## Expected Hardware Evidence Tomorrow

When the hardware arrives, run these from the Pi repo root after bootstrap:

```bash
./tools/pi5_no_hardware_preflight.sh
./tools/pi5_flycatcher_preflight.sh
./tools/pi5_expected_hardware_checklist.sh
```

Send the final PASS/WARN/FAIL summaries and the captured RTL/USB role evidence before any backend mapping patch is created.
