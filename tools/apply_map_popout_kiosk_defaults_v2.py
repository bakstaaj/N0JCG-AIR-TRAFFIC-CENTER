#!/usr/bin/env python3
"""
Apply Map Pop-out Kiosk Defaults V2 for RTL-Windows-ADS-B-Tracker.

Frontend-only patch layered on top of Map Pop-out / Full Screen V1:
- In ?map_popout=1 mode, default the map view to receiver-centered 100-mile radius.
- Disable the normal one-time aircraft fit in pop-out mode unless a URL switch enables plane auto-fit.
- Add URL switches for kiosk startup without changing the visible UI.

Supported URL switches:
  ?map_popout=1
      Default: receiver-centered 100-mile radius.
  ?map_popout=1&map_fit=planes
      Continuously auto-fit active planes/receiver as aircraft updates arrive.
  ?map_popout=1&fit=planes
      Alias for map_fit=planes.
  ?map_popout=1&autofit=planes
      Alias for map_fit=planes.
  ?map_popout=1&map_radius_miles=150
      Receiver-centered radius override.
  ?map_popout=1&radius_miles=150
      Alias for map_radius_miles.
  ?map_popout=1&radius=150
      Alias for map_radius_miles.

This patch intentionally does not modify backend/service code.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
import sys

APP_JS = Path("web/app.js")
JS_START = "// MAP_POPOUT_KIOSK_DEFAULTS_V2_START"
JS_END = "// MAP_POPOUT_KIOSK_DEFAULTS_V2_END"

JS_BLOCK = r'''
// MAP_POPOUT_KIOSK_DEFAULTS_V2_START
// Kiosk URL defaults for the map-only pop-out window.
(function(){
  'use strict';
  if (window.__rtlAdsbMapPopoutKioskDefaultsV2Installed) return;
  window.__rtlAdsbMapPopoutKioskDefaultsV2Installed = true;

  const POPOUT_PARAM = 'map_popout';
  const DEFAULT_RECEIVER_RADIUS_MILES = 100;
  const PLANE_AUTOFIT_MIN_INTERVAL_MS = 6000;

  let originalUpdateAircraftMap = null;
  let updateAircraftMapWrapped = false;
  let receiverRadiusFitApplied = false;
  let lastReceiverSignature = '';
  let lastPlaneAutoFitAt = 0;

  function urlParams() {
    try { return new URLSearchParams(window.location.search || ''); }
    catch (_) { return new URLSearchParams(''); }
  }

  function isMapPopoutWindow() {
    const params = urlParams();
    return params.get(POPOUT_PARAM) === '1';
  }

  function normalizedParamValue(name) {
    const value = urlParams().get(name);
    return String(value == null ? '' : value).trim().toLowerCase();
  }

  function configuredFitMode() {
    const candidates = [
      normalizedParamValue('map_fit'),
      normalizedParamValue('fit'),
      normalizedParamValue('autofit'),
      normalizedParamValue('auto_fit'),
      normalizedParamValue('map_autofit')
    ].filter(Boolean);

    for (const value of candidates) {
      if (['planes', 'aircraft', 'active', '1', 'true', 'yes', 'on'].includes(value)) return 'planes';
      if (['receiver', 'home', 'center', '0', 'false', 'no', 'off'].includes(value)) return 'receiver';
    }

    // Kiosk default for pop-out: receiver-centered 100-mile view.
    return 'receiver';
  }

  function configuredRadiusMiles() {
    const params = urlParams();
    const raw = params.get('map_radius_miles') || params.get('radius_miles') || params.get('radius') || '';
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed >= 5 && parsed <= 500) return parsed;
    return DEFAULT_RECEIVER_RADIUS_MILES;
  }

  function currentReceiverLocation() {
    try {
      if (typeof receiverMapLocation !== 'undefined' && Array.isArray(receiverMapLocation)) {
        const lat = Number(receiverMapLocation[0]);
        const lon = Number(receiverMapLocation[1]);
        if (Number.isFinite(lat) && Number.isFinite(lon)) return [lat, lon];
      }
    } catch (_) {}

    try {
      const latNode = document.getElementById('locationLatitude');
      const lonNode = document.getElementById('locationLongitude');
      const lat = Number(latNode && latNode.value);
      const lon = Number(lonNode && lonNode.value);
      if (Number.isFinite(lat) && Number.isFinite(lon)) return [lat, lon];
    } catch (_) {}

    return null;
  }

  function mapReady() {
    try {
      return typeof aircraftMap !== 'undefined' && aircraftMap && typeof aircraftMap.fitBounds === 'function';
    } catch (_) {
      return false;
    }
  }

  function invalidateAircraftMapSoon() {
    const delays = [0, 100, 300, 750, 1500];
    for (const delay of delays) {
      window.setTimeout(() => {
        try {
          if (mapReady() && typeof aircraftMap.invalidateSize === 'function') aircraftMap.invalidateSize(true);
        } catch (_) {}
      }, delay);
    }
  }

  function receiverRadiusBounds(center, radiusMiles) {
    const lat = Number(center[0]);
    const lon = Number(center[1]);
    const milesPerDegreeLat = 69.0;
    const cosLat = Math.max(0.12, Math.cos(lat * Math.PI / 180));
    const latDelta = radiusMiles / milesPerDegreeLat;
    const lonDelta = radiusMiles / (milesPerDegreeLat * cosLat);
    return [[lat - latDelta, lon - lonDelta], [lat + latDelta, lon + lonDelta]];
  }

  function fitReceiverRadius(force) {
    if (!isMapPopoutWindow() || configuredFitMode() !== 'receiver') return false;
    if (!mapReady()) return false;

    const center = currentReceiverLocation();
    if (!center) return false;

    const radius = configuredRadiusMiles();
    const signature = `${center[0].toFixed(6)},${center[1].toFixed(6)},${radius}`;
    if (!force && receiverRadiusFitApplied && signature === lastReceiverSignature) return true;

    try {
      // Disable the original app's first-aircraft fit in pop-out receiver mode.
      if (typeof aircraftMapFirstFit !== 'undefined') aircraftMapFirstFit = false;
    } catch (_) {}

    try {
      aircraftMap.fitBounds(receiverRadiusBounds(center, radius), {
        padding: [20, 20],
        animate: false
      });
      receiverRadiusFitApplied = true;
      lastReceiverSignature = signature;
      invalidateAircraftMapSoon();
      return true;
    } catch (_) {
      return false;
    }
  }

  function activeMarkerLatLngs() {
    const points = [];
    try {
      if (typeof aircraftMapMarkers !== 'undefined' && aircraftMapMarkers && typeof aircraftMapMarkers.values === 'function') {
        for (const marker of aircraftMapMarkers.values()) {
          try {
            const latlng = marker && typeof marker.getLatLng === 'function' ? marker.getLatLng() : null;
            if (latlng && Number.isFinite(Number(latlng.lat)) && Number.isFinite(Number(latlng.lng))) points.push(latlng);
          } catch (_) {}
        }
      }
    } catch (_) {}
    return points;
  }

  function fitActivePlanes(force) {
    if (!isMapPopoutWindow() || configuredFitMode() !== 'planes') return false;
    if (!mapReady()) return false;

    const now = Date.now();
    if (!force && now - lastPlaneAutoFitAt < PLANE_AUTOFIT_MIN_INTERVAL_MS) return true;

    const points = activeMarkerLatLngs();
    const receiver = currentReceiverLocation();
    if (receiver) {
      try { points.push(L.latLng(receiver[0], receiver[1])); } catch (_) { points.push(receiver); }
    }

    if (!points.length) {
      // No active aircraft yet: keep the kiosk on the default receiver radius view.
      return fitReceiverRadius(true);
    }

    try {
      if (typeof aircraftMapFirstFit !== 'undefined') aircraftMapFirstFit = false;
    } catch (_) {}

    try {
      if (points.length === 1) {
        const only = points[0];
        aircraftMap.setView(only, Math.min(10, Number(aircraftMap.getZoom && aircraftMap.getZoom()) || 10), {animate: false});
      } else {
        aircraftMap.fitBounds(points, {padding: [35, 35], maxZoom: 12, animate: false});
      }
      lastPlaneAutoFitAt = now;
      invalidateAircraftMapSoon();
      return true;
    } catch (_) {
      return false;
    }
  }

  function applyConfiguredKioskView(force) {
    if (!isMapPopoutWindow()) return;

    try {
      document.body.classList.add('map-popout-kiosk-defaults-v2');
      document.body.dataset.mapPopoutFit = configuredFitMode();
      document.body.dataset.mapPopoutRadiusMiles = String(configuredRadiusMiles());
    } catch (_) {}

    if (configuredFitMode() === 'planes') fitActivePlanes(force);
    else fitReceiverRadius(force);
  }

  function wrapUpdateAircraftMapForKioskFit() {
    if (!isMapPopoutWindow() || updateAircraftMapWrapped) return;
    try {
      if (typeof updateAircraftMap !== 'function') return;
      originalUpdateAircraftMap = updateAircraftMap;
      updateAircraftMap = function(records) {
        const result = originalUpdateAircraftMap.apply(this, arguments);
        window.setTimeout(() => applyConfiguredKioskView(false), 0);
        window.setTimeout(() => applyConfiguredKioskView(false), 350);
        return result;
      };
      updateAircraftMapWrapped = true;
    } catch (_) {}
  }

  function installKioskDefaults() {
    if (!isMapPopoutWindow()) return;

    try {
      if (configuredFitMode() === 'receiver' && typeof aircraftMapFirstFit !== 'undefined') {
        aircraftMapFirstFit = false;
      }
    } catch (_) {}

    wrapUpdateAircraftMapForKioskFit();
    applyConfiguredKioskView(true);
    invalidateAircraftMapSoon();
  }

  function waitAndInstall() {
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      installKioskDefaults();
      if ((mapReady() && currentReceiverLocation()) || attempts >= 120) {
        if (attempts >= 120 || receiverRadiusFitApplied || configuredFitMode() === 'planes') {
          window.clearInterval(timer);
        }
      }
    }, 250);
  }

  try { window.addEventListener('resize', () => applyConfiguredKioskView(true)); } catch (_) {}
  try { document.addEventListener('fullscreenchange', () => applyConfiguredKioskView(true)); } catch (_) {}

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      installKioskDefaults();
      waitAndInstall();
    });
  } else {
    installKioskDefaults();
    waitAndInstall();
  }
})();
// MAP_POPOUT_KIOSK_DEFAULTS_V2_END
'''.strip() + "\n"


def remove_existing_block(text: str) -> str:
    if JS_START not in text:
        return text
    before, rest = text.split(JS_START, 1)
    if JS_END not in rest:
        raise RuntimeError(f"Found {JS_START} without {JS_END}")
    _, after = rest.split(JS_END, 1)
    return before.rstrip() + "\n" + after.lstrip("\n")


def main() -> int:
    try:
        if not APP_JS.exists():
            raise FileNotFoundError("web/app.js not found; run from repository root")

        js = APP_JS.read_text(encoding="utf-8")
        if "MAP_POPOUT_FULLSCREEN_V1_START" not in js:
            print("WARNING: MAP_POPOUT_FULLSCREEN_V1_START not found. V2 can still apply, but install/apply the pop-out V1 patch first if the Pop Out Map button is missing.")

        cleaned = remove_existing_block(js)
        backup = APP_JS.with_suffix(APP_JS.suffix + f".bak_map_popout_kiosk_defaults_v2_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        backup.write_text(js, encoding="utf-8", newline="\n")
        APP_JS.write_text(cleaned.rstrip() + "\n\n" + JS_BLOCK, encoding="utf-8", newline="\n")

        print(f"PASS: Applied map pop-out kiosk defaults V2 to {APP_JS}")
        print(f"PASS: Backup written to {backup}")
        print("PASS: Pop-out default is now receiver-centered 100-mile radius")
        print("PASS: Plane auto-fit can be enabled with ?map_popout=1&map_fit=planes")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
