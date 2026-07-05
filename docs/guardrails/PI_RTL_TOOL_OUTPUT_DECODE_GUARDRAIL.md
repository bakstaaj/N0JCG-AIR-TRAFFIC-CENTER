# PI RTL Tool Output Decode Guardrail

RTL command-line tools can emit non-UTF-8 bytes on stdout or stderr. Python subprocess calls must not allow those bytes to crash receiver workflows.

## Required behavior

- Any `subprocess.run(..., capture_output=True, text=True)` used around RTL tools, decoder probes, `rtl_power`, `rtl_fm`, `rtl_eeprom`, or readsb helpers must include:
  - `encoding="utf-8"`
  - `errors="replace"`
- Non-UTF-8 tool output must be preserved in logs with replacement characters rather than raising `UnicodeDecodeError`.
- Airband scanner worker threads must not stop because a diagnostic child process wrote invalid UTF-8 bytes.
- If a command fails, the failure should be reported as a command exit/status problem, not as a Python text-decoding exception.

## Evidence

The UI-start Airband monitor on July 4, 2026 showed the browser sent only `/api/airband/scan/activity/start`, no `/stop`, and the backend later stopped with:

```text
'utf-8' codec can't decode byte 0xd6 in position 26: invalid continuation byte
```

That means the scanner was stopped by backend subprocess-output decoding, not by UI refresh state.
