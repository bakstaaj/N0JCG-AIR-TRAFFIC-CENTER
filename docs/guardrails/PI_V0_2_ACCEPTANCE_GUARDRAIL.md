# PI V0.2 Acceptance Guardrail

V0.2 acceptance must validate the complete UAT integration path without requiring live 978 MHz aircraft to be present.

Required checks:

- Wait for `/api/status` JSON before any API endpoint validation. `systemctl is-active alone is not sufficient` because the service can be active before port 8090 is listening.
- Treat zero 978 MHz aircraft as acceptable when the UAT decoder and collector are running or idle without fatal errors.
- Treat socket/readline idle timeouts in the UAT JSON collector as no-data conditions, not as decoder failures.
- Keep the aircraft user experience unified: enabled 1090 ADS-B and 978 UAT sources must feed the same `/api/aircraft.json`, map, aircraft table, and detail dialog.
- Keep browser refresh paused while the menu drawer is open so operator source switches are not disrupted by periodic status refreshes.
- Restore traffic source settings after validators that temporarily enable or disable sources.

## Menu refresh pause requirement

The V0.2 acceptance gate must preserve the menu refresh pause behavior: browser status, aircraft, and operation polling must pause while the configuration menu is open so the 1090 ADS-B and 978 UAT traffic source switches remain usable. Closing the menu may trigger one catch-up refresh.


- The V0.2 acceptance validator must expose RUN_V0_1_BASELINE=1 as the optional V0.1 baseline switch.

## Recovery guardrails

- UAT hardware capability compatibility validator must be executable at `tools/pi5_validate_uat_978_capability.sh` and may validate serial/role visibility without exclusive receiver capture when the service is already running.
- Static scans may warn on legacy timeout text; runtime /api/uat/status decides collector pass/fail for idle 978 UAT operation.
