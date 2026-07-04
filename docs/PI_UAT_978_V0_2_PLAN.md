# V0.2 UAT 978 Capability Plan

This milestone adds Universal Access Transceiver (UAT) 978 MHz capability to the Pi Air Traffic Tracker without disturbing the validated V0.1 ADS-B, NOAA, Airband, and systemd baseline.

## Current receiver ownership

| Role | Serial | Hardware | V0.1 state | V0.2 goal |
| --- | --- | --- | --- | --- |
| ADS-B 1090 | `00001090` | FlyCatcher ADS-B side | Enabled, app-owned `readsb` | Keep stable |
| NOAA/Airband | `00000162` | NESDR Nano2+ | Enabled, `rtl_fm` audio path | Keep stable |
| UAT 978 | `00000978` | FlyCatcher UAT side | Detected, disabled | Probe, then integrate |

## V0.2 phases

1. **Capability probe**: confirm the UAT RTL-SDR serial is visible, resolves to a runtime index, is not used by the active V0.1 services, can be opened exclusively, and can tune/capture at 978 MHz.
2. **Decoder selection**: record which UAT decoder tooling is present on the Pi, such as `dump978-fa` or another compatible decoder. Missing decoder tooling is a warning during the probe, not a failure.
3. **Backend runtime**: after hardware/tooling is understood, add an app-owned UAT manager parallel to the ADS-B `readsb` manager. It must use the stable EEPROM serial, not a hard-coded Linux device index.
4. **API/status contract**: expose UAT enabled/running/json-ready/message-count/error state in `/api/status` without changing the existing ADS-B contract.
5. **UI/data integration**: merge or present UAT aircraft separately only after the backend proves stable. FIS-B/weather products are a later scope item.

## Guardrails

- Do not enable a UAT decoder service until the probe passes on the Pi.
- Do not reuse the ADS-B `readsb` liveness shortcuts for UAT; process ownership must prove runtime liveness.
- Do not use UAT runtime index as configuration. Resolve index from serial `00000978` on each startup.
- Do not let UAT failures break the validated V0.1 ADS-B/NOAA/Airband service path.
- Treat no live 978 MHz messages as environmental unless the decoder process or receiver open fails.

## First validation command

Run this on the Pi after pulling the patch:

```bash
./tools/pi5_probe_uat_978_capability.sh
```

The probe is intentionally non-invasive. It does not start a persistent UAT decoder, modify systemd units, or change runtime settings.

## Raw IQ capture matrix

The first UAT probe is intentionally hardware-only.  It must not start a persistent UAT service or change the V0.1 ADS-B/NOAA/Airband runtime.  Because `rtl_sdr` builds vary in accepted gain syntax and synchronous-read behavior, the probe tries a small capture matrix using the resolved runtime index and the stable UAT serial, with multiple sample rates and gain argument styles.  A raw IQ file with bytes proves that the UAT receiver can tune/open/capture at 978 MHz; actual UAT frame decoding remains a later V0.2 step.
