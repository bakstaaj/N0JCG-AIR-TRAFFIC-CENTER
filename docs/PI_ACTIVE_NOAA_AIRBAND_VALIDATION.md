# Pi Active NOAA and Airband Validation

This validation milestone exercises active audio controls against the running Raspberry Pi service.

Run it on the Pi after the systemd service is installed and the live functional validator is passing:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
./tools/pi5_validate_active_noaa_airband.sh
```

The script validates:

- `/api/noaa/live/start`
- `/api/noaa/live/audio.wav`
- `/api/noaa/live/stop`
- `/api/settings/airband-scan`
- `/api/airband/channels`
- `/api/airband/scan/activity/start`
- `/api/airband/scan/status`
- `/api/airband/scan/activity/stop`

Airband live audio, skip, and block controls depend on live AM traffic being detected during the validation window. If no held Airband channel appears, the script reports a warning rather than a failure. The required pass condition is that active Airband scan starts, enters a searching/scanning state, and stops cleanly.

The validator temporarily switches Airband scan mode to `traditional` so it does not depend on `rtl_power` availability. It saves the current Airband tuning first and restores it at cleanup.

## Fast-spectrum fallback for empty FAA catalog

The active Airband validator must not fail only because `/api/airband/channels` is empty. Traditional scanning requires nearby FAA catalog channels, but the application default `fast_spectrum` mode can scan unlisted 120-130 MHz channels without catalog data. When the catalog returns zero nearby channels, the validator records a warning and validates Airband scanner start/stop using fast-spectrum mode.
