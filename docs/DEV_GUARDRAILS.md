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
