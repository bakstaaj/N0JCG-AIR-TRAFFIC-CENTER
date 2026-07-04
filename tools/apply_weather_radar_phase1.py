#!/usr/bin/env python3
"""Apply Phase 1 weather radar overlay UI patch.

Patches only:
  - web/app.js
  - web/app.css

The patch is idempotent and creates timestamped backups next to each file.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "web" / "app.js"
APP_CSS = ROOT / "web" / "app.css"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def backup(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"ERROR: Missing expected file: {path}")
    target = path.with_name(f"{path.name}.bak_weather_radar_phase1_{STAMP}")
    shutil.copy2(path, target)
    print(f"Backup: {target}")


def patch_js() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    backup(APP_JS)

    globals_anchor = """let aircraftMap = null;\nlet receiverMapMarker = null;\nlet receiverRangeRings = null;\nlet receiverMapLocation = null;\nlet aircraftMapMarkers = new Map();\n"""
    globals_replacement = """let aircraftMap = null;\nlet weatherRadarLayer = null;\nlet weatherRadarRefreshTimer = null;\nlet weatherRadarOpacity = Number(localStorage.getItem('rtlAdsbWeatherRadarOpacityV1') || '45');\nif (!Number.isFinite(weatherRadarOpacity) || weatherRadarOpacity < 15 || weatherRadarOpacity > 85) weatherRadarOpacity = 45;\nconst WEATHER_RADAR_ENABLED_KEY = 'rtlAdsbWeatherRadarEnabledV1';\nconst WEATHER_RADAR_OPACITY_KEY = 'rtlAdsbWeatherRadarOpacityV1';\nconst WEATHER_RADAR_REFRESH_MS = 5 * 60 * 1000;\nlet receiverMapMarker = null;\nlet receiverRangeRings = null;\nlet receiverMapLocation = null;\nlet aircraftMapMarkers = new Map();\n"""
    if "WEATHER_RADAR_ENABLED_KEY" not in js:
        if globals_anchor not in js:
            raise SystemExit("ERROR: Could not find aircraft map globals anchor in web/app.js")
        js = js.replace(globals_anchor, globals_replacement)

    functions_anchor = "function initializeAircraftMap() {\n"
    weather_functions = r'''
function weatherRadarTileUrl() {
  // Iowa State IEM current CONUS NEXRAD base reflectivity mosaic.
  // Cache-buster is rounded to the documented 5-minute cache cadence.
  const bucket = Math.floor(Date.now() / WEATHER_RADAR_REFRESH_MS);
  return `https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q/{z}/{x}/{y}.png?rtp=${bucket}`;
}

function ensureWeatherRadarPane() {
  if (!aircraftMap || !aircraftMap.createPane) return;
  if (!aircraftMap.getPane('weatherRadarPane')) {
    const pane = aircraftMap.createPane('weatherRadarPane');
    pane.style.zIndex = '350';
    pane.style.pointerEvents = 'none';
  }
}

function createWeatherRadarLayer() {
  ensureWeatherRadarPane();
  return L.tileLayer(weatherRadarTileUrl(), {
    pane: 'weatherRadarPane',
    opacity: weatherRadarOpacity / 100,
    maxZoom: 19,
    crossOrigin: true,
    attribution: 'Radar: Iowa State IEM / NEXRAD'
  });
}

function refreshWeatherRadarLayer() {
  if (!weatherRadarLayer) return;
  weatherRadarLayer.setUrl(weatherRadarTileUrl());
  try { weatherRadarLayer.redraw(); } catch (_) {}
}

function startWeatherRadarRefreshTimer() {
  stopWeatherRadarRefreshTimer();
  weatherRadarRefreshTimer = window.setInterval(refreshWeatherRadarLayer, WEATHER_RADAR_REFRESH_MS);
}

function stopWeatherRadarRefreshTimer() {
  if (weatherRadarRefreshTimer) {
    window.clearInterval(weatherRadarRefreshTimer);
    weatherRadarRefreshTimer = null;
  }
}

function updateWeatherRadarControls(enabled) {
  const toggle = el('weatherRadarToggle');
  const opacity = el('weatherRadarOpacity');
  const value = el('weatherRadarOpacityValue');
  if (toggle) toggle.checked = Boolean(enabled);
  if (opacity) opacity.value = String(weatherRadarOpacity);
  if (value) value.textContent = `${weatherRadarOpacity}%`;
}

function setWeatherRadarEnabled(enabled, announce = true) {
  if (!aircraftMap || typeof L === 'undefined') return;
  const active = Boolean(enabled);
  localStorage.setItem(WEATHER_RADAR_ENABLED_KEY, active ? '1' : '0');

  if (active) {
    if (!weatherRadarLayer) weatherRadarLayer = createWeatherRadarLayer();
    if (!aircraftMap.hasLayer(weatherRadarLayer)) weatherRadarLayer.addTo(aircraftMap);
    weatherRadarLayer.setOpacity(weatherRadarOpacity / 100);
    refreshWeatherRadarLayer();
    startWeatherRadarRefreshTimer();
    if (announce) setMessage('mapMessage', 'Weather radar overlay enabled. Aircraft markers and trails remain above radar.', 'good');
  } else {
    stopWeatherRadarRefreshTimer();
    if (weatherRadarLayer && aircraftMap.hasLayer(weatherRadarLayer)) aircraftMap.removeLayer(weatherRadarLayer);
    if (announce) setMessage('mapMessage', 'Weather radar overlay disabled.', '');
  }

  updateWeatherRadarControls(active);
}

function setWeatherRadarOpacity(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return;
  weatherRadarOpacity = Math.max(15, Math.min(85, Math.round(parsed)));
  localStorage.setItem(WEATHER_RADAR_OPACITY_KEY, String(weatherRadarOpacity));
  if (weatherRadarLayer) weatherRadarLayer.setOpacity(weatherRadarOpacity / 100);
  updateWeatherRadarControls(localStorage.getItem(WEATHER_RADAR_ENABLED_KEY) === '1');
}

function installWeatherRadarControls() {
  const toolbar = document.querySelector('.map-toolbar');
  if (!toolbar || el('weatherRadarControls')) return;

  const controls = document.createElement('div');
  controls.id = 'weatherRadarControls';
  controls.className = 'map-weather-controls';
  controls.innerHTML = `
    <label class="map-weather-toggle" title="Overlay current NEXRAD base reflectivity radar">
      <input id="weatherRadarToggle" type="checkbox"> Radar
    </label>
    <label class="map-weather-opacity" title="Weather radar overlay opacity">
      <span>Opacity</span>
      <input id="weatherRadarOpacity" type="range" min="15" max="85" step="5" value="${weatherRadarOpacity}">
      <span id="weatherRadarOpacityValue">${weatherRadarOpacity}%</span>
    </label>
    <button id="weatherRadarRefresh" type="button" title="Refresh radar tiles now">Refresh Radar</button>
  `;

  const mapMessage = el('mapMessage');
  if (mapMessage) toolbar.insertBefore(controls, mapMessage);
  else toolbar.appendChild(controls);

  const toggle = el('weatherRadarToggle');
  const opacity = el('weatherRadarOpacity');
  const refresh = el('weatherRadarRefresh');

  if (toggle) toggle.addEventListener('change', () => setWeatherRadarEnabled(toggle.checked));
  if (opacity) opacity.addEventListener('input', () => setWeatherRadarOpacity(opacity.value));
  if (refresh) {
    refresh.addEventListener('click', () => {
      refreshWeatherRadarLayer();
      setMessage('mapMessage', 'Weather radar overlay refreshed.', 'good');
    });
  }

  updateWeatherRadarControls(localStorage.getItem(WEATHER_RADAR_ENABLED_KEY) === '1');
}

function restoreWeatherRadarPreference() {
  installWeatherRadarControls();
  if (localStorage.getItem(WEATHER_RADAR_ENABLED_KEY) === '1') setWeatherRadarEnabled(true, false);
}

'''
    if "function weatherRadarTileUrl()" not in js:
        if functions_anchor not in js:
            raise SystemExit("ERROR: Could not find initializeAircraftMap anchor in web/app.js")
        js = js.replace(functions_anchor, weather_functions + functions_anchor)

    map_anchor = """  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {\n    maxZoom: 19,\n    attribution: '&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors'\n  }).addTo(aircraftMap);\n}\n"""
    map_replacement = """  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {\n    maxZoom: 19,\n    attribution: '&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors'\n  }).addTo(aircraftMap);\n\n  restoreWeatherRadarPreference();\n}\n"""
    if "restoreWeatherRadarPreference();" not in js:
        if map_anchor not in js:
            raise SystemExit("ERROR: Could not find OSM tile layer anchor in web/app.js")
        js = js.replace(map_anchor, map_replacement)

    APP_JS.write_text(js, encoding="utf-8", newline="\n")


def patch_css() -> None:
    css = APP_CSS.read_text(encoding="utf-8")
    backup(APP_CSS)
    css_add = r'''

/* Phase 1 weather radar map overlay controls */
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
.map-weather-toggle input { width: auto; margin: 0 4px 0 0; vertical-align: middle; }
.map-weather-opacity { display: flex !important; align-items: center; gap: 5px !important; white-space: nowrap; }
.map-weather-opacity input[type="range"] { width: 86px; margin: 0; padding: 0; }
#weatherRadarOpacityValue { min-width: 34px; color: var(--muted); font-size: 10px; text-align: right; }
#weatherRadarRefresh { padding: 4px 7px; min-height: 24px; font-size: 10px; }
'''
    if "Phase 1 weather radar map overlay controls" not in css:
        css = css.rstrip() + css_add + "\n"
    APP_CSS.write_text(css, encoding="utf-8", newline="\n")


def main() -> int:
    patch_js()
    patch_css()
    print("Applied Phase 1 weather radar overlay patch to web/app.js and web/app.css")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
