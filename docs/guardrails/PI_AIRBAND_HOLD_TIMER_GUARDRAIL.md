# PI Airband Hold Timer Guardrail

Airband scanning has two different thresholds:

- Activity threshold: decides whether a candidate should enter HOLD.
- Playback squelch: decides whether held audio is audible and should keep the HOLD alive.

## Required behavior

- A detected Airband signal should enter HOLD.
- HOLD must stay active until there have been 7 continuous seconds without audible/valid held audio.
- Lowering playback squelch while a signal is held must be able to reset the 7-second timer.
- An unmuted playback chunk delivered to the browser must reset the 7-second timer.
- The HOLD release timer must not keep using `airband_activity_threshold_rms * 0.70` after the operator lowers playback squelch.
- Missing short audio chunks should not immediately release HOLD; they should only contribute to quiet time until the 7-second limit is reached.

## Evidence

After the scanner stability fixes, the scanner could detect and play Airband audio, but it released HOLD too quickly and lowering squelch did not reset the release timer. The root issue was that HOLD quiet detection was still bounded by the activity threshold and browser playback did not feed audible state back into the backend timer.
