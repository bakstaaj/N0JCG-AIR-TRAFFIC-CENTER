#!/usr/bin/env python3
"""
Apply Map Pop-out / Full Screen View V1 for RTL-Windows-ADS-B-Tracker.

Frontend-only patch:
- Injects a Pop Out Map button into the existing map toolbar.
- Opens a dedicated map-only browser window using the normal app/API runtime.
- In pop-out mode, hides header/menu/aircraft table and expands the map to the full browser window.
- Adds a Full Screen button using the browser Fullscreen API.

This patch intentionally does not modify backend/service code.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
import sys

APP_JS = Path("web/app.js")
APP_CSS = Path("web/app.css")

JS_START = "// MAP_POPOUT_FULLSCREEN_V1_START"
JS_END = "// MAP_POPOUT_FULLSCREEN_V1_END"
CSS_START = "/* MAP_POPOUT_FULLSCREEN_V1_START */"
CSS_END = "/* MAP_POPOUT_FULLSCREEN_V1_END */"

JS_BLOCK = r'''
// MAP_POPOUT_FULLSCREEN_V1_START
// Frontend-only aircraft map pop-out/fullscreen support.
(function(){
  'use strict';
  if (window.__rtlAdsbMapPopoutV1Installed) return;
  window.__rtlAdsbMapPopoutV1Installed = true;

  const POPOUT_PARAM = 'map_popout';
  const POPOUT_BUTTON_ID = 'popOutAircraftMap';
  const FULLSCREEN_BUTTON_ID = 'aircraftMapBrowserFullscreen';

  function isMapPopoutWindow() {
    try {
      return new URLSearchParams(window.location.search).get(POPOUT_PARAM) === '1';
    } catch (_) {
      return false;
    }
  }

  function mapToolbar() {
    return document.querySelector('.map-toolbar');
  }

  function invalidateAircraftMapSoon() {
    const delays = [0, 100, 300, 750, 1500];
    for (const delay of delays) {
      window.setTimeout(() => {
        try {
          if (typeof aircraftMap !== 'undefined' && aircraftMap && typeof aircraftMap.invalidateSize === 'function') {
            aircraftMap.invalidateSize(true);
          }
        } catch (_) {}
      }, delay);
    }
  }

  function openMapPopout() {
    let url;
    try {
      url = new URL(window.location.href);
      url.searchParams.set(POPOUT_PARAM, '1');
    } catch (_) {
      url = {href: `${window.location.pathname}?${POPOUT_PARAM}=1`};
    }

    const width = Math.max(1000, Math.floor((window.screen && window.screen.availWidth) || 1400));
    const height = Math.max(700, Math.floor((window.screen && window.screen.availHeight) || 900));
    const features = [
      'popup=yes',
      'noopener=no',
      'noreferrer=no',
      'menubar=no',
      'toolbar=no',
      'location=no',
      'status=no',
      'scrollbars=no',
      'resizable=yes',
      'left=0',
      'top=0',
      `width=${width}`,
      `height=${height}`
    ].join(',');

    const child = window.open(url.href, 'RTL_ADSB_TRACKER_MAP_POPOUT', features);
    if (child) {
      try { child.focus(); } catch (_) {}
      return;
    }

    try {
      window.location.href = url.href;
    } catch (_) {
      window.location.search = `${POPOUT_PARAM}=1`;
    }
  }

  function closeMapPopout() {
    try {
      if (window.opener && !window.opener.closed) {
        window.close();
        return;
      }
    } catch (_) {}

    try {
      const url = new URL(window.location.href);
      url.searchParams.delete(POPOUT_PARAM);
      window.location.href = url.href;
    } catch (_) {
      window.location.search = '';
    }
  }

  async function toggleBrowserFullscreen() {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (_) {}
    updateFullscreenButtonLabel();
    invalidateAircraftMapSoon();
  }

  function updateFullscreenButtonLabel() {
    const button = document.getElementById(FULLSCREEN_BUTTON_ID);
    if (!button) return;
    button.textContent = document.fullscreenElement ? 'Exit Full Screen' : 'Full Screen';
  }

  function ensureToolbarButtons() {
    const toolbar = mapToolbar();
    if (!toolbar) return false;

    let popoutButton = document.getElementById(POPOUT_BUTTON_ID);
    if (!popoutButton) {
      popoutButton = document.createElement('button');
      popoutButton.id = POPOUT_BUTTON_ID;
      popoutButton.type = 'button';
      popoutButton.className = 'map-popout-control';
      toolbar.insertBefore(popoutButton, toolbar.firstChild || null);
    }
    popoutButton.textContent = isMapPopoutWindow() ? 'Close Map Popout' : 'Pop Out Map';
    popoutButton.onclick = isMapPopoutWindow() ? closeMapPopout : openMapPopout;

    let fullscreenButton = document.getElementById(FULLSCREEN_BUTTON_ID);
    if (!fullscreenButton) {
      fullscreenButton = document.createElement('button');
      fullscreenButton.id = FULLSCREEN_BUTTON_ID;
      fullscreenButton.type = 'button';
      fullscreenButton.className = 'map-popout-control';
      fullscreenButton.addEventListener('click', toggleBrowserFullscreen);
      popoutButton.insertAdjacentElement('afterend', fullscreenButton);
    }
    updateFullscreenButtonLabel();
    return true;
  }

  function applyMapPopoutMode() {
    if (!isMapPopoutWindow()) return;
    document.body.classList.add('map-popout-window');
    try { document.title = 'RTL ADS-B Tracker — Map'; } catch (_) {}
    invalidateAircraftMapSoon();
  }

  function installMapPopoutUi() {
    ensureToolbarButtons();
    applyMapPopoutMode();
    invalidateAircraftMapSoon();
  }

  function waitForToolbarAndInstall() {
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      const ok = ensureToolbarButtons();
      applyMapPopoutMode();
      if (ok || attempts >= 80) {
        window.clearInterval(timer);
        invalidateAircraftMapSoon();
      }
    }, 250);
  }

  try { document.addEventListener('fullscreenchange', updateFullscreenButtonLabel); } catch (_) {}
  try { window.addEventListener('resize', invalidateAircraftMapSoon); } catch (_) {}

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      installMapPopoutUi();
      waitForToolbarAndInstall();
    });
  } else {
    installMapPopoutUi();
    waitForToolbarAndInstall();
  }
})();
// MAP_POPOUT_FULLSCREEN_V1_END
'''.strip() + "\n"

CSS_BLOCK = r'''
/* MAP_POPOUT_FULLSCREEN_V1_START */
.map-popout-control {
  white-space: nowrap;
}
body.map-popout-window {
  overflow: hidden !important;
}
body.map-popout-window .app-header,
body.map-popout-window .menu-backdrop,
body.map-popout-window .menu-drawer,
body.map-popout-window .active-panel {
  display: none !important;
}
body.map-popout-window main.focus-layout {
  display: block !important;
  width: 100vw !important;
  height: 100vh !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden !important;
}
body.map-popout-window .map-panel {
  display: flex !important;
  flex-direction: column !important;
  width: 100vw !important;
  height: 100vh !important;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
  border-radius: 0 !important;
  overflow: hidden !important;
}
body.map-popout-window .map-toolbar,
body.map-popout-window .map-footer {
  flex: 0 0 auto !important;
}
body.map-popout-window #aircraftMap {
  flex: 1 1 auto !important;
  width: 100vw !important;
  min-height: 0 !important;
  height: auto !important;
}
body.map-popout-window .leaflet-container {
  background: #101820;
}
/* MAP_POPOUT_FULLSCREEN_V1_END */
'''.strip() + "\n"


def remove_block(text: str, start: str, end: str) -> str:
    if start not in text:
        return text
    before, rest = text.split(start, 1)
    if end not in rest:
        raise RuntimeError(f"Found {start} without {end}; refusing to patch")
    _, after = rest.split(end, 1)
    return before.rstrip() + "\n" + after.lstrip("\n")


def backup(path: Path) -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak_map_popout_fullscreen_v1_{stamp}")
    backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"PASS: backed up {path} -> {backup_path}")


def patch_file(path: Path, block: str, start: str, end: str, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    original = path.read_text(encoding="utf-8")
    backup(path)
    cleaned = remove_block(original, start, end)
    patched = cleaned.rstrip() + "\n\n" + block
    path.write_text(patched, encoding="utf-8", newline="\n")
    print(f"PASS: applied {label} patch to {path}")


def main() -> int:
    try:
      patch_file(APP_JS, JS_BLOCK, JS_START, JS_END, "map pop-out JavaScript")
      patch_file(APP_CSS, CSS_BLOCK, CSS_START, CSS_END, "map pop-out CSS")
      print("PASS: Applied map pop-out/fullscreen V1")
      return 0
    except Exception as exc:
      print(f"FAIL: {exc}", file=sys.stderr)
      return 1

if __name__ == "__main__":
    raise SystemExit(main())
