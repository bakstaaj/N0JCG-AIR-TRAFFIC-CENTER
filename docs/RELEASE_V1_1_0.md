# N0JCG Air Traffic Center v1.1.0

**Release type:** Successor production release  
**Repository:** `bakstaaj/N0JCG-AIR-TRAFFIC-CENTER`

## Included changes

- Backend-enforced five-minute unregistered trial for aircraft tracking, NOAA, Airband, and shared audio.
- Registration activation through the local backend with signed lease verification.
- Canonical Air Traffic Center licensing Worker URL, product slug, application User-Agent, and regression tests.
- Manual trial restart control for unregistered installations; the control hides after registration.
- Aircraft list, map markers, and displayed trails clear when the trial expires.
- Air Traffic Center remains available as a web UI/API when RTL-SDR hardware is temporarily disconnected.
- Branded user guide and current N0JCG Air Traffic Center interface assets.

## Validation

- Python licensing regression tests pass.
- Python backend compilation passes.
- JavaScript syntax validation passes.
- Current source is merged to `main` before the `v1.1.0` tag is created.
- Deployment archives are generated from the tagged source tree and accompanied by SHA-256 checksums.
