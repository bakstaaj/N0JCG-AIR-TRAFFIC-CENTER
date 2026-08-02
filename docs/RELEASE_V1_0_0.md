# N0JCG AIR TRAFFIC CENTER v1.0.0

**Release date:** July 23, 2026  
**Release type:** First full production release

N0JCG AIR TRAFFIC CENTER v1.0.0 promotes the Raspberry Pi 5 port from development checkpoints to a complete, live-hardware-validated aviation tracking and radio application.

## Production hardware target

| Role | Hardware | EEPROM serial | Runtime |
| --- | --- | --- | --- |
| ADS-B 1090 MHz | Nooelec FlyCatcher ADS-B side | `00001090` | App-owned RTL-SDR-enabled `readsb` |
| NOAA/Airband | NESDR Nano2+ | `00000162` | Shared `rtl_power` and `rtl_fm` receiver |
| UAT 978 MHz | Nooelec FlyCatcher UAT side | `00000978` | Optional operator-controlled `dump978-fa` source |

Linux RTL-SDR indexes are resolved from EEPROM serials at runtime. USB enumeration order is not treated as stable.

## Major release capabilities

### Aircraft tracking

- Continuous 1090 MHz ADS-B reception through app-owned `readsb`.
- Optional 978 MHz UAT source controls and merged aircraft presentation.
- Single aircraft map, active-aircraft list, details, trails, and history across enabled traffic sources.
- Aircraft details, operator enrichment, altitude-colored trails, and active-track cleanup.
- Animated weather-radar history overlay and playback controls.

### NOAA Weather Radio

- Portable scan of all seven standard NOAA Weather Radio frequencies.
- RF-first channel ranking so a dominant carrier is not displaced by quiet adjacent-channel audio.
- Audio validation of the strongest RF candidate or close candidates.
- Saved verified channel tied to receiver coordinates and rescanned after location changes.
- Validated receiver profile:
  - 240,000 samples/second RF input
  - 24,000 samples/second audio output
  - 49.6 dB RF gain
  - 0 PPM correction
  - offset tuning request
  - DC removal
  - FM deemphasis
- Fast live-audio startup and clear browser playback.

### Civil Airband AM

- Fast Spectrum Search over 120–130 MHz.
- Traditional catalog-assisted scanning when FAA NASR data is installed.
- Live hold audio, skip, block, squelch adjustment, and seven-second silence release.
- Validated AM receiver profile:
  - 240,000 samples/second RF input
  - 24,000 samples/second audio output
  - 49.6 dB RF gain
  - 0 PPM correction
  - offset tuning request
  - DC removal
  - no FM deemphasis
- Bounded AM capture and spectrum-sweep validation that does not depend on live traffic being present.

### Raspberry Pi runtime

- Raspberry Pi 5 with Debian Trixie full.
- Native systemd service on TCP port 8090.
- Persistent USBFS memory provisioning for concurrent ADS-B, UAT, and NOAA/Airband RTL-SDR operation.
- Serial-based receiver ownership and service/API diagnostics.
- Script-first installation, validation, release, and recovery workflows for MSYS2 UCRT64.

## v1.0.0 acceptance baseline

The release is accepted only after all of the following pass on the target Pi:

- Service and API restart.
- ADS-B receiver mapping and running decoder.
- Web UI and static assets.
- Complete NOAA and Airband profile reporting.
- NOAA live start and non-silent 24 kHz WAV delivery.
- Airband Fast Spectrum Search completes at least one 49.6 dB sweep.
- USBFS memory ceiling is configured for concurrent SDR operation.
- No tracked working-tree changes remain on either development host or Pi.

## Operational notes

- Live Airband voice validation still depends on transmissions being present; scanner control, RF sweep, and bounded AM audio paths are validated independently.
- FAA catalog data is optional for Fast Spectrum Search and required for traditional nearby-channel listings.
- The weather-radar overlay requires internet access from the browser.
- UAT remains operator controlled and can be left disabled where 978 MHz coverage is unavailable.

## Upgrade

From the Pi repository:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
git fetch --tags origin
git pull --ff-only
sudo systemctl restart pi-air-traffic-tracker.service
```

The release publication workflow verifies that the Pi is running the exact release commit before creating the annotated tag and GitHub Release.
