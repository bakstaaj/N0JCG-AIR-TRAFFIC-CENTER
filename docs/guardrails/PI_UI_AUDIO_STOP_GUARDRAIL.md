# PI UI Audio Stop Guardrail

NOAA Weather and Airband scanning share the same NOAA/Airband SDR. The browser UI must never let background refresh, polling, reconnect logic, or status reconciliation accidentally stop an active receiver mode.

## Required behavior

- Automatic refresh may poll `/api/status`, `/api/airband/scan/status`, and aircraft endpoints.
- Automatic refresh must not POST stop commands.
- Stop commands for `/api/noaa/live/stop` and `/api/airband/scan/activity/stop` should originate from a recent operator action such as clicking a stop/toggle button, NOAA rescan, Airband tuning change, or receiver-setting change.
- The browser should audit allowed and blocked stop attempts in `window.__piAudioStopGuard`.
- The backend should log all NOAA/Airband control POSTs with the path, query string, client, user agent, referer, and UI stop-guard header.
- Normal scanner/audio diagnostics that run without a browser are still valid backend health checks. If backend diagnostics pass but browser operation stops early, inspect the audio control POST audit log.

## Runtime evidence commands

```bash
journalctl -u pi-air-traffic-tracker.service --no-pager | grep AUDIO_CONTROL_POST | tail -n 40
```

In the browser developer console:

```javascript
window.__piAudioStopGuard
```
