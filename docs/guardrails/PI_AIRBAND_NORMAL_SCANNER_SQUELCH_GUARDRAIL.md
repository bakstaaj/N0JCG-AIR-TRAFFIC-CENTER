# PI Airband Normal Scanner Squelch Guardrail

Airband scanner hold must behave like a normal radio scanner.

## Required behavior

- Activity threshold controls when a carrier/audio candidate enters HOLD.
- Playback squelch controls whether the held channel is open or closed.
- If playback squelch is off or `0`, squelch is open: static/noise plays and HOLD must not release because of the 7-second quiet timer.
- If playback squelch is above the noise floor, audio is muted while below threshold.
- Only 7 continuous seconds of closed squelch should release HOLD and resume scanning.
- Any open squelch event must reset the timer to zero.
- Lowering playback squelch while held must immediately recalculate open/closed state and reset the timer if the held RMS is above the new threshold.
- The UI must display HOLD frequency, squelch OPEN/CLOSED state, RMS, quiet seconds, and remaining release time.

## Evidence

After scanner stability fixes, the scanner stayed running and played held audio, but HOLD did not behave like a normal scanner: squelch-off did not hold static open, and lowering squelch did not reset the 7-second timer. This guardrail prevents future regressions by tying release behavior directly to playback squelch state.
