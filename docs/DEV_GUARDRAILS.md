# PI Air Traffic Tracker Development Guardrails

This file records project-specific rules learned during development. Keep it updated whenever workflow corrections or script preferences are discovered.

## Supported Development Environment

- Use Windows MSYS2 UCRT64 as the supported development environment for repo staging and script handoff.
- Keep commands and scripts compatible with MSYS2 UCRT64 paths such as `~/sdrdev` and `/c/Users/jim/Downloads`.
- The target runtime is Raspberry Pi 5 running Trixie full.
- Do not assume an Ubuntu development server for this project unless explicitly requested.

## Script Handoff Rules

- Prefer a single directly downloadable `.sh` script for non-trivial command sequences.
- Do not provide zip bundles as the primary handoff unless there is a strong reason.
- Scripts should be runnable from the repository root unless clearly stated otherwise.
- Staging scripts that create the repository may run from any MSYS2 directory, but must clearly say that in the header and response instructions.
- Scripts should validate that they are being run from the expected repo root before making repo-local changes when practical.
- Scripts should be idempotent where practical.
- Scripts should create backups before modifying existing project files when overwriting user-edited files is possible.
- Scripts should print clear PASS/FAIL status messages.
- Every downloadable script handoff must include exact MSYS2 run instructions in the response that links the script.

## No Blocking Output In Scripts

- Do not put `git diff`, `git log`, `git show`, or similar commands in scripts unless their output is used for a PASS/FAIL test.
- Do not invoke commands that may open a pager and stop the script at a `:` prompt.
- If repository state needs to be summarized, use non-paging checks such as:
  - `git status --short --branch`
  - `git diff --name-only --exit-code` only when testing clean/dirty state
  - `git diff --check` only when testing whitespace/errors
- If a script ever must call a Git command that could page, force no pager with `GIT_PAGER=cat` or `--no-pager`.

## Validation Style

- Use actual PASS/FAIL checks, not visual inspection.
- Recommended validations:
  - `bash -n` for shell scripts
  - `python3 -m py_compile` for Python scripts
  - `node --check web/app.js` when Node is installed
- Do not rely on grep/diff output that the operator must visually inspect as the only validation.

## `set -e` / Diagnostic Script Guardrails

- `set -Eeuo pipefail` is allowed, but every optional probe must be written so it cannot abort the script accidentally.
- Warning helpers must return success (`0`). A warning should increment a warning count, print `WARN: ...`, and continue.
- Optional checks must not be implemented as bare commands under `set -e`.
- Use explicit `if command; then pass ...; else warn ...; fi` blocks for optional checks.
- Use explicit `if command; then pass ...; else fail ...; fi` blocks for required checks that should count a failure but still reach the final summary.
- Only true precondition failures should exit immediately, such as running from the wrong directory or a missing required input file.
- Diagnostic scripts should always reach a final PASS/FAIL summary unless a true precondition prevents safe execution.
- Commands expected to return nonzero during probing, such as `curl`, `grep`, `ssh`, or HTTP checks, must be wrapped with `if`, `case`, or `|| true` so `set -e` does not terminate the script.
- Avoid helper functions that return nonzero for warnings when those helpers are called directly in the main flow.
- For pipelines under `pipefail`, handle expected no-match cases explicitly. Do not let a normal `grep` miss abort the whole script.
- When collecting diagnostic artifacts, prefer recording the failure in the report and continuing over stopping early.

## Current Project Scope

- Target repository: `bakstaaj/PI-AIR-TRAFFIC-TRACKER`.
- Target hardware roles:
  - FlyCatcher ADS-B 1090 MHz side: primary ADS-B receiver.
  - NESDR Nano2+: NOAA Weather Radio and civil airband AM receiver.
  - FlyCatcher UAT 978 MHz side: reserve and detect for later integration.
- The first porting checkpoint is a functional port of `RTL-WINDOWS-ADS-B-TRACKER` behavior to Pi-native runtime/service paths.
- Do not integrate UAT into the application until ADS-B 1090 plus NOAA/Airband are stable on the Pi.

## Maintenance Rule

When new feedback is given about scripts, deployment, build workflow, supported environment, or project scope, add it here before or alongside the next patch.

## Python Source Portability Guardrails

