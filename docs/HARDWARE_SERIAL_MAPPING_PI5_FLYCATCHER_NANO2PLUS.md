# Raspberry Pi 5 FlyCatcher + NESDR Nano2+ Serial Mapping

This file records the intended hardware-role mapping for the Raspberry Pi 5 Trixie port after the SDR EEPROM serial numbers were set.

## Target Hardware

| Role | Hardware | Stable RTL Serial | Initial Runtime Use |
|---|---|---:|---|
| NOAA / Airband | NESDR Nano2+ external USB SDR | `00000162` | Enabled |
| ADS-B 1090 MHz | FlyCatcher ADS-B side | `00001090` | Enabled |
| UAT 978 MHz | FlyCatcher UAT side | `00000978` | Detected but disabled until later milestone |

## Important Rule

Backend code should resolve the current RTL runtime index from the stable EEPROM serial at startup. It should not hard-code RTL device indexes because USB enumeration order can change across reboots or cabling changes.

## Validation

Run this on the Raspberry Pi with the FlyCatcher and NESDR connected:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_validate_receiver_serial_mapping.sh
```

Expected result:

```text
FINAL: PASS
```

The validator writes a detected runtime mapping to:

```text
runtime/settings/pi_air_traffic_hardware_roles.detected.json
```

That detected file is runtime evidence and should remain untracked.

## Backend Milestone

The next backend patch should use this serial mapping:

- ADS-B decoder uses serial `00001090`.
- NOAA/Airband `rtl_fm` uses serial `00000162`.
- UAT serial `00000978` is detected and reported but not yet used by the application.
