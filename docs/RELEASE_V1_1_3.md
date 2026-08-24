# N0JCG Air Traffic Center v1.1.3

**Release type:** Dedicated Airband receiver and documentation successor release  
**Repository:** `bakstaaj/N0JCG-AIR-TRAFFIC-CENTER`

## Included changes

- Civil Airband now owns dedicated RTL-SDR EEPROM serial `00000118`.
- NOAA Weather Radio remains on serial `00000162`; the two VHF audio roles no longer compete for one receiver.
- ADS-B 1090 remains on `00001090`; UAT 978 remains on `00000978`.
- Pi deployment, receiver-role, startup, service, UI/API, and Airband validation workflows now verify the four-role mapping.
- The branded end-user DOCX and PDF guide are refreshed for v1.1.3 with the dedicated Airband hardware, antenna arrangement, guided installer, and current operator screenshots.
- The release package includes the guided first-deployment script and service installation/validation tools.

## Validated baseline

- Pi 5 service active on port 8090.
- Airband profile: AM, 240 kHz RF input, 24 kHz audio, 49.6 dB gain, 0 PPM, offset tuning, and DC removal.
- Live Airband tuning on serial `00000118` completed successfully with RF evidence and audio RMS during Pi validation.
- Python compilation, unit tests, shell syntax, package contents, and guide rendering passed before publication.

## Operator note

Keep the civil Airband antenna connected to `00000118` and the NOAA VHF antenna connected to `00000162`. Receiver indexes can change after reboot; the application resolves ownership from EEPROM serials.
