# Repository structure and contribution workflow

N0JCG Air Traffic Center is maintained as a standalone product repository. The repository is the source of truth for the application; ROC deployments are test hosts and must not become a second source tree.

## Layout

| Path | Responsibility |
| --- | --- |
| `web/` | Browser application assets and the operator interface. |
| `src/backend/` | Pi-native API and receiver orchestration. |
| `src/native/` | Small native helpers used by the Pi runtime. |
| `deploy/` | systemd units and deployment-time service configuration. |
| `runtime/settings/` | Checked-in templates and stable receiver-role mappings only. |
| `docs/` | Product guide, release notes, validation evidence, and guardrails. |
| `tools/` | Reusable installation, validation, packaging, and operational tools. |

Generated reports, runtime logs, captures, local patch backups, and temporary checkpoint directories are not repository content and are ignored by `.gitignore`.

## Product and brand rules

- Use the complete product name **N0JCG Air Traffic Center** in formal documentation and release material.
- Use `N0JCG` with the numeral zero; do not substitute the letter O.
- Preserve the approved N0JCG palette and icon assets in the browser application.
- Keep the ROC test deployment namespaced and separate from this source repository.
- Preserve compatibility identifiers unless a separate migration explicitly changes them.

## Change workflow

1. Make a focused change in the standalone repository.
2. Run source validation locally.
3. Run hardware-dependent checks on the Raspberry Pi when receiver behavior is affected.
4. Review `git diff` and stage only intended files.
5. Deploy the scoped web/runtime assets to a test host only after validation.
6. Compare served assets with the repository copy and record the relevant smoke result.

Do not commit API keys, receiver runtime indexes, generated aircraft data, audio captures, logs, or local deployment credentials. Resolve receiver roles by EEPROM serial: NOAA/Airband `00000162`, ADS-B 1090 `00001090`, and UAT 978 `00000978`.
