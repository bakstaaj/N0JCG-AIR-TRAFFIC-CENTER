#!/usr/bin/env bash
set -u

fail=0
pass() { printf 'PASS: %s\n' "$1"; }
failmsg() { printf 'FAIL: %s\n' "$1"; fail=1; }

[[ -f web/app.js ]] || failmsg 'web/app.js not found; run from repo root'

if [[ -f web/app.js ]]; then
  if command -v node >/dev/null 2>&1; then
    if node --check web/app.js >/tmp/map_popout_kiosk_defaults_v3_node_check.out 2>&1; then
      pass 'JavaScript syntax check passed'
    else
      cat /tmp/map_popout_kiosk_defaults_v3_node_check.out
      failmsg 'JavaScript syntax check failed'
    fi
  else
    failmsg 'node not found; cannot validate JavaScript syntax'
  fi

  grep -q 'MAP_POPOUT_KIOSK_DEFAULTS_V3_START' web/app.js || failmsg 'missing JavaScript marker MAP_POPOUT_KIOSK_DEFAULTS_V3_START'
  grep -q 'DEFAULT_RECEIVER_RADIUS_MILES = 60' web/app.js || failmsg 'missing 60-mile receiver radius default'
  grep -q 'DEFAULT_RECEIVER_RADIUS_MILES = 100' web/app.js && failmsg 'old 100-mile kiosk default is still present' || true
  grep -q "map_fit" web/app.js || failmsg 'missing map_fit URL switch'
  grep -q "normalizedParamValue('fit')" web/app.js || failmsg 'missing fit=planes alias parser'
  grep -q "normalizedParamValue('autofit')" web/app.js || failmsg 'missing autofit=planes alias parser'
  grep -q "map_radius_miles" web/app.js || failmsg 'missing map_radius_miles URL switch'
  grep -q "radio_radius_miles" web/app.js || failmsg 'missing radio_radius_miles URL switch'
  grep -q "configuredRadioRadiusMiles" web/app.js || failmsg 'missing radio/Airband radius helper'
  grep -q "syncRadioRadiusControl" web/app.js || failmsg 'missing radio/Airband radius sync function'
  grep -q "document.getElementById('locationRadius')" web/app.js || failmsg 'missing locationRadius control sync'
  grep -q "document.getElementById('saveAirbandRadius')" web/app.js || failmsg 'missing existing Apply Radius button bridge'
  grep -q 'aircraftMapFirstFit = false' web/app.js || failmsg 'missing original first-fit suppression for pop-out receiver mode'
  grep -q 'receiverRadiusBounds' web/app.js || failmsg 'missing receiver-radius bounds calculation'
  grep -q 'fitActivePlanes' web/app.js || failmsg 'missing plane auto-fit function'
  grep -q 'updateAircraftMap = function(records)' web/app.js || failmsg 'missing updateAircraftMap wrapper for kiosk auto-fit'
  grep -q 'renderLocation = function(location)' web/app.js || failmsg 'missing renderLocation wrapper for radio radius sync'
fi

if [[ $fail -eq 0 ]]; then
  pass 'Map pop-out kiosk defaults V3 validation complete'
else
  failmsg 'validation failed'
fi

exit "$fail"
