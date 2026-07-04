# Pi UAT 978 Backend API Guardrail

UAT 978 MHz support is a V0.2 capability layered on top of the validated V0.1 Pi runtime. Keep UAT isolated from the existing ADS-B 1090, NOAA, and Airband paths until the explicit UAT validators pass.

## Rules

- Use the stable RTL EEPROM serial `00000978` for UAT; do not hard-code Linux runtime device indexes.
- Keep UAT disabled for persistent autostart unless a later milestone explicitly enables it.
- Use app-owned `runtime/bin/dump978-fa` and `runtime/bin/skyaware978`; do not depend on unmanaged system binaries for runtime behavior.
- Expose UAT through manual API controls first: `/api/uat/status`, `/api/uat/start`, and `/api/uat/stop`.
- Starting UAT must not stop or reconfigure the ADS-B 1090 decoder.
- UAT start/stop validation must leave the decoder stopped at the end of the test.
- `/api/status` may report UAT capability and current state, but it must not imply UAT autostart is enabled.

## Required validation

Run this on the Pi after backend API changes:

```bash
./tools/pi5_validate_uat_backend_api.sh
```

Expected result:

```text
FINAL: PASS
```
