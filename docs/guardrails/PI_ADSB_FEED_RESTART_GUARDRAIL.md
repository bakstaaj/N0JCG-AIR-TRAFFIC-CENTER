# PI ADS-B Feed Restart Guardrail

The active aircraft list must not clear just because the HTTP UI polls while readsb is restarting or failing.

## Required behavior

- Do not delete `runtime/settings/readsb-json/aircraft.json` before every readsb start attempt.
- `/api/aircraft.json` polling must not restart readsb every 2 seconds.
- A failed or short-lived readsb process must enter a restart backoff before another on-demand start.
- The backend should cache the last valid aircraft payload and serve it with stale/recovery metadata while readsb restarts.
- UI polling may show stale/recovering metadata, but it must not wipe the active aircraft table on every transient decoder restart.
- Logs showing repeated `Starting readsb for ADS-B serial 00001090` within a few seconds are a regression signal.

## Evidence

A July 8, 2026 debug log showed `/api/aircraft.json` polling interleaved with repeated readsb starts every few seconds. That restart loop cleared the aircraft table roughly every 2 seconds because the manager deleted `aircraft.json` on each start.
