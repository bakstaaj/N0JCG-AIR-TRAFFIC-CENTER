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
