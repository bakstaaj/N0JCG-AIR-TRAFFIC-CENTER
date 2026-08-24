# N0JCG AIR TRAFFIC CENTER User Guide

**Platform:** Raspberry Pi 5 running Debian/Raspberry Pi OS Trixie  
**Application service:** `pi-air-traffic-tracker.service`  
**Default web port:** `8090`  
**Guide revision:** August 24, 2026 (v1.1.3)

## 1. Scope

This guide covers installation, receiver identification, RTL-SDR EEPROM serial assignment, service setup, validation, and normal operation of **N0JCG AIR TRAFFIC CENTER**. The canonical repository is `N0JCG-AIR-TRAFFIC-CENTER`; existing `PI-AIR-TRAFFIC-TRACKER` checkout paths remain supported for installed service compatibility.

The four receiver roles covered here are:

- NOAA Weather Radio audio on the `00000162` VHF receiver.
- Civil Airband audio on the dedicated `00000118` receiver.
- ADS-B aircraft reception on 1090 MHz.
- UAT aircraft reception on 978 MHz.

This guide does **not** cover configuring these receivers for any other scanner, radio, SDR, or decoder application. Those applications have their own documentation. Do not run another SDR application against these receivers while N0JCG AIR TRAFFIC CENTER is active.

## Getting started with a new Pi

Use this dedicated section when building a new standalone N0JCG Air Traffic Center installation from an empty SD card. The guided installer performs the software setup and validation, while the operator prepares the Pi, connects the radios, and follows the one-at-a-time serial prompts.

### Hardware needed

- Raspberry Pi 5 with a reliable USB-C power supply and adequate cooling.
- High-endurance 32 GB or larger microSD card and a quality card reader.
- Ethernet cable for the initial setup and recommended normal operation. Wi-Fi is supported when Ethernet is unavailable.
- Nooelec FlyCatcher dual-tuner receiver with its ADS-B and UAT paths physically identified.
- Nooelec NESDR Nano2+ for NOAA Weather Radio.
- A dedicated RTL receiver for civil Airband.
- Powered USB hub when the Pi power budget or cable layout requires one.
- Band-appropriate antennas, coax, and labels for each receiver path.

### Recommended antenna arrangement

- 1090 MHz: dedicated outdoor or window-mounted ADS-B antenna with low-loss coax and a clear sky view.
- 978 MHz: a band-appropriate antenna or the FlyCatcher path intended for UAT reception.
- 118-163 MHz: a VHF antenna covering civil Airband and NOAA Weather Radio, connected to the NESDR Nano2+.

Label the cables before inserting the radios. Connect each antenna to the matching receiver role; do not use USB order as a role identifier.

### Load the Pi operating system

1. Use Raspberry Pi Imager to write the current 64-bit Raspberry Pi OS/Debian-family image to the SD card. Use Lite for a headless appliance or Desktop if the Pi will have a local display.
2. In the Imager customization screen, set the hostname, create the Pi user, configure the network and time zone, and enable SSH using password authentication for the initial deployment.
3. Insert the card, connect Ethernet and power, and allow the Pi to complete its first boot.
4. Confirm the Pi is reachable over SSH from the workstation. Keep all RTL-SDR receivers disconnected until the installer requests them.

### Run the guided installer

From an MSYS2/UCRT64 terminal on the workstation containing this repository, run:

```bash
./tools/install_pi_initial_deployment.sh
```

The launcher prompts for the Pi IP address, SSH user (normally `pi`), and SSH password, then stores reusable values in a private local `.env` file. The file contains the password and must not be committed or shared.

For each radio, follow the exact prompt sequence:

1. Insert only the named radio, such as “Insert the ADS-B radio”.
2. The installer confirms that one RTL-SDR is connected, backs up its EEPROM, and assigns the correct serial automatically.
3. Remove the radio when instructed.
4. Reinsert it once for automatic verification, then remove it again before the next role.

The required serial assignments are:

| Radio role | Required serial |
| --- | --- |
| ADS-B / FlyCatcher ADS-B path | `00001090` |
| NOAA Weather Radio / NESDR Nano2+ | `00000162` |
| Civil Airband / dedicated RTL receiver | `00000118` |
| UAT / FlyCatcher UAT path | `00000978` |

