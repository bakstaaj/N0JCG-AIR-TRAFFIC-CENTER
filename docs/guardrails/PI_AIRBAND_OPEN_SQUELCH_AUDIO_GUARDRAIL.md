# PI Airband Open Squelch Audio Guardrail

Airband hold audio must behave like a normal scanner speaker.

## Required behavior

- Squelch off means open audio. The browser must receive audible open audio/static while the channel is held.
- The live Airband audio endpoint must not return repeated 204/no-content responses while squelch is off and hold is active.
- Above the noise threshold, the UI squelch label is the numeric value plus `muted` when the squelch is closed, for example `300 muted`.
- When open above the threshold, the UI squelch label is only the numeric value, for example `300`.
- Off/open squelch is labeled `off`.
- HOLD status must be visible in both Operations and Airband scan status while a channel is held.
