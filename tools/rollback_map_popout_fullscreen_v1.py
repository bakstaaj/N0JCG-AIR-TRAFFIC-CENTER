#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys

TARGETS = [
    (Path('web/app.js'), '// MAP_POPOUT_FULLSCREEN_V1_START', '// MAP_POPOUT_FULLSCREEN_V1_END'),
    (Path('web/app.css'), '/* MAP_POPOUT_FULLSCREEN_V1_START */', '/* MAP_POPOUT_FULLSCREEN_V1_END */'),
]

def remove_block(text: str, start: str, end: str) -> tuple[str, bool]:
    if start not in text:
        return text, False
    before, rest = text.split(start, 1)
    if end not in rest:
        raise RuntimeError(f"Found {start} without {end}")
    _, after = rest.split(end, 1)
    return before.rstrip() + "\n" + after.lstrip("\n"), True

def main() -> int:
    try:
        changed = False
        for path, start, end in TARGETS:
            if not path.exists():
                print(f"PASS: {path} not present; skipped")
                continue
            text = path.read_text(encoding='utf-8')
            new_text, did = remove_block(text, start, end)
            if did:
                path.write_text(new_text, encoding='utf-8', newline='\n')
                print(f"PASS: removed map pop-out V1 block from {path}")
                changed = True
            else:
                print(f"PASS: no map pop-out V1 block found in {path}")
        print('PASS: rollback complete' if changed else 'PASS: nothing to rollback')
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