- Python files copied from Windows must not contain unescaped Windows paths such as `C:\Users` inside normal Python string literals or docstrings; use raw strings, escaped backslashes, or MSYS2/POSIX paths.
- Every source-copy or port-staging script must run Python compile validation across the copied Python files before reporting final success.
- A copied baseline that fails Python compilation must be fixed in the port repo before the initial baseline commit.
- When this class of failure is found, update this guardrails document before or alongside the patch that fixes it.

## Local Backup Artifact Guardrails

- Script-created backup directories such as `.port_fix_backups/` and `.commit_baseline_backups/` are local recovery artifacts.
- These backup directories should be ignored by Git and should not be committed to the repository.
- If a fix script creates a new backup directory pattern, update `.gitignore` and this guardrails document before or alongside the patch.

## PI Air Traffic Tracker Pre-Hardware Rule\n\n- Before FlyCatcher/Nano2+ hardware arrives, it is acceptable to add documentation, config templates, no-device validation scripts, and Pi runtime readiness checks.\n- Do not hard-code RTL device indexes before live Pi enumeration evidence is collected.\n- Do not enable UAT runtime features until the project explicitly moves to the UAT phase; reserve/configure UAT role only.\n- Keep ADS-B 1090 on the FlyCatcher ADS-B side and NOAA/Airband on the external NESDR Nano2+ for the first hardware milestone.\n- Hardware-dependent backend patches must be based on actual \, \, USB, and service/runtime evidence collected from the Pi.

## Ignored Runtime Template Guardrail\n\n- Runtime directories such as `runtime/settings/` may be broadly ignored to protect local state.\n- If a version-controlled template must live under an ignored runtime path, scripts must stage only the exact intended template with `git add -f <path>`; do not broadly unignore or stage runtime state.\n- Scripts must wrap `git add` operations in explicit PASS/FAIL checks so ignored-path failures do not abort before the final summary.\n- Prefer canonical documentation/templates under `docs/` for future templates unless the runtime path is required by the application.

## Git Whitespace Auto-Fix Guardrail\n\n- If `git diff --check` fails after a generated patch, fix scripts should normalize only the intended touched files instead of broad-formatting the repository.\n- Whitespace fix scripts should remove CRLF endings, strip trailing spaces/tabs, ensure final newlines, then rerun `git diff --cached --check` as a PASS/FAIL validation.\n- If whitespace validation still fails, scripts should write the check output to an ignored report file and still reach the final PASS/FAIL summary.

## Staged Whitespace Recovery Guardrail

If `git diff --cached --check` fails after a generated patch, do not visually inspect and hand-edit files as the primary workflow. Use a repo-root repair script that backs up the intended files, unstages the pending change set, normalizes the working-tree copies, restages the corrected files, force-adds only intentional ignored templates, reruns `git diff --cached --check`, and commits only after PASS validation.

## Executable Script Tracking Guardrail

- Runnable Pi/Linux shell scripts under `tools/` must be committed with the Git executable bit set.
- A `Permission denied` result from `./tools/name.sh` after clone usually means the script content exists but Git mode was not tracked as executable.
- Immediate operator workaround is `bash ./tools/name.sh`, but the repo fix should use `chmod +x` plus `git update-index --chmod=+x` before commit.
- Executable-bit fixes must validate both `bash -n` syntax and tracked mode `100755` for intended runnable `.sh` files.

## JSON Validation Guardrail

- JSON files must be validated one file at a time.
- Do not call `python3 -m json.tool` with multiple input files in one command; it accepts one input JSON file and an optional output file.
- Use a loop with explicit PASS/FAIL accounting for multi-file JSON validation.

## Executable-Bit Scope Guardrail

- Executable-bit fixes should be scoped to scripts required by the active workflow.
- Do not mass-stage executable-bit changes for unrelated copied scripts unless that broad cleanup is the explicit task.
- When a mass chmod accidentally touches unrelated scripts, unstage, restore the unrelated paths, then stage only the intended workflow files.

## Generated Local Report Directory Guardrail

- Any repo-root diagnostic report or backup directory created by a workflow script must be ignored in `.gitignore` before or alongside the script that creates it.
- Push/pre-push validation scripts must not fail because of local report directories that were generated by earlier workflow scripts.
- Prefer writing transient reports under a clearly named ignored directory, and only commit the source fix plus the guardrail update.

## Pi Runtime Dependency Guardrails