After all four radios are programmed, reconnect them with their antennas. The installer validates the serial-role map, installs the app-owned decoders and services, starts the Pi web/API service, and runs the final checks. When it reports success, open:

```text
http://<pi-ip-address>:8090
```

If the FlyCatcher ADS-B and UAT paths cannot be positively identified, stop. Do not assign their roles by Linux device index.

## 2. Hardware and permanent receiver names

The application owns receivers by their permanent RTL-SDR EEPROM serial numbers. Linux device numbers such as device `0`, `1`, or `2` are temporary and may change after a reboot, USB reconnection, or cabling change.

| Application role | Physical receiver | Frequency use | Required EEPROM serial | Normal runtime |
| --- | --- | --- | --- | --- |
| NOAA Weather Radio | Nooelec NESDR Nano2+ | NOAA 162 MHz NFM | `00000162` | `rtl_power` and `rtl_fm` |
| Civil Airband | Dedicated RTL receiver | Civil Airband AM | `00000118` | `rtl_power` and `rtl_fm` |
| ADS-B 1090 | Nooelec FlyCatcher ADS-B side | 1090 MHz ADS-B | `00001090` | App-owned `readsb` |
| UAT 978 | Nooelec FlyCatcher UAT side | 978 MHz UAT | `00000978` | App-owned `dump978-fa` when enabled |

Use the leading zeroes exactly as shown. Each value is an eight-character serial string.

### Recommended physical labels

Place a label on each antenna cable and receiver connection:

```text
NOAA WEATHER     SN 00000162
AIRBAND          SN 00000118
ADS-B 1090       SN 00001090
UAT 978           SN 00000978
```

Connect the antennas to their matching receiver paths:

- The NOAA VHF antenna connects to the Nano2+ assigned `00000162`.
- The civil Airband antenna connects to the dedicated receiver assigned `00000118`.
- The 1090 MHz antenna connects to the FlyCatcher ADS-B side assigned `00001090`.
- The 978 MHz antenna connects to the FlyCatcher UAT side assigned `00000978`.

Do not rely only on USB order or an old screenshot of device indexes.

## 3. Important serial-number safety rules

Changing an RTL-SDR EEPROM writes persistent hardware configuration. Follow these rules:

1. Stop N0JCG AIR TRAFFIC CENTER and any other SDR software first.
2. Identify a receiver by its physical connection and current manufacturer/product data.
3. Back up each EEPROM before changing its serial.
4. Never assign a serial based only on a Linux runtime index.
5. Never allow two connected receivers to have the same final serial.
6. Do not use `rtl_eeprom -g`, `-w`, `-m`, or `-p` for this procedure.
7. If the ADS-B and UAT sides of the FlyCatcher cannot be positively distinguished, stop. Do not guess.
8. Power-cycle the receivers after EEPROM changes before validating them.

The commands below intentionally change only the serial string with `rtl_eeprom -s`.

## 4. Raspberry Pi preparation

### 4.1 Base system

Use a Raspberry Pi 5 with a reliable power supply, current Debian-family 64-bit OS, network access, and SSH enabled. Update the system before installing the application:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

### 4.2 Clone the application

On the Raspberry Pi:

```bash
mkdir -p ~/sdrdev
cd ~/sdrdev
git clone https://github.com/bakstaaj/N0JCG-AIR-TRAFFIC-CENTER.git PI-AIR-TRAFFIC-TRACKER
cd PI-AIR-TRAFFIC-TRACKER
```

For an existing installation:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
git fetch --tags origin
git pull --ff-only
```

Do not discard local changes to make an update work. Investigate a non-clean repository before pulling.

### 4.3 Install runtime dependencies

Run from the repository root on the Pi:

```bash
./tools/pi5_no_hardware_preflight.sh
./tools/pi5_install_runtime_dependencies.sh
```

The dependency installer:

- Installs RTL-SDR, USB, audio, build, Python, Git, and SoX packages.
- Blacklists the Linux DVB drivers that would otherwise claim RTL-SDR hardware.
- Adds the user to relevant SDR/audio groups.
- Disables conflicting distribution decoder services when found.

If it prints `REBOOT RECOMMENDED`, reboot before continuing:

```bash
sudo reboot
```

After reboot:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
```

