# PI Shared Audio SDR Guardrail

NOAA Weather live audio, Airband live hold audio, Airband capture, and Airband fast-spectrum scanning all share the same physical NOAA/Airband RTL-SDR.

## Required behavior

- Use EEPROM serial `00000162` as the primary selector for the shared audio SDR.
- Do not rely only on runtime numeric RTL indexes for the shared audio SDR because index order can change as ADS-B, UAT, and audio receivers are opened by different tools.
- Before declaring NOAA live startup failed, require multiple start attempts with enough settle time to receive the first audio chunk.
- Treat `usb_claim_interface error -6`, `Failed to open rtlsdr device`, `No supported devices found`, and `Device or resource busy` during fast-spectrum startup as retryable transient receiver-claim failures.
- Keep NOAA and Airband mutually exclusive because they share the same receiver.
- Airband fast spectrum may fall back from serial selection to the resolved runtime index only after serial selection retries fail.
- Preserve the UI guard that prevents unattended stop POSTs, but diagnose scanner stops from backend state and receiver logs first when no stop POST exists.

## Evidence that drove this guardrail

The July 4, 2026 UI-stop evidence showed NOAA `/api/noaa/auto/start` sometimes failed because no live audio samples arrived after two starts, while Airband fast-spectrum failed with `usb_claim_interface error -6` and `Failed to open rtlsdr device #0`. That combination indicates shared receiver startup/release hardening rather than a UI refresh stop request.

## V2 evidence

After the first hardening patch, `latest_airband_fast_spectrum.log` showed serial selector `00000162` and fallback index `0` each failed once with `No supported devices found`. That message is also a transient receiver-discovery/claim failure on the Pi and must be retried with longer settle intervals before the scanner is marked stopped.
