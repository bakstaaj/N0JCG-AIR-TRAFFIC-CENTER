#!/usr/bin/env python3
"""Apply Phase 1 weather radar overlay as an append-only web UI patch.

This version intentionally does not depend on the exact formatting of the
existing Leaflet/OpenStreetMap initialization block. It appends a small module
that waits for the existing aircraftMap global and then adds radar controls.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
APP_JS = ROOT / "web" / "app.js"
APP_CSS = ROOT / "web" / "app.css"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
JS_MARKER = "RTP_WEATHER_RADAR_PHASE1_V2"
CSS_MARKER = "Phase 1 weather radar map overlay controls V2"

JS_BLOCK = r'''

/* RTP_WEATHER_RADAR_PHASE1_V2: current NEXRAD radar overlay for the aircraft map. */
(() => {
  'use strict';
  if (window.__rtpWeatherRadarPhase1V2Installed) return;
  window.__rtpWeatherRadarPhase1V2Installed = true;

  const ENABLED_KEY = 'rtlAdsbWeatherRadarEnabledV1';
  const OPACITY_KEY = 'rtlAdsbWeatherRadarOpacityV1';
  const REFRESH_MS = 5 * 60 * 1000;
  const MIN_OPACITY = 15;
  const MAX_OPACITY = 85;
  const DEFAULT_OPACITY = 45;
  let radarLayer = null;
  let refreshTimer = null;
  let installedControls = false;

  function getElement(id) {
    try { return document.getElementById(id); } catch (_) { return null; }
  }

  function getMap() {
    try {
      if (typeof aircraftMap !== 'undefined' && aircraftMap) return aircraftMap;
    } catch (_) {}
    return null;
  }

  function currentOpacity() {
    const stored = Number(localStorage.getItem(OPACITY_KEY) || DEFAULT_OPACITY);
    if (!Number.isFinite(stored)) return DEFAULT_OPACITY;
    return Math.max(MIN_OPACITY, Math.min(MAX_OPACITY, Math.round(stored)));
  }

  function setStatus(message, kind) {
    try {
      if (typeof setMessage === 'function') {
        setMessage('mapMessage', message, kind || '');
        return;
      }
    } catch (_) {}
    const node = getElement('mapMessage');
    if (node) node.textContent = message;
  }

  function radarUrl() {
    const bucket = Math.floor(Date.now() / REFRESH_MS);
    return `https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q/{z}/{x}/{y}.png?rtp=${bucket}`;
  }

  function ensureRadarPane(map) {
    if (!map || typeof map.createPane !== 'function') return 'tilePane';
    let pane = null;
    try { pane = map.getPane('weatherRadarPane'); } catch (_) {}
    if (!pane) {
      pane = map.createPane('weatherRadarPane');
      // Above base map tiles, below route/trail overlays and aircraft markers.
      pane.style.zIndex = '300';
      pane.style.pointerEvents = 'none';
    }
    return 'weatherRadarPane';
  }

  function createRadarLayer(map) {
    if (typeof L === 'undefined' || !L.tileLayer) return null;
    return L.tileLayer(radarUrl(), {
      pane: ensureRadarPane(map),
      opacity: currentOpacity() / 100,
      maxZoom: 19,
      crossOrigin: true,
      attribution: 'Radar: Iowa State IEM / NEXRAD'
    });
  }

  function updateControls(enabled) {
    const opacity = currentOpacity();
    const toggle = getElement('weatherRadarToggle');
    const slider = getElement('weatherRadarOpacity');
    const value = getElement('weatherRadarOpacityValue');
    if (toggle) toggle.checked = Boolean(enabled);
    if (slider) slider.value = String(opacity);
    if (value) value.textContent = `${opacity}%`;
  }

  function refreshRadar() {
    if (!radarLayer) return;
    try { radarLayer.setUrl(radarUrl()); } catch (_) {}
    try { radarLayer.redraw(); } catch (_) {}
  }

  function stopRefreshTimer() {
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  function startRefreshTimer() {
    stopRefreshTimer();
    refreshTimer = window.setInterval(refreshRadar, REFRESH_MS);
  }

  function enableRadar(enabled, announce) {
    const map = getMap();
    if (!map || typeof L === 'undefined') return false;
    const active = Boolean(enabled);
    localStorage.setItem(ENABLED_KEY, active ? '1' : '0');

    if (active) {
      if (!radarLayer) radarLayer = createRadarLayer(map);
      if (!radarLayer) return false;
      try {
        if (!map.hasLayer(radarLayer)) radarLayer.addTo(map);
      } catch (_) {
        try { radarLayer.addTo(map); } catch (_e) { return false; }
      }
      try { radarLayer.setOpacity(currentOpacity() / 100); } catch (_) {}
      refreshRadar();
      startRefreshTimer();
      if (announce) setStatus('Weather radar overlay enabled.', 'good');
    } else {
      stopRefreshTimer();
      try {
        if (radarLayer && map.hasLayer(radarLayer)) map.removeLayer(radarLayer);
      } catch (_) {}
      if (announce) setStatus('Weather radar overlay disabled.', '');
    }

    updateControls(active);
    return true;
  }

  function setOpacity(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return;
    const opacity = Math.max(MIN_OPACITY, Math.min(MAX_OPACITY, Math.round(parsed)));
    localStorage.setItem(OPACITY_KEY, String(opacity));
    if (radarLayer) {
      try { radarLayer.setOpacity(opacity / 100); } catch (_) {}
    }
    updateControls(localStorage.getItem(ENABLED_KEY) === '1');
  }

  function installControls() {
    if (installedControls || getElement('weatherRadarControls')) return true;
    const map = getMap();
    const toolbar = document.querySelector('.map-toolbar');
    if (!map || !toolbar) return false;

    const controls = document.createElement('div');
    controls.id = 'weatherRadarControls';
    controls.className = 'map-weather-controls';
    controls.innerHTML = [
      '<label class="map-weather-toggle" title="Overlay current NEXRAD base reflectivity radar">',
      '<input id="weatherRadarToggle" type="checkbox"> Radar',
      '</label>',
      '<label class="map-weather-opacity" title="Weather radar overlay opacity">',
      '<span>Opacity</span>',
      `<input id="weatherRadarOpacity" type="range" min="${MIN_OPACITY}" max="${MAX_OPACITY}" step="5" value="${currentOpacity()}">`,
      `<span id="weatherRadarOpacityValue">${currentOpacity()}%</span>`,
      '</label>',
      '<button id="weatherRadarRefresh" type="button" title="Refresh radar tiles now">Refresh Radar</button>'
    ].join('');

    const message = getElement('mapMessage');
    if (message && message.parentElement === toolbar) toolbar.insertBefore(controls, message);
    else toolbar.appendChild(controls);

    const toggle = getElement('weatherRadarToggle');
    const slider = getElement('weatherRadarOpacity');
    const refresh = getElement('weatherRadarRefresh');

    if (toggle) toggle.addEventListener('change', () => enableRadar(toggle.checked, true));
    if (slider) slider.addEventListener('input', () => setOpacity(slider.value));
    if (refresh) refresh.addEventListener('click', () => {
      refreshRadar();
      setStatus('Weather radar overlay refreshed.', 'good');
    });

    installedControls = true;
    updateControls(localStorage.getItem(ENABLED_KEY) === '1');
    if (localStorage.getItem(ENABLED_KEY) === '1') enableRadar(true, false);
    return true;
  }

  function boot() {
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      if (installControls() || attempts >= 80) window.clearInterval(timer);
    }, 250);
    installControls();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
'''

CSS_BLOCK = r'''

/* Phase 1 weather radar map overlay controls V2 */
.map-weather-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
  padding: 3px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: rgba(8, 16, 29, .82);
}
.map-weather-controls label { margin: 0; }
.map-weather-toggle { font-weight: 600; }
.map-weather-toggle input {
  width: auto;
  margin: 0 4px 0 0;
  vertical-align: middle;
}
.map-weather-opacity {
  display: flex !important;
  align-items: center;
  gap: 5px !important;
  white-space: nowrap;
}
.map-weather-opacity input[type="range"] {
  width: 86px;
  margin: 0;
  padding: 0;
}
#weatherRadarOpacityValue {
  min-width: 34px;
  color: var(--muted);
  font-size: 10px;
  text-align: right;
}
#weatherRadarRefresh {
  padding: 4px 7px;
  min-height: 24px;
  font-size: 10px;
}
'''


def backup(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"ERROR: Missing required file: {path}")
    target = path.with_name(f"{path.name}.bak_weather_radar_phase1_v2_{STAMP}")
    shutil.copy2(path, target)
    print(f"Backup: {target}")


def append_once(path: Path, marker: str, block: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"Already patched: {path}")
        return False
    path.write_text(text.rstrip() + block + "\n", encoding="utf-8", newline="\n")
    print(f"Patched: {path}")
    return True


def main() -> None:
    backup(APP_JS)
    backup(APP_CSS)
    append_once(APP_JS, JS_MARKER, JS_BLOCK)
    append_once(APP_CSS, CSS_MARKER, CSS_BLOCK)
    print("Applied weather radar Phase 1 V2 append-only patch.")


if __name__ == "__main__":
    main()
