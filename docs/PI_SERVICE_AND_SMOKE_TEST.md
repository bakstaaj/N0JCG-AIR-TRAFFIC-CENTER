# Pi service and UI/API smoke-test workflow

This milestone validates the initial Raspberry Pi 5 FlyCatcher/NESDR port as a running web/API application before treating it as an installed boot service.

## Pi-side order

From the Raspberry Pi repository root:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_install_app_owned_readsb.sh
./tools/pi5_validate_backend_serial_startup.sh
./tools/pi5_validate_ui_api_smoke.sh
sudo ./tools/pi5_install_systemd_service.sh
./tools/pi5_validate_systemd_service.sh
```

## What is validated

- The app-owned RTL-SDR-enabled `readsb` binary exists under `runtime/bin/readsb`.
- The backend starts on `0.0.0.0:8090` for LAN access.
- `/api/status` reports the Pi receiver-role contract for serials `00001090`, `00000162`, and `00000978`.
- The ADS-B decoder is running and producing `aircraft.json`.
- The web root, `app.js`, `app.css`, and `/api/aircraft.json` respond.
- The systemd service `pi-air-traffic-tracker.service` can be installed, enabled, started, and validated.

## LAN access

After the service installer or validator passes, open the displayed URL from another computer on the same LAN:

```text
http://<pi-ip-address>:8090
```

## Notes

The Debian-packaged `readsb` service must not own the ADS-B receiver. The service installer disables `readsb.service` and runs the app-owned backend, which starts app-owned `runtime/bin/readsb` using stable EEPROM serial ownership.
