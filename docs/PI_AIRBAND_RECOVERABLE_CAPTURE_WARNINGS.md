# Pi Airband Recoverable Capture Warnings

## Problem

Fast-spectrum Airband scanning can occasionally identify a candidate carrier and then fail to collect a short AM validation WAV chunk. One observed runtime message was:

```text
Audio capture ended before samples were received.
```

That condition is recoverable when the scanner remains active. It should not be reported as a fatal `airband_scan_error`, and validation should not fail solely because a single candidate produced no samples.

## Change

The scanner now keeps fatal scan failures in `airband_scan_error` and records recoverable per-candidate/per-channel capture misses in:

```text
airband_scan_warning
airband_last_warning
airband_recoverable_capture_errors
```

A successful capture clears the current `airband_scan_warning`.

The active NOAA/Airband validator now treats the known no-samples capture miss as a warning when the scanner is still running in `spectrum_searching` or `searching` state.

## Validation

Run on the Pi after pulling the patch and restarting the service:

```bash
cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER
sudo systemctl restart pi-air-traffic-tracker.service
./tools/pi5_validate_active_noaa_airband.sh
```

Expected result:

```text
FINAL: PASS
```

No live Airband transmission during the test window may still produce warnings for unexercised live audio/skip/block behavior.
