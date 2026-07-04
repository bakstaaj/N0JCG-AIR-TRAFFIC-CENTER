# Guardrail: Unified Traffic Source Merge

Traffic sources must feed the same aircraft map/list UI unless there is a deliberate product decision to split the UI.

Required behavior:

- Do not create a separate UAT-only aircraft map as the default display.
- Keep `/api/aircraft.json` as the browser's unified aircraft feed.
- Preserve source attribution on merged records.
- Persist operator source switches under the runtime settings directory.
- Default ADS-B 1090 to enabled and UAT 978 to disabled.
- Do not hard-code RTL device indexes; source control must continue to use stable serials.
- Do not autostart UAT from systemd in V0.2; it is enabled by operator setting and app-owned backend control.

## Validator readiness requirement

Traffic-source validation must wait for `/api/status` to return JSON after a
systemd restart before exercising `/api/settings/traffic-sources`,
`/api/aircraft.json`, or `/api/uat/status`. `systemctl is-active` alone is not
a sufficient readiness check because the Python HTTP listener can still be
initializing after systemd reports the process active.

## HTTP readiness requirement

Any validator that restarts `pi-air-traffic-tracker.service` or validates newly-added API endpoints must wait for the HTTP API to return valid JSON from `/api/status` before testing feature endpoints. systemctl is-active alone is not sufficient because the service can be active before the Python HTTP server has bound port 8090.

If HTTP readiness fails, the validator must capture useful startup evidence, including `systemctl status pi-air-traffic-tracker.service` and recent `journalctl -u pi-air-traffic-tracker.service` output, before returning `FINAL: FAIL`.