- A no-hardware preflight with missing `rtl_*`, `sox`, or ADS-B decoder tools is not a backend failure until the Pi runtime dependency bootstrap has been run.
- Pi runtime install scripts should validate package-manager availability, install available packages, and treat unavailable optional ADS-B decoder packages as warnings instead of aborting.
- Do not hard-code RTL device indexes or serial-role mappings until live FlyCatcher + Nano2+/RTL enumeration evidence has been collected on the target Pi.
- Dependency scripts may create local report folders, but those folders must be ignored in `.gitignore` before or alongside the script that creates them.
- Runtime dependency validation must check commands directly, not rely on visual inspection of apt output.

## Active Source Validation Scope

- Validation scripts must not compile or lint generated backup/report folders such as `.port_fix_backups/`, `.exec_bits_json_scope_reports/`, or other dot-prefixed local workflow artifacts.
- Prefer `git ls-files` for tracked source validation, plus explicit known new files created by the current patch, instead of broad `find .` scans.
- JSON validation must run one file at a time with `python3 -m json.tool <file>`; do not pass multiple JSON files to a single invocation.
- Any script that creates local backup/report folders must ignore those folders in `.gitignore` before or alongside the script change.

## Executable Mode Guardrail

- Any repo script intended to be run directly as `./tools/name.sh` on the Raspberry Pi must be committed with executable mode (`100755`).
- Patch scripts that add new Pi runtime scripts must validate the tracked file mode before committing.
- If a Pi pull reports `Permission denied` for a repo script, run it once with `bash ./tools/name.sh` as the immediate workaround, then fix and commit the executable bit from the development repo.

## Pi Script Executable Mode Guardrails

- Pi-side tools intended to run as `./tools/name.sh` must be committed with Git mode `100755`.
- On Windows/MSYS2, do not rely on `chmod +x` alone for Git mode changes; use `git update-index --chmod=+x <path>` for tracked executable scripts.
- Validate executable mode with `git ls-files -s -- <path>` and treat any mode other than `100755` as a FAIL before commit.
- A Raspberry Pi `Permission denied` on a repo script can be worked around immediately with `bash ./tools/name.sh`, but the repo must still be fixed so future pulls execute directly.

## Pi 5 FlyCatcher Serial Mapping Guardrail

The Pi 5 FlyCatcher/NESDR target should use stable EEPROM serials for receiver roles after live enumeration confirms them: NESDR Nano2+ NOAA/Airband serial 00000162, FlyCatcher ADS-B serial 00001090, and FlyCatcher UAT serial 00000978. Do not hard-code RTL indexes in backend code; resolve runtime indexes from serials during startup and keep UAT disabled until that milestone is explicitly enabled. If EEPROM serials are changed, rerun the Pi serial mapping validator before patching backend ownership.

## Hardware Mapping Evidence Guardrail

Hardware role commits must include the evidence source and validator path. A preflight that previously saw duplicate FlyCatcher serials must be superseded by a new serial-validation run before backend mapping is changed.

## Pi Validator Executable Mode Recovery

- MSYS2 executable-mode recovery for newly added Pi validator scripts: when a new
  Pi tool is meant to run as `./tools/name.sh`, force the executable bit into
  Git's index with `git update-index --chmod=+x tools/name.sh` before validating
  the staged mode.
- Validate the mode from Git's staged index with `git ls-files -s -- tools/name.sh`;
  do not rely only on the Windows/MSYS2 filesystem mode.

## Pi backend serial receiver ownership\n\n- The Pi 5 FlyCatcher/NESDR target owns receivers by stable RTL EEPROM serials: 00001090 for ADS-B 1090, 00000162 for NOAA/Airband, and 00000978 for UAT.\n- Backend code must resolve runtime RTL indexes from serials at startup and must not hard-code indexes.\n- Product labels from rtl_test are diagnostic only after EEPROM serials are assigned; serial ownership is the source of truth.\n- The first Pi backend milestone should add a Pi-specific shim instead of modifying the Windows baseline backend directly.

## Pi Backend Startup Guardrails

- Pi backend autostart must not block the HTTP API while waiting for `aircraft.json`; `readsb` may be healthy before any live ADS-B frames are decoded.
- Startup validation should treat a live decoder process plus resolved serial roles as sufficient for initial PASS, while separately warning if `aircraft.json` is not present yet.
- Validators that launch the backend with `--autostart` must allow enough time for serial probing plus decoder process checks before declaring the HTTP port unreachable.

