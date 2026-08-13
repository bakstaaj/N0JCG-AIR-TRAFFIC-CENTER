# N0JCG Air Traffic Center v1.1.2

**Release type:** First-deployment installer release
**Repository:** `bakstaaj/N0JCG-AIR-TRAFFIC-CENTER`

## Included changes

- Guided workstation-to-Pi first-deployment installer.
- Reusable protected `.env` connection settings for Pi IP, SSH user, and password.
- Deployment into `/home/<pi-user>/n0jcg-air-traffic-center`.
- OS dependency, app-owned RTL-compatible decoder, and systemd service installation.
- One-at-a-time automatic RTL serial assignment with EEPROM backups and post-write verification.
- Pre-service serial-role, decoder, systemd, UI, and API validation.
- Branded v1.1.1 end-user guide with the new-Pi setup section and website publication assets.

## Validation

- Bash syntax validation passed for both first-deployment scripts.
- Release archive verified to contain the new installer and all required deployment scripts.
- Python licensing regression tests, backend compilation, and JavaScript syntax validation remain passing.
- Archive is generated from the tagged source tree and accompanied by SHA-256 checksums.
