# Contributing to N0JCG Air Traffic Center

Keep changes focused on the standalone Air Traffic Center repository. Match the N0JCG Open Radio Platform brand and design system, preserve existing operator workflows, and name state clearly when hardware confirmation is unavailable.

Before opening a change:

```bash
node --check web/app.js
python3 -m py_compile src/backend/pi_air_traffic_backend.py
find tools deploy -type f -name '*.sh' -print0 | xargs -0 -r -n1 bash -n
```

For UI changes, also check the desktop map-first view and a short-height viewport. For receiver or audio changes, run the relevant Pi validation script and report whether the result is simulated, local, or hardware-observed.

Do not commit generated reports, patch backups, runtime settings, secrets, audio captures, or claims of live hardware validation without evidence. ROC deployment is a test step; the standalone repository remains authoritative.
