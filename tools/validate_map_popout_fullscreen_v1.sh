#!/usr/bin/env bash
set -u

fail=0
pass() { printf 'PASS: %s\n' "$1"; }
failmsg() { printf 'FAIL: %s\n' "$1"; fail=1; }

[[ -f web/app.js ]] || failmsg 'web/app.js not found; run from repo root'
[[ -f web/app.css ]] || failmsg 'web/app.css not found; run from repo root'

if [[ -f web/app.js ]]; then
  if command -v node >/dev/null 2>&1; then
    if node --check web/app.js >/tmp/map_popout_node_check.out 2>&1; then
      pass 'JavaScript syntax check passed'
    else
      cat /tmp/map_popout_node_check.out
      failmsg 'JavaScript syntax check failed'
    fi
  else
    failmsg 'node not found; cannot validate JavaScript syntax'
  fi

  grep -q 'MAP_POPOUT_FULLSCREEN_V1_START' web/app.js || failmsg 'missing JavaScript marker MAP_POPOUT_FULLSCREEN_V1_START'
  grep -q 'map_popout' web/app.js || failmsg 'missing map_popout query parameter logic'
  grep -q 'Pop Out Map' web/app.js || failmsg 'missing Pop Out Map button text'
  grep -q 'requestFullscreen' web/app.js || failmsg 'missing browser Fullscreen API call'
  grep -q 'invalidateSize' web/app.js || failmsg 'missing Leaflet invalidateSize after layout change'
fi

if [[ -f web/app.css ]]; then
  grep -q 'MAP_POPOUT_FULLSCREEN_V1_START' web/app.css || failmsg 'missing CSS marker MAP_POPOUT_FULLSCREEN_V1_START'
  grep -q 'body.map-popout-window' web/app.css || failmsg 'missing pop-out body CSS class'
  grep -q '#aircraftMap' web/app.css || failmsg 'missing aircraft map pop-out sizing CSS'
fi

if [[ $fail -eq 0 ]]; then
  pass 'Map pop-out/fullscreen V1 validation complete'
else
  failmsg 'validation failed'
fi

exit "$fail"
