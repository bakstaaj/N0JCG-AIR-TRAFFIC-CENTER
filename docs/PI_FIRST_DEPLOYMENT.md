# N0JCG Air Traffic Center first Pi deployment

Use this workflow for a new Raspberry Pi that does not yet have the application installed. It is designed for a workstation running MSYS2/UCRT64 and a Raspberry Pi OS/Debian-family target.

## Start from the workstation

From the repository root:

```bash
./tools/install_pi_initial_deployment.sh
```

The launcher asks for:

- the Pi IP address;
- the SSH user, defaulting to `pi`; and
- the SSH password.

It stores these as `PI_HOST`, `PI_USER`, and `PI_PASS` in `.env`, restricts that file to the current user, and reuses the values on later runs. Do not commit or share `.env`; it contains the SSH password. A safe template is provided at `.env.example`.

The bundle is created from the current committed Git revision and uploaded over SSH. The remote destination is:

```text
/home/<pi-user>/n0jcg-air-traffic-center
```

The installer is intentionally interactive because receiver identity cannot be inferred safely from transient Linux USB indexes.

## Receiver serial walkthrough

For each receiver, the installer asks you to:

1. Disconnect every other RTL-SDR.
2. Connect only the receiver for the named role.
3. Confirm the physical product/board path shown by `rtl_test -t` and `rtl_eeprom`.
4. Allow an EEPROM backup to be saved under `runtime/preflight/serial-backups/`.
5. Type `PROGRAM` before the serial is written.
6. Disconnect/reconnect that receiver and confirm the new serial.

The roles are performed in this order:

| Role | Required EEPROM serial |
| --- | --- |
| ADS-B 1090 / FlyCatcher ADS-B side | `00001090` |
| NOAA/Airband 162 / NESDR Nano2+ | `00000162` |
| UAT 978 / FlyCatcher UAT side | `00000978` |

Use the physical FlyCatcher labels and antenna path to distinguish its ADS-B and UAT sides. If the two sides cannot be positively distinguished, stop the installer rather than assigning serials by device index.

## Installation order

The remote workflow performs these stages:

1. Extract the application into the standalone N0JCG path.
2. Install OS packages, RTL-SDR tools, audio tools, Python, build tools, and support libraries.
3. Install the project-owned RTL-compatible `readsb` binary and build the project-owned `dump978-fa` tooling.
4. Program and verify the receiver serials one at a time.
5. Run serial-role and decoder checks before service startup.
6. Install and enable the USBFS and Air Traffic Center systemd services.
7. Start the web/API service and run systemd, UI/API, and serial startup validation.

The web application is served by the Pi itself. No ROC web application is required for this standalone installation.

## Finish

When the final checks pass, open this address from a browser on the same LAN:

```text
http://<pi-ip-address>:8090
```

If the service or API validation fails, do not continue to operator use. Review the reported `runtime/preflight/` evidence and `journalctl -u pi-air-traffic-tracker.service --no-pager` on the Pi.
