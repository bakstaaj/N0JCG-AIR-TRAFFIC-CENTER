#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys

APP_JS = Path('web/app.js')
JS_START = '// MAP_POPOUT_KIOSK_DEFAULTS_V2_START'
JS_END = '// MAP_POPOUT_KIOSK_DEFAULTS_V2_END'

def remove_block(text: str) -> tuple[str, bool]:
    if JS_START not in text:
        return text, False
    before, rest = text.split(JS_START, 1)
    if JS_END not in rest:
        raise RuntimeError(f'Found {JS_START} without {JS_END}')
    _, after = rest.split(JS_END, 1)
    return before.rstrip() + '\n' + after.lstrip('\n'), True

def main() -> int:
    try:
        if not APP_JS.exists():
            raise FileNotFoundError('web/app.js not found; run from repository root')
        text = APP_JS.read_text(encoding='utf-8')
        new_text, changed = remove_block(text)
        if changed:
            APP_JS.write_text(new_text, encoding='utf-8', newline='\n')
            print('PASS: removed map pop-out kiosk defaults V2 block from web/app.js')
        else:
            print('PASS: no map pop-out kiosk defaults V2 block found')
        print('PASS: rollback complete')
        return 0
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