## Pi readsb RTL-SDR Guardrails

- Do not assume the Debian/Raspberry Pi OS `readsb` package can own an RTL-SDR just because `/usr/bin/readsb` exists.
- Validate RTL-SDR support by checking that `--device-type rtlsdr` is accepted; package builds may list generic RTL-SDR text in usage but still report `SDR type 'rtlsdr' not recognized`.
- For this Pi 5 FlyCatcher/NESDR target, prefer an app-owned readsb binary under `runtime/bin/readsb` or `bin/readsb`, matching the proven RTL-Pi-ADS-B-TRACKER pattern.
- Backend code must select the ADS-B receiver by EEPROM serial `00001090`, not by a hard-coded Linux runtime index.
- Keep the system/package `readsb.service` disabled unless explicitly testing package behavior, so it does not own the ADS-B SDR.
- If readsb exits before the backend binds HTTP, capture the app-owned readsb log and the backend stdout before changing code.

## App-owned readsb commit recovery

- The Pi Air Traffic Tracker must not rely on Debian-packaged `readsb` unless a validation proves that `--device-type rtlsdr` is recognized.
- Use the app-owned RTL-SDR-enabled `readsb` binary path first for Pi ADS-B operation.
- Patch scripts that create tracked source changes must either create the commit themselves after PASS/FAIL validation or clearly state that they intentionally leave changes uncommitted.
- Before pushing, no tracked patch files should remain unstaged and no intended new tool should remain untracked.
- New Pi tool scripts intended to run as `./tools/name.sh` must be staged with Git mode `100755` using `git update-index --chmod=+x` when MSYS2 does not preserve executable mode automatically.

## Pi API status contract guardrail
- When the Pi backend shim adds Pi-specific runtime ownership fields, `/api/status` must expose them through the active HTTP handler, not only through an internal manager method.
- Keep the Windows/Pi-port baseline module unchanged when practical; prefer Pi-shim monkey patches or wrappers for Pi-specific API contract fields such as `receiver_roles`, `decoder`, app-owned `readsb` path, and serial-role diagnostics.
- Treat a running decoder and a passing API validator as separate requirements. A healthy `readsb` process is not enough if `/api/status` does not expose the fields that validators and UI code depend on.
- Recovery scripts for API-contract mismatches must update this guardrail file before or alongside the code fix.

## Patch commit and push guardrail
- A patch script may include `git push` only after all local validations and the commit step pass.
- Never push when validation, whitespace checks, executable-mode checks, or commit creation fail.
- Before staged whitespace validation, normalize touched text files so they use LF line endings, no trailing whitespace, and exactly one final newline with no blank line at EOF.
- If a script creates local report or backup directories, add them to `.gitignore` before repository cleanliness or push validation.
- When a patch script intentionally leaves changes uncommitted or unpushed, it must say so explicitly in the final output.

## Pi service and UI smoke-test guardrails
- Validate the Pi web/API runtime in foreground/dev mode before installing or changing systemd service behavior.
- Pi service installers must disable the distro `readsb.service` so it cannot own the ADS-B receiver; the app backend starts app-owned `runtime/bin/readsb`.
- Systemd service units for the Pi tracker must run from the checked-out repo root, set `RTL_ADSB_TRACKER_RUNTIME` to the repo `runtime` directory, and expose the web UI on `0.0.0.0:8090` by default.
- Service and smoke validators must prove `/api/status`, `/api/aircraft.json`, `/`, `/app.js`, and `/app.css` respond before declaring PASS.
- Patch scripts that include push must only push after repo validation, staged whitespace validation, commit success, and a clean post-commit state.

## Pi live functional validation
- Live functional validators should run against the service without changing receiver settings or starting long-running scans unless the milestone explicitly says so.
- Separate hard service/API failures from RF-environment warnings. A healthy decoder with no ADS-B message increase during a short indoor/quiet observation window should warn, not fail.
- Validate the Pi `/api/status` contract, app-owned readsb command, receiver serial roles, UI assets, aircraft JSON, NOAA capture, and passive Airband endpoints before treating the Pi service as operational.
- Patch scripts may push to origin only after all local validation passes and the intended commit succeeds. If validation fails, do not push.
- For large generated shell payloads, prefer shell here-docs and validate generated scripts with `bash -n`; avoid fragile nested quote generators that can fail before writing files.

