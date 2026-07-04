# Port Plan: Raspberry Pi 5 + FlyCatcher + NESDR Nano2+

## Scope

Port the Windows RTL ADS-B Tracker behavior into a Pi-native application:

- Keep the browser UI and user workflows as close to the Windows version as practical.
- Replace Windows service packaging with `systemd`.
- Replace Windows executable paths and service helpers with Linux/Pi commands.
- Use the FlyCatcher ADS-B USB side for 1090 MHz ADS-B first.
- Use the NESDR Nano2+ as the NOAA / civil airband receiver.
- Leave FlyCatcher UAT as a reserved, detected device until the ADS-B/audio baseline is stable.

## Hardware mapping

| Receiver role | Device | Frequency/function | Notes |
| --- | --- | --- | --- |
| `adsb_1090` | FlyCatcher ADS-B side | 1090 MHz ADS-B | First continuous decoder |
| `audio_vhf` | NESDR Nano2+ | 162 MHz NOAA + 118-137 MHz AM airband | Reuse Windows audio workflow |
| `uat_978` | FlyCatcher UAT side | 978 MHz UAT | Detect now, integrate later |

## Initial port checkpoints

1. Stage Windows baseline source into this Pi repository.
2. Add Pi hardware preflight script.
3. Add Pi package/bootstrap script.
4. Create Pi backend entry point from the Windows Pi-port backend.
5. Replace Windows-only paths, `.exe` names, service wrappers, firewall commands, and process handling.
6. Add `systemd` service installer.
7. Validate static syntax: shell, Python, JavaScript.
8. Validate live hardware:
   - RTL-SDR devices enumerate.
   - ADS-B receiver produces nonzero message count.
   - NOAA listen produces audio bytes.
   - Airband manual listen starts/stops cleanly.
9. Commit and tag only after one meaningful hardware/API validation.

## Guardrails

- Keep `docs/DEV_GUARDRAILS.md` updated in this repository before or alongside patches that change workflow.
- Prefer single `.sh` handoff scripts for non-trivial command sequences.
- Scripts should be idempotent where practical.
- Scripts should print PASS/FAIL.
- Avoid pager-generating Git commands.
- Use real PASS/FAIL checks rather than visual inspection.
- Do not commit generated logs, captures, or local secrets.
