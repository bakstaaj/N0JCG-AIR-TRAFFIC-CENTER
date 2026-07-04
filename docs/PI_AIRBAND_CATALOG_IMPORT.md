# Pi FAA Airband Catalog Import

The Airband scanner depends on runtime FAA NASR FRQ catalog data at:

```text
runtime/settings/faa_airband_catalog.json
```

This file is runtime data and is not committed to Git. The backend loads it through `AirbandCatalog` and `/api/airband/channels` filters it by the configured receiver location and Airband radius.

## Import from FAA FRQ CSV ZIP

Copy the FAA NASR FRQ CSV ZIP to the Pi, then import it:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_import_faa_airband_catalog.sh /tmp/FAA_NASR_2026-05-14_FRQ_CSV.zip
```

The import helper writes `runtime/settings/faa_airband_catalog.json`, restarts `pi-air-traffic-tracker.service` if it is active, and validates that `/api/airband/channels` returns nearby channels.

## Validate catalog visibility

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_validate_airband_catalog.sh
```

Run the active NOAA/Airband validator only after catalog validation returns `FINAL: PASS`:

```bash
./tools/pi5_validate_active_noaa_airband.sh
```

## Notes

The Airband scanner cannot start in traditional mode when the channel list is empty. If `/api/airband/channels` returns `channel_count=0`, debug the catalog import, catalog path, receiver location, and radius before debugging SDR audio or scanner logic.