## 5. Assign and verify the RTL-SDR serial numbers

Perform this section only if the receivers do not already report the required serials.

### 5.1 Stop receiver-owning services

```bash
sudo systemctl stop pi-air-traffic-tracker.service 2>/dev/null || true
sudo systemctl stop readsb.service dump1090.service dump1090-fa.service \
  dump1090-mutability.service 2>/dev/null || true
```

Confirm that no long-running decoder owns an RTL-SDR:

```bash
pgrep -a -f 'readsb|dump1090|dump978|rtl_fm|rtl_power|rtl_sdr' || true
```

If an unrelated SDR process is shown, stop it before continuing.

### 5.2 Inventory all connected receivers

```bash
mkdir -p runtime/preflight
rtl_test -t 2>&1 | tee runtime/preflight/rtl_inventory_before_serials.txt
```

A fully named installation should eventually contain all four lines, although the numeric indexes may differ:

```text
SN: 00000162
SN: 00000118
SN: 00001090
SN: 00000978
```

Inspect EEPROM identity data for every listed index. If four receivers appear as indexes 0, 1, 2, and 3:

```bash
rtl_eeprom -d 0
rtl_eeprom -d 1
rtl_eeprom -d 2
```

Record a table before writing anything:

| Current index | Manufacturer/product | Physical role | Current serial | Required serial |
| --- | --- | --- | --- | --- |
| Confirmed index | NESDR Nano2+ | NOAA Weather Radio | Record value | `00000162` |
| Confirmed index | Dedicated RTL receiver | Civil Airband | Record value | `00000118` |
| Confirmed index | FlyCatcher ADS-B side | ADS-B 1090 | Record value | `00001090` |
| Confirmed index | FlyCatcher UAT side | UAT 978 | Record value | `00000978` |

### 5.3 Distinguish the two FlyCatcher receivers safely

The FlyCatcher exposes two independent RTL receivers. Identify them from their product strings and the board’s labeled ADS-B/UAT paths. A validated installation has appeared as:

```text
Nooelec, FlyCatcher_ADS_B, SN: 00001090
Nooelec, FlyCatcher_UAT,   SN: 00000978
```

Product strings are useful identification evidence, but the final application ownership is determined by serial number.

If both FlyCatcher sides still have indistinguishable factory strings or duplicate serials, do not choose one by index alone. Use the FlyCatcher board labeling and connection documentation to establish which tuner is the ADS-B side and which is the UAT side. Disconnect the external Nano2+ temporarily if doing so makes the two FlyCatcher entries easier to isolate. Re-run `rtl_test -t` after every physical connection change.

### 5.4 Back up each EEPROM

Set these variables only after completing the identification table. Replace the example index values with the indexes observed in the current inventory:

```bash
NOAA_INDEX=0
UAT_INDEX=1
ADSB_INDEX=2
```

Back up every EEPROM:

```bash
rtl_eeprom -d "$NOAA_INDEX" -r runtime/preflight/noaa_162_eeprom_before.bin
rtl_eeprom -d "$ADSB_INDEX" -r runtime/preflight/adsb_1090_eeprom_before.bin
rtl_eeprom -d "$UAT_INDEX" -r runtime/preflight/uat_978_eeprom_before.bin
```

Keep these files with the installation records. Do not commit them to Git.

### 5.5 Write only the required serial strings

Recheck each variable and physical role immediately before its command. Then write the serials:

```bash
sudo rtl_eeprom -d "$NOAA_INDEX" -s 00000162
sudo rtl_eeprom -d "$AIRBAND_INDEX" -s 00000118
sudo rtl_eeprom -d "$ADSB_INDEX" -s 00001090
sudo rtl_eeprom -d "$UAT_INDEX" -s 00000978
```

`rtl_eeprom` asks for confirmation before writing. Confirm only when its displayed device identity matches the intended physical receiver.

### 5.6 Fully power-cycle and validate

