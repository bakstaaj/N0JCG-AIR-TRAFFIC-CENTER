#!/usr/bin/env python3
"""
Apply active aircraft/trail display cleanup V2 for RTL-Windows-ADS-B-Tracker.

V2 intentionally uses an append-only runtime wrapper instead of brittle source
rewrites. It filters stale readsb aircraft records from /api/aircraft.json before
existing UI rendering sees them. Existing map cleanup code then removes inactive
markers and active trail display layers. Browser/server trail history is not
cleared, so Restore History remains available.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

PATCH_ID = "active-trail-cleanup-v2"
APP_JS = Path("web/app.js")
START = "/* ACTIVE_TRAIL_CLEANUP_V2_START */"
END = "/* ACTIVE_TRAIL_CLEANUP_V2_END */"

PATCH = r'''
/* ACTIVE_TRAIL_CLEANUP_V2_START */
(function(){
  'use strict';

  // Active display cleanup V2:
  // - Hide stale aircraft from the active table and active map display.
  // - Let the existing map cleanup remove stale markers and active trail layers.
  // - Do not clear browser/server trail history; Restore History still works.
  const ACTIVE_TRAIL_CLEANUP_STALE_SECONDS = 60;

  function activeTrailCleanupAircraftAgeSeconds(aircraft, fieldName){
    if(!aircraft || typeof aircraft !== 'object') return null;
    const value = Number(aircraft[fieldName]);
    return Number.isFinite(value) ? value : null;
  }

  function activeTrailCleanupIsAircraftRecordActive(aircraft){
    const seen = activeTrailCleanupAircraftAgeSeconds(aircraft, 'seen');
    return seen == null || seen <= ACTIVE_TRAIL_CLEANUP_STALE_SECONDS;
  }

  function activeTrailCleanupIsAircraftMapPositionActive(aircraft){
    const seenPosition = activeTrailCleanupAircraftAgeSeconds(aircraft, 'seen_pos');
    if(seenPosition != null) return seenPosition <= ACTIVE_TRAIL_CLEANUP_STALE_SECONDS;
    return activeTrailCleanupIsAircraftRecordActive(aircraft);
  }

  function activeTrailCleanupHasPosition(aircraft){
    return Number.isFinite(Number(aircraft && aircraft.lat)) &&
      Number.isFinite(Number(aircraft && aircraft.lon));
  }

  function activeTrailCleanupDisplayRecordAllowed(aircraft){
    if(!activeTrailCleanupIsAircraftRecordActive(aircraft)) return false;
    if(activeTrailCleanupHasPosition(aircraft)) return activeTrailCleanupIsAircraftMapPositionActive(aircraft);
    return true;
  }

  function activeTrailCleanupFilterAircraftList(records){
    if(!Array.isArray(records)) return records;
    return records.filter(activeTrailCleanupDisplayRecordAllowed);
  }

  function activeTrailCleanupFilterAircraftPayload(payload){
    if(!payload || typeof payload !== 'object' || !Array.isArray(payload.aircraft)) return payload;
    const originalCount = payload.aircraft.length;
    const filteredAircraft = activeTrailCleanupFilterAircraftList(payload.aircraft);
    const filteredCount = originalCount - filteredAircraft.length;
    const copy = Object.assign({}, payload, {
      aircraft: filteredAircraft,
      active_display_aircraft_count: filteredAircraft.length,
      active_display_filtered_stale_count: Math.max(0, filteredCount)
    });
    return copy;
  }

  function activeTrailCleanupWrapGlobalFunction(name, wrapperFactory){
    let original = null;
    try { original = window[name]; } catch(_e) {}
    if(typeof original !== 'function') return false;
    if(original.__activeTrailCleanupV2Wrapped) return true;

    const wrapped = wrapperFactory(original);
    if(typeof wrapped !== 'function') return false;
    wrapped.__activeTrailCleanupV2Wrapped = true;
    wrapped.__activeTrailCleanupV2Original = original;

    try { window[name] = wrapped; } catch(_e) {}
    try {
      // In classic browser scripts, this updates the global function binding as
      // well as window.<name>. eval keeps the assignment generic and isolated.
      (0, eval)(name + ' = window["' + name + '"];');
    } catch(_e) {}
    return true;
  }

  function activeTrailCleanupInstallJsonFilter(){
    return activeTrailCleanupWrapGlobalFunction('jsonRequest', function(original){
      return async function activeTrailCleanupJsonRequest(url, options){
        const payload = await original.call(this, url, options);
        const target = String(url || '');
        if(target.indexOf('/api/aircraft.json') >= 0 || /(^|\/)aircraft\.json(?:\?|$)/.test(target)){
          return activeTrailCleanupFilterAircraftPayload(payload);
        }
        return payload;
      };
    });
  }

  function activeTrailCleanupInstallMapFilter(){
    return activeTrailCleanupWrapGlobalFunction('updateAircraftMap', function(original){
      return function activeTrailCleanupUpdateAircraftMap(aircraftRecords){
        return original.call(this, activeTrailCleanupFilterAircraftList(aircraftRecords));
      };
    });
  }

  function activeTrailCleanupInstall(){
    const jsonWrapped = activeTrailCleanupInstallJsonFilter();
    const mapWrapped = activeTrailCleanupInstallMapFilter();
    window.__activeTrailCleanupV2 = {
      installed: true,
      jsonRequestWrapped: jsonWrapped,
      updateAircraftMapWrapped: mapWrapped,
      staleSeconds: ACTIVE_TRAIL_CLEANUP_STALE_SECONDS,
      installedUtc: new Date().toISOString()
    };
    return jsonWrapped || mapWrapped;
  }

  activeTrailCleanupInstall();
  try { document.addEventListener('DOMContentLoaded', activeTrailCleanupInstall); } catch(_e) {}
  try { setTimeout(activeTrailCleanupInstall, 0); } catch(_e) {}
  try { setTimeout(activeTrailCleanupInstall, 1000); } catch(_e) {}

  try {
    window.activeTrailCleanupV2FilterAircraftPayload = activeTrailCleanupFilterAircraftPayload;
  } catch(_e) {}
})();
/* ACTIVE_TRAIL_CLEANUP_V2_END */
'''.strip() + "\n"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak_{PATCH_ID}_{stamp}")
    shutil.copy2(path, backup)
    return backup


def remove_existing_patch(text: str) -> tuple[str, int]:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\s*", re.DOTALL)
    return pattern.subn("", text)


def main() -> int:
    if not APP_JS.exists():
        fail(f"{APP_JS} not found. Run this from the repository root.")

    original = APP_JS.read_text(encoding="utf-8")
    cleaned, removed = remove_existing_patch(original)

    if START in original and "activeTrailCleanupFilterAircraftPayload" in original and removed == 1:
        print("PASS: active trail cleanup V2 patch is already present; refreshing append block.")
    else:
        print("Applying active trail cleanup V2 append-only patch.")

    backup = backup_file(APP_JS)
    updated = cleaned.rstrip() + "\n\n" + PATCH

    if updated == original:
        print("PASS: no changes needed; active trail cleanup V2 already matches expected content.")
        return 0

    APP_JS.write_text(updated, encoding="utf-8")
    print(f"PASS: patched {APP_JS}")
    print(f"Backup: {backup}")
    print("Next: run ./tools/validate_active_trail_cleanup_v2.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
