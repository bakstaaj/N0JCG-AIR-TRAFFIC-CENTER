# PI UAT Map Icon Guardrail

The aircraft map remains a unified traffic display for 1090 ADS-B and 978 UAT sources. Do not split UAT traffic into a separate aircraft map or list.

## Required marker behavior

- Keep 1090 ADS-B traffic on the existing jet-style aircraft map marker.
- Show 978 UAT traffic with a same-style prop-plane marker.
- Use source metadata from merged aircraft records, including `source`, `sources`, or `source_label`.
- Keep the marker label and click/double-click aircraft detail behavior unchanged.
- If a record includes UAT source metadata, the marker may use the prop-plane icon even when the aircraft is part of the unified `/api/aircraft.json` feed.
- Do not require live UAT aircraft to validate static marker behavior; source-aware icon selection can be validated from code markers and a synthetic aircraft record.

## Rationale

UAT 978 MHz traffic is commonly associated with general aviation. A prop-plane marker gives the operator an immediate visual cue that the aircraft came from the 978 UAT path while preserving the same unified map and details workflow as 1090 ADS-B traffic.