Shut the Pi down instead of performing only a warm restart:

```bash
sudo poweroff
```

Remove power for at least ten seconds, restore power, reconnect through SSH, and run:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
rtl_test -t 2>&1 | tee runtime/preflight/rtl_inventory_after_serials.txt
./tools/pi5_validate_receiver_serial_mapping.sh
```

The validator must end with:

```text
FINAL: PASS
```

It writes the detected runtime mapping to:

```text
runtime/settings/pi_air_traffic_hardware_roles.detected.json
```

This runtime file records the current serial-to-index mapping. It is evidence, not permanent configuration.

## 6. Install the application-owned decoders

### 6.1 ADS-B 1090 decoder

Install the project-owned RTL-SDR-capable `readsb` binary:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_install_app_owned_readsb.sh
```

The binary is installed at:

```text
runtime/bin/readsb
```

The application starts it with serial `00001090`. A separately installed `readsb.service` must remain disabled so it cannot claim the ADS-B receiver first.

### 6.2 UAT 978 decoder

Build and install the project-owned `dump978-fa` tools:

```bash
./tools/pi5_install_app_owned_dump978.sh
./tools/pi5_validate_uat_decoder_tooling.sh
```

The primary binary is installed at:

```text
runtime/bin/dump978-fa
```

UAT remains an operator-selectable traffic source. Installing the binary does not require UAT to be enabled at all times.

## 7. Configure USBFS memory for concurrent receivers

ADS-B, UAT, NOAA, and Airband can run concurrently. Install the project’s USBFS memory unit and service dependency before installing the main service:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER

sudo install -m 0644 \
  deploy/systemd/pi-air-traffic-usbfs-memory.service \
  /etc/systemd/system/pi-air-traffic-usbfs-memory.service

sudo install -d -m 0755 \
  /etc/systemd/system/pi-air-traffic-tracker.service.d

sudo install -m 0644 \
  deploy/systemd/pi-air-traffic-tracker.service.d/10-usbfs-memory.conf \
  /etc/systemd/system/pi-air-traffic-tracker.service.d/10-usbfs-memory.conf

sudo systemctl daemon-reload
sudo systemctl enable --now pi-air-traffic-usbfs-memory.service
cat /sys/module/usbcore/parameters/usbfs_memory_mb
```

Expected value:

```text
0
```

In this context, `0` means the USBFS ceiling is not restricted to the small default allocation. This prevents allocation/submission failures when multiple RTL-SDR streams are active.

## 8. Install and start N0JCG AIR TRAFFIC CENTER

Install the systemd service from the Pi repository root:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
sudo ./tools/pi5_install_systemd_service.sh
```

The installer writes the four serial assignments into the service environment:

```text
PI_AIR_TRAFFIC_AUDIO_SERIAL=00000162
PI_AIR_TRAFFIC_AIRBAND_SERIAL=00000118
PI_AIR_TRAFFIC_ADSB_SERIAL=00001090
PI_AIR_TRAFFIC_UAT_SERIAL=00000978
```

Check service state:

```bash
sudo systemctl status pi-air-traffic-tracker.service --no-pager
```

Useful service commands:

```bash
sudo systemctl restart pi-air-traffic-tracker.service
sudo systemctl stop pi-air-traffic-tracker.service
sudo systemctl start pi-air-traffic-tracker.service
sudo journalctl -u pi-air-traffic-tracker.service -n 200 --no-pager
```

## 9. Validate the complete installation

Run the core validators:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_validate_systemd_service.sh
./tools/pi5_validate_ui_api_smoke.sh
./tools/pi5_validate_backend_serial_startup.sh
./tools/pi5_validate_readsb_fresh_start.sh
./tools/pi5_validate_live_functional.sh
./tools/pi5_validate_active_noaa_airband.sh
./tools/pi5_validate_uat_978_capability.sh
./tools/pi5_validate_uat_backend_api.sh
./tools/pi5_validate_traffic_source_ui_merge.sh
```

Each applicable validator should finish with `FINAL: PASS`. Airband voice tests may warn when no transmission occurs during the test window; RF scanning and control validation can still pass.

Inspect the live API status:

```bash
curl -fsS http://127.0.0.1:8090/api/status | \
  jq '{receiver_roles, traffic_sources, uat_978}'
