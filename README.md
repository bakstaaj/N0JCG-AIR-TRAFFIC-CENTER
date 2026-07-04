# PI-AIR-TRAFFIC-TRACKER

Raspberry Pi 5 aircraft tracking and aviation audio application.

This repository starts as a Pi port of `bakstaaj/RTL-WINDOWS-ADS-B-TRACKER`, targeting:

- Raspberry Pi 5 running Raspberry Pi OS / Debian Trixie full.
- Nooelec FlyCatcher HAT for the primary 1090 MHz ADS-B receiver.
- Nooelec NESDR Nano2+ RTL-SDR for NOAA Weather Radio and civil airband AM audio.
- Future FlyCatcher 978 MHz UAT receiver support after the baseline ADS-B/audio port is stable.

The first porting goal is to preserve the Windows tracker UI and user-facing behavior, then replace the Windows-specific backend/service/runtime pieces with Pi-native Linux equivalents.

## Initial hardware roles

| Role | Hardware | Initial purpose |
| --- | --- | --- |
| ADS-B 1090 | FlyCatcher ADS-B USB side | Continuous ADS-B aircraft tracking |
| Audio | NESDR Nano2+ | NOAA Weather Radio and civil airband listening/scanning |
| UAT 978 | FlyCatcher UAT USB side | Reserved for later application integration |

## Current status

This is an initial staged port. The Windows baseline source has been copied into this repository so the next work can focus on the Pi-native backend, installer, service, and live hardware validations.

See `docs/PORT_PLAN_PI5_FLYCATCHER.md` and `docs/DEV_GUARDRAILS.md`.
