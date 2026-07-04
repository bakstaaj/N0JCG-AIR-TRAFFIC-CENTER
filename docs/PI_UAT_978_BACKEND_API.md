# Pi UAT 978 MHz Backend API Controls

V0.2 adds explicit manual backend control for the app-owned `dump978-fa` UAT decoder while keeping persistent UAT autostart disabled.

## Policy

- UAT remains disabled as an automatic/persistent receiver role.
- The backend exposes manual start/stop/status controls for validation and future UI integration.
- The decoder uses stable RTL EEPROM serial ownership: `00000978`.
- The decoder binary is app-owned: `runtime/bin/dump978-fa`.
- The UAT JSON and raw message ports are loopback-only by default.

## Endpoints

- `GET /api/uat/status`
- `GET /api/uat/status.json`
- `POST /api/uat/start`
- `POST /api/uat/stop`

The normal `/api/status` payload is also enriched with `uat_978` so the UI can discover UAT capability without starting the decoder.

## Validation

Run on the Pi:

```bash
./tools/pi5_validate_uat_backend_api.sh
```

The validator starts the decoder manually, verifies the JSON port opens, confirms `/api/status` is enriched, then stops the decoder and verifies no UAT process remains.