```

Verify that the reported roles contain:

```text
ADS-B serial:       00001090
NOAA/audio serial:  00000162
Airband serial:     00000118
UAT serial:         00000978
```

The numeric runtime indexes may be different from those recorded during installation. That is normal.

## 10. Open the browser interface

From another device on the same network, open:

```text
http://<pi-lan-ip>:8090
```

For the validated installation used during development:

```text
http://192.168.68.110:8090
```

If the Pi address changes, use its current LAN address. The port remains `8090` unless the systemd configuration is intentionally changed.

## 11. Traffic source operation

### ADS-B 1090

ADS-B 1090 is normally enabled and runs continuously. The application-owned `readsb` process owns serial `00001090` and writes aircraft data consumed by the unified map and aircraft list.

If ADS-B is enabled but no aircraft appear:

```bash
pgrep -a -f 'runtime/bin/readsb'
curl -fsS http://127.0.0.1:8090/api/status | jq '.receiver_roles.adsb, .decoder'
sudo journalctl -u pi-air-traffic-tracker.service -n 100 --no-pager
```

### UAT 978

UAT is optional and operator controlled:

1. Open the application menu.
2. Open **Traffic Sources**.
3. Enable **UAT 978**.
4. Apply the traffic-source settings.

The UAT decoder uses serial `00000978`. Decoded UAT aircraft are merged with ADS-B aircraft in the same map, list, history, and detail views.

No UAT aircraft during a short observation does not prove a receiver failure. UAT is used primarily by general aviation aircraft, is bursty, and may be limited by terrain, antenna placement, and local traffic levels.

### Unified aircraft presentation

The operator does not use separate maps for ADS-B and UAT. Enabled sources feed one aircraft presentation. Aircraft received from either source can appear in:

- The active-aircraft list.
- The main map.
- Aircraft detail panels.
- Trails and history.

## 12. NOAA Weather Radio operation

NOAA uses receiver serial `00000162`. Civil Airband uses the dedicated receiver serial `00000118`.

To start NOAA:

1. Open the NOAA Weather controls.
2. Select **Start NOAA Weather**.
3. Allow the application to scan all seven standard NOAA frequencies.
4. The application ranks channels by RF carrier strength, validates audio, and selects the best station.

Do not permanently hard-code the local NOAA frequency in a portable installation. The saved verified channel is associated with the receiver location and can be rescanned when the location changes.

The validated NOAA receiver profile is:

| Setting | Value |
| --- | --- |
| RF input rate | 240,000 samples/second |
| Audio output rate | 24,000 samples/second |
| RF gain | 49.6 dB |
| PPM correction | 0 |
| Offset tuning | Enabled |
| DC removal | Enabled |
| FM deemphasis | Enabled |

Use **Reset & Rescan NOAA** when the receiver location, antenna, or RF environment changes.

## 13. Civil Airband operation

Airband uses the dedicated `00000118` receiver in AM mode. Stop any active NOAA listening session before starting Airband from the application UI.

The recommended normal mode is **Fast Spectrum Search**, which examines 120–130 MHz for RF activity and audio-validates only the strongest candidates instead of listening linearly to every quiet channel.

The validated Airband profile is:

| Setting | Value |
| --- | --- |
| Demodulation | AM |
| RF input rate | 240,000 samples/second |
| Audio output rate | 24,000 samples/second |
| RF gain | 49.6 dB |
| PPM correction | 0 |
| Offset tuning | Enabled |
| DC removal | Enabled |
| FM deemphasis | Disabled |

FM deemphasis is intentionally disabled for AM Airband voice.

Traditional nearby-channel scanning requires the optional FAA catalog. Fast Spectrum Search does not require it. This guide does not cover exporting this receiver configuration to any other scanner application.

## 14. Weather radar and map operation

The weather radar overlay is browser-side and requires internet access from the browser. Radar history uses buffered frame transitions: the displayed frame remains visible while the next frame loads.

Current playback defaults are:

| Playback item | Delay |
| --- | --- |
| Normal frame | 750 ms |
| Slow frame | 1.2 seconds |
| Fast frame | 450 ms |
| Latest frame hold | 15 seconds |

Leaflet tile fading is disabled globally, so loaded frames and map tiles appear without an opacity ramp. Radar opacity remains adjustable from the Weather Radar menu.

## 15. Routine updates

From the Pi:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
git status --short
git fetch --tags origin
git pull --ff-only
sudo systemctl restart pi-air-traffic-tracker.service
```