## Patch script validation recovery rules
- Patch scripts that use generated helper code must avoid fragile nested quoting patterns when shell here-docs are sufficient.
- Python source validation must use `git ls-files '*.py'` as the source of truth, must report the actual tracked file count, and must not mark a successful zero-file validation as a failed compile.
- Patch scripts must normalize touched text files before `git diff --cached --check` so blank EOF/trailing whitespace failures are caught before commit and never pushed.
- Patch scripts may run `git push` only after repository validation, staging, executable-mode checks, staged whitespace checks, and commit all pass.
## Pi readsb process liveness guardrail

- The Pi backend must not treat the mere existence or readability of `aircraft.json` as proof that `readsb` is currently running.
- Stale `runtime/settings/readsb-json/aircraft.json` files can remain after service restarts and must not short-circuit ADS-B decoder startup.
- `PiSerialDecoderManager.is_running()` must reflect the backend-owned child process state; status/reporting code may read JSON for telemetry, but startup gating must launch `readsb` when no child process is alive.
- Fresh-start validators should stop the service, leave a stale JSON sentinel, restart the service, and confirm app-owned `runtime/bin/readsb` is launched for serial `00001090`.
## Patch-script local artifact guardrail

- Patch scripts that create report or backup directories must ignore their own local artifact roots during preflight clean-tree checks.
- Add known script-local roots such as `.pi_*_reports/` and `.pi_*_backups/` to `.gitignore` before staging, but do not fail only because the current script created its report directory.
- Clean-tree checks should still fail on unrelated source, docs, runtime template, or tool changes.

## Fresh-start validator status readiness guardrail

Fresh-start validators that restart the Pi service must wait for a stable, non-empty, parseable `/api/status` response that includes the required Pi contract fields before extracting JSON values. A transient empty response or partially initialized status response must be retried until timeout, not treated as a final source failure. Backend fixes and validator defects must remain separated: if process evidence and later live functional validation pass, repair the validator rather than reworking runtime code.

## Pi active NOAA/Airband validation guardrail

Active audio validation must be handled as an operational test, not a pure API smoke test. Scripts may start and stop NOAA live audio and Airband scanning, but they must restore settings where practical, stop shared-audio modes on exit, and treat live Airband voice hits as conditional RF events. Required Airband validation is scanner start, observable active/searching/scanning state, and clean stop; held-channel audio and skip/block controls are PASS when available and WARN when no live transmission is captured.

## Patch script cleanliness guardrail

Patch/recovery scripts must not fail merely because unrelated untracked local artifacts exist, including generated report folders, backup folders, runtime/preflight outputs, or accidental scratch files from earlier validation runs. Scripts must stage explicit path lists, warn about unrelated untracked files that are left untouched, and fail only on unexpected tracked/staged changes outside the patch's intended file set. Report directories created by the current script must be ignored or created after the cleanliness decision so the script never fails on its own output.

## Pi Airband catalog runtime-data guardrail

- The Airband scanner depends on `runtime/settings/faa_airband_catalog.json`; this generated FAA NASR catalog is runtime data and must not be assumed present after a fresh clone or pull.
- Active Airband scanner validators must check `/api/airband/channels` before starting the scanner. If the channel list is empty, fail with an actionable catalog-import prerequisite instead of treating it as an SDR/audio failure.
- Use `tools/pi5_import_faa_airband_catalog.sh` to import a FAA FRQ CSV ZIP and restart/revalidate the service. Use `tools/pi5_validate_airband_catalog.sh` before active Airband scanner validation.
- Patch scripts must ignore unrelated untracked local artifacts and known report/backup directories during preflight; they must stage explicit intended paths only and fail only on unexpected tracked/staged changes outside the patch set.

## Active Airband validator catalog guardrail

Active Airband validation must match the supported runtime modes. Do not force traditional catalog-based scanning when `/api/airband/channels` is empty. Treat an empty nearby FAA catalog as a warning for catalog/list validation, then validate scanner start/stop through `fast_spectrum`, which is the Pi default and can operate on unlisted 120-130 MHz channels.

## Patch clean-tree guardrail for local artifacts

