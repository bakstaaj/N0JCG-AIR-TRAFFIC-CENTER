# Pi SSH / sshpass Handoff Guardrail

Remote Raspberry Pi command handoffs for this project should use `sshpass` so the operator does not have to repeatedly type the Pi password during SCP/SSH upload-and-run workflows.

## Rules

- Default Pi SSH user for this project is `pi`, not `jim`.
- Generated diagnostic, patch, and validation scripts handed off from MSYS2 should be uploaded to the Pi `/tmp` directory before execution unless a repo-local path is explicitly required.
- Use `scp -O` for MSYS2-to-Pi file uploads to preserve the existing project workflow.
- Prefer command examples that set `PI_USER`, `PI_HOST`, and `PI_PASS` once, then use `sshpass -p "$PI_PASS"` for both `scp` and `ssh`.
- Do not hard-code or commit real passwords into repository files, scripts, docs, or chat handoff artifacts.
- When a script must run from the repository root, execute it through SSH as:

```bash
sshpass -p "$PI_PASS" ssh "$PI_USER@$PI_HOST" 'cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER && /tmp/script_name.sh'
```

- For longer observations, pass environment variables inside the remote command rather than editing the uploaded script, for example:

```bash
sshpass -p "$PI_PASS" ssh "$PI_USER@$PI_HOST" 'cd ~/sdrdev/PI-AIR-TRAFFIC-TRACKER && UAT_OBSERVE_SECONDS=900 /tmp/pi5_diagnose_uat_978_traffic.sh'
```

## Current Pi defaults

```text
PI_USER=pi
PI_HOST=192.168.254.63
SCRIPT_UPLOAD_DIR=/tmp
REPO_ROOT=~/sdrdev/PI-AIR-TRAFFIC-TRACKER
```

## UAT 978 diagnostic evidence note

The short UAT 978 diagnostic run on 2026-07-04 reported `23 PASS, 2 WARN, 0 FAIL`, `FINAL: PASS`. Raw capture, decoder running state, JSON port, raw port, collector state, source errors, and fatal log pattern checks all passed. The classification was healthy receiver/decoder path with no decoded 978 MHz aircraft/messages observed during the 300-second window. Treat this as a quiet/coverage/antenna-placement result, not a confirmed UAT receiver failure.