Then verify:

```bash
sudo systemctl is-active pi-air-traffic-tracker.service
curl -fsS http://127.0.0.1:8090/api/status | jq '.receiver_roles'
```

Do not pull over unexpected tracked modifications. Preserve and review local work first.

## 16. Troubleshooting

### Expected serial is missing

1. Stop the application service.
2. Run `rtl_test -t`.
3. Power-cycle the Pi and receivers.
4. Check USB seating and power.
5. Re-run `pi5_validate_receiver_serial_mapping.sh`.

Do not rewrite an EEPROM merely because a numeric index changed.

### Receiver is busy or cannot be claimed

```bash
sudo systemctl stop pi-air-traffic-tracker.service
pgrep -a -f 'readsb|dump1090|dump978|rtl_fm|rtl_power|rtl_sdr'
```

Stop the conflicting process. Do not run a distribution `readsb` service beside the application-owned decoder.

### USB buffer allocation or transfer submission fails

```bash
cat /sys/module/usbcore/parameters/usbfs_memory_mb
systemctl status pi-air-traffic-usbfs-memory.service --no-pager
```

The expected USBFS value is `0`. Reinstall the unit and drop-in from Section 7 if necessary, then restart the tracker service.

### ADS-B process runs but no aircraft appear

- Confirm the 1090 MHz antenna is connected to the ADS-B side.
- Confirm `receiver_roles.adsb.serial` is `00001090`.
- Run `pi5_validate_readsb_fresh_start.sh`.
- Check the service log for repeated decoder restarts.

### UAT process runs but no aircraft appear

- Confirm the 978 MHz antenna is connected to the UAT side.
- Confirm `receiver_roles.uat.serial` is `00000978`.
- Run `pi5_validate_uat_978_capability.sh`.
- Observe during a longer daytime period before concluding reception has failed.

### NOAA scan does not find a usable station

- Confirm the NOAA VHF antenna is connected to serial `00000162` and the Airband antenna is connected to serial `00000118`.
- Stop Airband before starting NOAA.
- Use **Reset & Rescan NOAA**.
- Check service logs for USB claim or allocation errors.

### Airband traffic is infrequent

Infrequent voice traffic is normal in some locations. Use Fast Spectrum Search and validate scanner sweeps independently of live voice. A quiet observation period is not by itself a hardware failure.

## 17. Final installation checklist

- [ ] Nano2+ is physically labeled NOAA and reports `00000162`.
- [ ] Dedicated Airband receiver is physically labeled and reports `00000118`.
- [ ] FlyCatcher ADS-B side is physically labeled and reports `00001090`.
- [ ] FlyCatcher UAT side is physically labeled and reports `00000978`.
- [ ] All three EEPROM backups exist under `runtime/preflight/`.
- [ ] `pi5_validate_receiver_serial_mapping.sh` reports `FINAL: PASS`.
- [ ] `runtime/bin/readsb` is installed and executable.
- [ ] `runtime/bin/dump978-fa` is installed and executable.
- [ ] USBFS memory service is enabled and reports `0`.
- [ ] `pi-air-traffic-tracker.service` is enabled and active.
- [ ] `/api/status` reports all four correct serial roles.
- [ ] ADS-B 1090 is enabled and its message feed is growing.
- [ ] NOAA can scan and deliver browser audio.
- [ ] Airband Fast Spectrum Search completes a sweep.
- [ ] UAT can be enabled from Traffic Sources and reports consistent state.
- [ ] The browser UI opens on port `8090`.

When every applicable item is complete, the installation is ready for normal N0JCG AIR TRAFFIC CENTER operation.