Patch scripts must stage explicit intended files and must not fail only because unrelated untracked local artifacts exist, including report directories, backup directories, scratch files, or accidental numeric filenames. Warn about unrelated untracked paths, ignore them for patch cleanliness, and fail only on unexpected tracked/staged changes outside the patch set.

## Release checkpoint and tag guardrail

Release checkpoint scripts must update README/release/validation documentation from the validated runtime state, then run repository validation before commit, push, or tag creation. Tags must never be created before validation and commit succeed. If a requested tag already exists remotely, the script must not delete or overwrite it automatically; it should warn and skip or require an explicit new tag name.

## Airband scanner recoverable warning guardrail

Do not overload fatal status fields with recoverable scanner observations. For Airband scanning, `airband_scan_error` is reserved for fatal scanner failures that move the scanner to `error` or prevent operation. Per-candidate/per-channel audio capture misses while the scan loop remains active must be exposed through warning fields and must be downgraded to WARN in validators.
- Active service validators that may be run immediately after `systemctl restart` must include an explicit readiness wait for `/api/status` before counting endpoint failures. Connection-refused during startup is a readiness condition, not a feature failure.

## Release tag finalization guardrail

- Do not force-move release tags after validation fixes land. If a primary release tag already exists and does not point at the final validated commit, create a successor validated tag instead.
- Finalizer scripts must fetch tags before deciding whether to create a tag and must stage only explicit documentation/checkpoint files.

## Pi V0.1 acceptance bundle guardrail

When a milestone has several hardware validators, add or maintain a single acceptance bundle that runs the required validators and emits one top-level `FINAL: PASS`/`FINAL: FAIL` summary. The bundle may warn on optional runtime data, such as the FAA Airband catalog, but required runtime paths must remain hard failures.

## V0.2 UAT integration guardrail

UAT work must start with a non-invasive Pi capability probe. Keep the `00000978` UAT receiver disabled in the persistent backend until the probe proves serial detection, exclusive receiver access, 978 MHz tuning/capture, and available decoder tooling. UAT patch scripts must preserve the validated V0.1 ADS-B, NOAA, Airband, and acceptance validation paths.

## UAT raw capture guardrail

Do not fail a UAT hardware milestone from a single `rtl_sdr` option combination. Resolve the receiver from the stable EEPROM serial first, then try a bounded capture matrix covering runtime index, stable serial, sample-rate candidates, and gain argument styles. Treat the milestone as hardware-ready when raw IQ bytes are captured; keep decoder installation and persistent service enablement in separate later milestones.

## UAT decoder tooling guardrail

Do not enable a persistent UAT 978 MHz decoder service until the app-owned decoder binary is installed, the UAT serial opens through SoapySDR by EEPROM serial, and the existing V0.1 ADS-B/NOAA/Airband acceptance suite remains green. UAT patch milestones must keep serial `00000978` isolated from the running ADS-B and audio receivers.

## UAT dump978 validator timeout guardrail

For non-persistent decoder startup probes, `timeout` exit code 124 can mean the
receiver opened successfully and the decoder stayed alive until the validator
stopped it. Do not classify rc=124 as a startup failure unless the captured log
also contains a known fatal SDR/configuration pattern.
- UAT `dump978-fa` startup validators must classify GNU `timeout` exit code 124 as success before broad log scanning, unless a strong pre-timeout SDR/configuration error is present.

### dump978 timeout classifier guardrail
- In non-persistent UAT decoder probes, `timeout` exit code 124 is success when `dump978-fa` stays alive until the controlled stop.
- Classify rc=124 before broad log scanning; shutdown logs can include generic error text even when SDR startup succeeded.

### UAT manual backend control guardrail

UAT 978 MHz work must keep persistent UAT autostart disabled until a dedicated acceptance gate proves service behavior. V0.2 backend API work may expose manual `/api/uat/start`, `/api/uat/stop`, and `/api/uat/status` controls using serial `00000978`, but it must not disturb ADS-B, NOAA, or Airband runtime ownership.

## Guardrail folder index — UAT 978 backend API

- `docs/guardrails/PI_UAT_978_BACKEND_API_GUARDRAIL.md` — V0.2 UAT manual backend API controls, serial ownership, no autostart, app-owned `dump978-fa`, and validator executable-mode requirements.
