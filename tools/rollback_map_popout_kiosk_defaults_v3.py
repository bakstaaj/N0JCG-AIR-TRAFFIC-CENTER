#!/usr/bin/env python3
"""Remove Map Pop-out Kiosk Defaults V2/V3 appended blocks from web/app.js."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
import sys

APP_JS = Path('web/app.js')
BLOCKS = [
    ('// MAP_POPOUT_KIOSK_DEFAULTS_V3_START', '// MAP_POPOUT_KIOSK_DEFAULTS_V3_END'),
    ('// MAP_POPOUT_KIOSK_DEFAULTS_V2_START', '// MAP_POPOUT_KIOSK_DEFAULTS_V2_END'),
]


def remove_block(text: str, start: str, end: str) -> tuple[str, bool]:
    if start not in text:
        return text, False
    before, rest = text.split(start, 1)
    if end not in rest:
        raise RuntimeError(f'Found {start} without {end}')
    _, after = rest.split(end, 1)
    return before.rstrip() + '\n' + after.lstrip('\n'), True


def main() -> int:
    try:
        if not APP_JS.exists():
            raise FileNotFoundError('web/app.js not found; run from repository root')
        original = APP_JS.read_text(encoding='utf-8')
        text = original
        removed = []
        for start, end in BLOCKS:
            text, did_remove = remove_block(text, start, end)
            if did_remove:
                removed.append(start)
        if not removed:
            print('PASS: No map pop-out kiosk defaults V2/V3 block found; nothing to roll back')
            return 0
        backup = APP_JS.with_suffix(APP_JS.suffix + f'.bak_before_rollback_map_popout_kiosk_defaults_v3_{_dt.datetime.now().strftime("%Y%m%d_%H%M%S")}')
        backup.write_text(original, encoding='utf-8', newline='\n')
        APP_JS.write_text(text.rstrip() + '\n', encoding='utf-8', newline='\n')
        print(f'PASS: Removed {len(removed)} map pop-out kiosk defaults block(s) from {APP_JS}')
        print(f'PASS: Backup written to {backup}')
        return 0
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
