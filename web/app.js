
// V9 DOM-based aircraft marker double-click bridge.
// Uses the real map container id (#aircraftMap), stops Leaflet double-click
// zoom at window capture, and reuses the existing aircraft-list click behavior.
(function(){
  if(window.__rtpV39DomAircraftMarkerDblclickInstalled)return;
  window.__rtpV39DomAircraftMarkerDblclickInstalled=true;

  function rtpV39Path(event){
    try{if(event&&typeof event.composedPath==="function")return event.composedPath();}catch(_e){}
    const out=[];
    let node=event&&event.target;
    while(node){out.push(node);node=node.parentNode;}
    try{out.push(window);}catch(_e){}
    return out;
  }

  function rtpV39IsElement(node){
    return !!(node&&node.nodeType===1);
  }

  function rtpV39IsInAircraftMap(event){
    const path=rtpV39Path(event);
    for(const node of path){
      if(!rtpV39IsElement(node))continue;
      try{
        if(node.id==="aircraftMap")return true;
        if(node.classList&&(
          node.classList.contains("leaflet-container")||
          node.classList.contains("leaflet-map-pane")||
          node.classList.contains("leaflet-marker-pane")||
          node.classList.contains("leaflet-marker-icon")||
          node.classList.contains("aircraft-icon-wrap")
        ))return true;
      }catch(_e){}
    }
    return false;
  }

  function rtpV39FindMarkerIcon(event){
    const path=rtpV39Path(event);
    for(const node of path){
      if(!rtpV39IsElement(node))continue;
      try{
        if(node.classList&&node.classList.contains("leaflet-marker-icon"))return node;
      }catch(_e){}
    }
    for(const node of path){
      if(!rtpV39IsElement(node))continue;
      try{
        if(node.classList&&node.classList.contains("aircraft-icon-wrap"))return node;
      }catch(_e){}
    }
    return null;
  }

  function rtpV39Stop(event){
    try{if(event&&typeof L!=="undefined"&&L.DomEvent)L.DomEvent.stop(event);}catch(_e){}
    try{event.preventDefault();}catch(_e){}
    try{event.stopPropagation();}catch(_e){}
    try{event.stopImmediatePropagation();}catch(_e){}
    return false;
  }

  function rtpV39DisableLeafletDblZoom(){
    // Best effort only. The primary protection is stopping the event at window capture.
    try{
      const mapEl=document.getElementById("aircraftMap");
      if(mapEl&&mapEl._leaflet_id&&window.L){
        // Leaflet does not provide a public map lookup by element. Leave this as no-op.
      }
    }catch(_e){}
  }

  function rtpV39CleanToken(value){
    const s=String(value||"").trim().toUpperCase();
    if(!s)return "";
    const match=s.match(/[A-Z0-9]{3,8}/);
    return match?match[0]:"";
  }

  function rtpV39MarkerTokens(markerIcon){
    const tokens=[];
    function add(value){
      const token=rtpV39CleanToken(value);
      if(token&&!tokens.includes(token))tokens.push(token);
    }
    if(markerIcon){
      try{
        const d=markerIcon.dataset||{};
        add(d.aircraftHex||d.hex||d.icao||d.callsign||d.flight);
      }catch(_e){}
      try{add(markerIcon.getAttribute("data-aircraft-hex"));}catch(_e){}
      try{add(markerIcon.getAttribute("data-hex"));}catch(_e){}
      try{add(markerIcon.getAttribute("title"));}catch(_e){}
      try{add(markerIcon.getAttribute("aria-label"));}catch(_e){}
      try{add(markerIcon.textContent);}catch(_e){}
      try{
        const wrapped=markerIcon.querySelector&&markerIcon.querySelector(".aircraft-icon-wrap");
        if(wrapped)add(wrapped.textContent);
      }catch(_e){}
    }
    return tokens;
  }

  function rtpV39OutsideMap(element){
    try{
      const map=document.getElementById("aircraftMap");
      return !!(element&&(!map||!map.contains(element)));
    }catch(_e){return true;}
  }

  function rtpV39CandidateListElements(){
    const selectors=[
      "[data-aircraft-hex]",
      "[data-hex]",
      "[data-icao]",
      "[data-flight]",
      ".aircraft-row",
      ".aircraft-item",
      ".aircraft-card",
      ".aircraft-list-row",
      "#aircraft-list tr",
      "#aircraft-table tr",
      "#aircraft-body tr",
      "tbody tr",
      "tr",
      "li",
      "[role='button']",
      "button",
      "div"
    ].join(",");
    try{
      return Array.from(document.querySelectorAll(selectors)).filter(rtpV39OutsideMap);
    }catch(_e){return [];}
  }

  function rtpV39ScoreElement(element,tokens){
    if(!element||!tokens||!tokens.length)return 0;
    let score=0;
    let text="";
    try{text=String(element.textContent||"").toUpperCase();}catch(_e){}
    let data="";
    try{
      const d=element.dataset||{};
      data=String(d.aircraftHex||d.hex||d.icao||d.flight||d.callsign||"").toUpperCase();
    }catch(_e){}

    for(const token of tokens){
      if(data&&data===token)score=Math.max(score,100);
      if(data&&data.includes(token))score=Math.max(score,90);
      if(text){
        if(text===token)score=Math.max(score,80);
        else if(text.includes(token))score=Math.max(score,60);
      }
    }

    try{
      const tag=String(element.tagName||"").toUpperCase();
      const cls=String(element.className||"").toLowerCase();
      if(tag==="TR")score+=20;
      if(cls.includes("aircraft"))score+=20;
      if(element.hasAttribute("data-aircraft-hex")||element.hasAttribute("data-hex")||element.hasAttribute("data-icao"))score+=20;
      if(text.length>800)score-=20;
    }catch(_e){}

    return score;
  }

  function rtpV39FindMatchingListElement(tokens){
    const candidates=rtpV39CandidateListElements();
    let best=null;
    let bestScore=0;
    for(const el of candidates){
      const score=rtpV39ScoreElement(el,tokens);
      if(score>bestScore){
        best=el;
        bestScore=score;
      }
    }
    return bestScore>0?best:null;
  }

  function rtpV39DispatchExistingListClick(element){
    if(!element)return false;
    try{element.scrollIntoView({block:"nearest",inline:"nearest"});}catch(_e){}
    const events=[
      ["pointerdown",PointerEvent],
      ["mousedown",MouseEvent],
      ["mouseup",MouseEvent],
      ["click",MouseEvent]
    ];
    for(const item of events){
      const type=item[0],Ctor=item[1]||MouseEvent;
      try{
        element.dispatchEvent(new Ctor(type,{bubbles:true,cancelable:true,view:window,pointerType:"mouse",button:0,buttons:type.endsWith("down")?1:0}));
      }catch(_e){
        try{element.dispatchEvent(new MouseEvent(type,{bubbles:true,cancelable:true,view:window,button:0}));}catch(_e2){}
      }
    }
    try{if(typeof element.click==="function")element.click();}catch(_e){}
    return true;
  }

  function rtpV39HandleDblclick(event){
    if(!rtpV39IsInAircraftMap(event))return;
    const markerIcon=rtpV39FindMarkerIcon(event);
    const tokens=rtpV39MarkerTokens(markerIcon);

    // Stop map zoom first, before doing any slower DOM work.
    rtpV39Stop(event);
    rtpV39DisableLeafletDblZoom();

    let listElement=null;
    let clicked=false;
    if(markerIcon&&tokens.length){
      listElement=rtpV39FindMatchingListElement(tokens);
      clicked=rtpV39DispatchExistingListClick(listElement);
    }

    if(markerIcon&&!clicked){
      // Fallback: preserve marker popup usability.
      try{markerIcon.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,view:window,button:0}));}catch(_e){}
    }

    try{
      window.__rtpV39DomAircraftMarkerDblclickStatus={
        installed:true,
        handled:true,
        mapDblclick:true,
        markerIconFound:!!markerIcon,
        tokens,
        listElementFound:!!listElement,
        listClickDispatched:!!clicked,
        targetTag:event&&event.target&&event.target.tagName||null,
        targetClass:String(event&&event.target&&event.target.className||""),
        lastHandledUtc:new Date().toISOString()
      };
    }catch(_e){}

    return false;
  }

  function rtpV39Install(){
    if(window.__rtpV39DomAircraftMarkerDblclickBound)return;
    window.__rtpV39DomAircraftMarkerDblclickBound=true;
    window.addEventListener("dblclick",rtpV39HandleDblclick,true);
  }

  try{rtpV39Install();}catch(_e){}
  try{document.addEventListener("DOMContentLoaded",rtpV39Install);}catch(_e){}
})();



// V8 temporary double-click event logger.
// Logs browser dblclick event routing to backend /api/debug/ui-event.




// V7 aircraft marker double-click bridge.
// Reuses the existing aircraft-list click behavior that already opens the
// aircraft details dialog. Single-click marker behavior is left alone.




// V6 safe aircraft marker double-click hook.
// This intentionally does not disable normal Leaflet click handling and does
// not install click/mousedown handlers, so normal single-click marker popups
// continue to work.




// V5 aircraft marker double-click hook.
// This operates at the Leaflet marker layer so it does not depend on the name
// of the aircraft render/update function in this UI build.



// Extracted from web/index.html by refactor_inline_ui_assets.py

'use strict';

let audioObjectUrl = null;
let liveListening = false;
let liveAudioContext = null;
let noaaAudioPreparedForStart = false; /* Step 60: NOAA prepares browser audio before selection and owns receiver */
let noaaAudioUsesAirbandContext = false; /* Step 65: NOAA browser playback context and reconnect support */
let noaaPlaybackChunksScheduled = 0;
let noaaPlaybackLastChunkRms = null; /* Step 72: dedicated NOAA browser AudioContext after Airband handoff */
let noaaHtmlAudioElement = null; /* Step 75: NOAA HTML audio element queue replaces silent Web Audio scheduling */
let noaaHtmlAudioQueue = [];
let noaaHtmlAudioCurrentUrl = null;
let noaaHtmlAudioPrimerUrl = null;
let noaaHtmlAudioFetchBusy = false;
let noaaHtmlAudioRealPlaybackStarted = false;
let noaaHtmlAudioGeneration = 0;
let liveNextCursor = 0;
let liveNextPlayTime = 0;
let livePumpTimer = null;
let airbandAudioContext = null;
let airbandAudioAuthorized = false;
let airbandAudioCursor = 0;
let airbandNextPlayTime = 0;
let airbandPumpTimer = null;
let airbandPlayingHoldId = null;
let airbandLastPlaybackMuted = false;
let airbandLastPlaybackRms = null;
let airbandLastPlaybackSquelchLabel = '';
let airbandTestPlayedEventId = 0;
let aircraftMap = null;
let receiverMapMarker = null;
let receiverRangeRings = null;
let receiverMapLocation = null;
let aircraftMapMarkers = new Map();
let aircraftLastPositions = new Map();
let aircraftTrailSegments = new Map();
let aircraftMapFirstFit = true;
let receiverInitialMapViewApplied = false;
let receiverLocationPickActive = false;
let receiverLocationPreview = null;
const TRAIL_STORAGE_KEY = 'rtlPiAdsbTrailHistoryV1';
const TRAIL_RETENTION_KEY = 'rtlPiAdsbTrailRetentionMinutes';
const TRAIL_DISPLAY_MODE_KEY = 'rtlAdsbTrailDisplayModeV1';
const TRAIL_CLEARED_AT_KEY = 'rtlPiAdsbTrailClearedAtV1';
let aircraftTrailHistory = new Map();
let aircraftTrailRetentionMinutes = 240;
let aircraftTrailDisplayMode = localStorage.getItem(TRAIL_DISPLAY_MODE_KEY) || 'active';
if (aircraftTrailDisplayMode !== 'active' && aircraftTrailDisplayMode !== 'history') aircraftTrailDisplayMode = 'active';
let aircraftTrailClearedAt = Number(localStorage.getItem(TRAIL_CLEARED_AT_KEY) || '0');
const ACTIVE_AIRCRAFT_STALE_SECONDS = 60;
const INITIAL_MAP_RADIUS_MILES = 30; // PI_INITIAL_MAP_RELOAD_30_MILES_V1 // PI_INITIAL_MAP_RELOAD_30_MILES_V1
const METERS_PER_MILE = 1609.344;

function el(id) { return document.getElementById(id); }
function setText(id, value) { const node = el(id); if (node) node.textContent = value; }
function formattedNumber(value) { return typeof value === 'number' ? value.toLocaleString() : '—'; }
function setMessage(id, message, kind) {
  const node = el(id);
  if (!node) return;
  node.textContent = message;
  node.className = 'message ' + (kind || '');
}
async function jsonRequest(url, options) {
  const response = await fetch(url, Object.assign({cache: 'no-store'}, options || {}));
  let result = null;
  try { result = await response.json(); } catch (_) {}
  if (!response.ok) {
    throw new Error((result && result.error) ? result.error : `Request failed: HTTP ${response.status}`);
  }
  return result;
}

/* Step 70: validate operation status API objects before property access */
function requireObjectResponse(value, label) {
  if (value && typeof value === 'object' && !Array.isArray(value)) return value;
  throw new Error(`${label} returned no status data; the service may be restarting`);
}

function altitudeFeet(aircraft) {
  const value = aircraft.alt_baro != null ? aircraft.alt_baro : (aircraft.altitude != null ? aircraft.altitude : aircraft.alt_geom);
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function aircraftSeenSeconds(aircraft) {
  const seen = Number(aircraft && aircraft.seen);
  if (Number.isFinite(seen)) return seen;
  const seenPos = Number(aircraft && aircraft.seen_pos);
  if (Number.isFinite(seenPos)) return seenPos;
  return null;
}
function isAircraftRecordActive(aircraft) {
  const seenSeconds = aircraftSeenSeconds(aircraft);
  return seenSeconds == null || seenSeconds <= ACTIVE_AIRCRAFT_STALE_SECONDS;
}
function trailColor(altitude) {
  if (altitude == null) return '#a0aab8';
  if (altitude < 5001) return '#39ff14';
  if (altitude < 10001) return '#087830';
  if (altitude < 20001) return '#39cfff';
  if (altitude < 30001) return '#1851b5';
  if (altitude < 40001) return '#d4a600';
  return '#ff3030';
}
function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;').replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
function initializeAircraftMap() {
  if (typeof L === 'undefined') {
    setMessage('mapMessage', 'Map library could not load. The browser workstation must have internet access for Leaflet and map tiles.', 'error');
    return;
  }
  // LEAFLET_GLOBAL_NO_TILE_FADE_V1:
  // Disable Leaflet's JavaScript opacity ramp before any tile layer exists.
  aircraftMap = L.map('aircraftMap', {
    fadeAnimation: false
  }).setView([29.7604, -95.3698], 9);

  aircraftMap.on('click', finishReceiverLocationPick);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(aircraftMap);
}
function fitMapToReceiverRadius(position, radiusMiles) {
  if (!aircraftMap || !Array.isArray(position) || position.length < 2) return;
  const radiusMeters = Number(radiusMiles) * METERS_PER_MILE;
  if (!Number.isFinite(radiusMeters) || radiusMeters <= 0) return;
  const bounds = L.circle(position, {radius: radiusMeters}).getBounds();
  aircraftMap.fitBounds(bounds, {padding: [18, 18]});
}

function setReceiverPreviewOnMap(latitude, longitude) {
  if (!aircraftMap) return;
  const position = [Number(latitude), Number(longitude)];
  receiverLocationPreview = position;
  if (!receiverMapMarker) {
    receiverMapMarker = L.circleMarker(position, {
      radius: 8, color: '#f2c35c', weight: 3, fillColor: '#2778d4', fillOpacity: 0.95
    }).addTo(aircraftMap).bindPopup('');
  } else {
    receiverMapMarker.setLatLng(position);
    if (receiverMapMarker.setStyle) receiverMapMarker.setStyle({color: '#f2c35c', weight: 3});
  }
  receiverMapMarker.setPopupContent(
    `<strong>Receiver Location Preview</strong><br>${position[0].toFixed(6)}, ${position[1].toFixed(6)}<br>Click Save Receiver Location to confirm.`
  );
  receiverMapMarker.openPopup();
  drawReceiverRangeRings(position);
}
function beginReceiverLocationPick() {
  if (!aircraftMap) {
    setMessage('locationMessage', 'Map is not available for location selection.', 'error');
    return;
  }
  receiverLocationPickActive = true;
  el('pickLocationOnMap').disabled = true;
  el('cancelLocationPick').disabled = false;
  el('aircraftMap').classList.add('map-location-pick-active');
  if (typeof closeMenu === 'function') closeMenu();
  setMessage(
    'mapMessage',
    'Location selection active: click the map at the physical antenna location.',
    'warning'
  );
}
function finishReceiverLocationPick(event) {
  if (!receiverLocationPickActive) return;
  const latitude = Number(event.latlng.lat);
  const longitude = Number(event.latlng.lng);

  el('locationLatitude').value = latitude.toFixed(6);
  el('locationLongitude').value = longitude.toFixed(6);
  if (el('locationName')) el('locationName').dataset.edited = 'true';
  setReceiverPreviewOnMap(latitude, longitude);

  receiverLocationPickActive = false;
  el('pickLocationOnMap').disabled = false;
  el('cancelLocationPick').disabled = true;
  el('aircraftMap').classList.remove('map-location-pick-active');

  if (typeof openMenu === 'function') openMenu();
  const pickerButton = el('pickLocationOnMap');
  const settings = el('configurationDetails') || (pickerButton ? pickerButton.closest('details') : null);
  if (settings) settings.open = true;

  setMessage(
    'locationMessage',
    `Map selection preview: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}. Click Save Receiver Location to confirm.`,
    'warning'
  );
  setMessage('mapMessage', 'Receiver location preview selected. Save it from Configuration to apply.', 'warning');
}
function cancelReceiverLocationPick() {
  receiverLocationPickActive = false;
  el('pickLocationOnMap').disabled = false;
  el('cancelLocationPick').disabled = true;
  el('aircraftMap').classList.remove('map-location-pick-active');
  setMessage('locationMessage', 'Map location selection cancelled. Saved receiver location is unchanged.', '');
  setMessage('mapMessage', 'Map location selection cancelled.', '');
}

function drawReceiverRangeRings(position) {
  if (!aircraftMap || !position) return;
  if (receiverRangeRings) aircraftMap.removeLayer(receiverRangeRings);
  receiverRangeRings = L.layerGroup().addTo(aircraftMap);

  const milesToMeters = 1609.344;
  const center = [Number(position[0]), Number(position[1])];

  for (let miles = 5; miles <= 100; miles += 5) {
    const major = miles % 25 === 0;
    L.circle(center, {
      radius: miles * milesToMeters,
      color: major ? '#3e4650' : '#1d232a',
      weight: major ? 2.0 : 0.75,
      opacity: major ? 0.82 : 0.62,
      fill: false,
      interactive: false,
      dashArray: major ? null : '3 5'
    }).addTo(receiverRangeRings);

    if (major) {
      const labelPoint = L.latLng(center[0] + (miles / 69.0), center[1]);
      L.marker(labelPoint, {
        interactive: false,
        keyboard: false,
        icon: L.divIcon({
          className: '',
          html: `<div class="range-ring-major-label">${miles} mi</div>`,
          iconSize: [45, 18],
          iconAnchor: [22, 9]
        })
      }).addTo(receiverRangeRings);
    }
  }
}

function setReceiverOnMap(location) {
  if (!aircraftMap || !location) return;
  const position = [Number(location.latitude), Number(location.longitude)];
  receiverMapLocation = position;
  if (!receiverMapMarker) {
    receiverMapMarker = L.circleMarker(position, {
      radius: 8, color: '#ffffff', weight: 2, fillColor: '#2778d4', fillOpacity: 0.95
    }).addTo(aircraftMap).bindPopup('');
  } else {
    receiverMapMarker.setLatLng(position);
  }
  receiverMapMarker.setPopupContent(`<strong>Receiver</strong><br>${escapeHtml(location.name || '')}<br>${position[0].toFixed(5)}, ${position[1].toFixed(5)}`);
  if (!receiverInitialMapViewApplied) {
    fitMapToReceiverRadius(position, INITIAL_MAP_RADIUS_MILES);
    // Apply the receiver-centered 30-mile startup view exactly once per page
    // load, regardless of whether aircraft or status data returned first.
    receiverInitialMapViewApplied = true;
    aircraftMapFirstFit = false;
  }
  if (receiverMapMarker && receiverMapMarker.setStyle) {
    receiverMapMarker.setStyle({color: '#ffffff', weight: 2});
  }
  receiverLocationPreview = null;
  drawReceiverRangeRings(position);
}
function aircraftMapSourceKey(aircraft) {
  const source = String(aircraft && aircraft.source || '').toLowerCase();
  const sourceLabel = String(aircraft && aircraft.source_label || '').toLowerCase();
  const sources = Array.isArray(aircraft && aircraft.sources)
    ? aircraft.sources.map(item => String(item || '').toLowerCase())
    : [];
  const hasUat = source.includes('uat_978') || sourceLabel.includes('uat') || sources.includes('uat_978');
  if (hasUat) return 'uat_978';
  return 'adsb_1090';
}

function aircraftMapIconPath(sourceKey) {
  if (sourceKey === 'uat_978') {
    return {
      className: 'aircraft-source-uat',
      title: '978 UAT prop-plane traffic',
      path: 'M20 3 L22 8 L21 16 L33 20 L33 23 L22 22 L22 32 L27 36 L27 38 L20 36 L13 38 L13 36 L18 32 L18 22 L7 23 L7 20 L19 16 L18 8 Z',
      propeller: 'M9 6 C13 3 17 3 20 6 C23 3 27 3 31 6 C27 9 23 9 20 6 C17 9 13 9 9 6 Z'
    };
  }
  return {
    className: 'aircraft-source-adsb',
    title: '1090 ADS-B jet traffic',
    path: 'M20 2 L23 15 L36 20 L36 23 L23 21 L22 34 L27 37 L27 39 L20 37 L13 39 L13 37 L18 34 L17 21 L4 23 L4 20 L17 15 Z',
    propeller: ''
  };
}

function aircraftMapIcon(aircraft) {
  const color = '#5f6670';
  const track = Number.isFinite(Number(aircraft.track)) ? Number(aircraft.track) : 0;
  const flight = aircraft.flight ? String(aircraft.flight).trim() : '';
  const label = flight || String(aircraft.hex || '').toUpperCase();
  const sourceKey = aircraftMapSourceKey(aircraft);
  const iconShape = aircraftMapIconPath(sourceKey);
  const propeller = iconShape.propeller
    ? `<path d="${iconShape.propeller}" fill="${color}" stroke="#ffffff" stroke-width="1.25" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`
    : '';
  const html = `<div class="aircraft-icon-wrap ${iconShape.className}" data-aircraft-source="${sourceKey}" title="${escapeHtml(iconShape.title)}">` +
    `<svg width="28" height="28" viewBox="0 0 40 40" style="transform:rotate(${track}deg)" aria-hidden="true">` +
    propeller +
    `<path d="${iconShape.path}"` +
    ` fill="${color}" stroke="#ffffff" stroke-width="1.25" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>` +
    `</svg>` +
    `<span class="aircraft-icon-label">${escapeHtml(label)}</span>` +
    `</div>`;
  return L.divIcon({
    className: '',
    html: html,
    iconSize: [33, 31],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14]
  });
}

function aircraftPopup(aircraft) {
  const flight = aircraft.flight ? String(aircraft.flight).trim() : '';
  const altitude = altitudeFeet(aircraft);
  const speed = aircraft.gs == null ? '—' : `${aircraft.gs} kt`;
  const track = aircraft.track == null ? '—' : `${aircraft.track}°`;
  return `<strong>${escapeHtml(flight || aircraft.hex || 'Unknown')}</strong><br>` +
    `ICAO: ${escapeHtml(aircraft.hex || '')}<br>` +
    `Altitude: ${altitude == null ? '—' : altitude.toLocaleString() + ' ft'}<br>` +
    `Speed: ${escapeHtml(speed)} &nbsp; Track: ${escapeHtml(track)}`;
}
function trailCutoffTime() {
  const retentionCutoff = aircraftTrailRetentionMinutes > 0
    ? Date.now() - aircraftTrailRetentionMinutes * 60000
    : 0;
  return Math.max(retentionCutoff, aircraftTrailClearedAt);
}
function pruneTrailHistory() {
  const cutoff = trailCutoffTime();
  let allPoints = [];
  for (const [key, points] of aircraftTrailHistory.entries()) {
    const retained = points.filter(point => !cutoff || point.time >= cutoff).slice(-1440);
    if (retained.length) {
      aircraftTrailHistory.set(key, retained);
      allPoints.push(...retained.map(point => ({key: key, point: point})));
    } else {
      aircraftTrailHistory.delete(key);
    }
  }
  if (allPoints.length > 12000) {
    allPoints.sort((a, b) => a.point.time - b.point.time);
    const removeCount = allPoints.length - 12000;
    for (const entry of allPoints.slice(0, removeCount)) {
      const points = aircraftTrailHistory.get(entry.key) || [];
      const index = points.indexOf(entry.point);
      if (index >= 0) points.splice(index, 1);
      if (!points.length) aircraftTrailHistory.delete(entry.key);
    }
  }
}
function saveTrailHistory() {
  try {
    pruneTrailHistory();
    const serializable = Object.fromEntries(aircraftTrailHistory.entries());
    if (aircraftTrailHistory.size) {
      localStorage.setItem(TRAIL_STORAGE_KEY, JSON.stringify(serializable));
    } else {
      localStorage.removeItem(TRAIL_STORAGE_KEY);
    }
    localStorage.setItem(TRAIL_RETENTION_KEY, String(aircraftTrailRetentionMinutes));
    localStorage.setItem(TRAIL_DISPLAY_MODE_KEY, aircraftTrailDisplayMode);
  } catch (_) {
    setMessage('mapMessage', 'Map is live, but browser storage could not save aircraft trails.', 'warning');
  }
}
function loadTrailHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(TRAIL_STORAGE_KEY) || '{}');
    aircraftTrailHistory = new Map(Object.entries(saved).filter(([, points]) => Array.isArray(points)));
    pruneTrailHistory();
  } catch (_) {
    aircraftTrailHistory = new Map();
    localStorage.removeItem(TRAIL_STORAGE_KEY);
  }
}
function removeTrailLayersForAircraft(key) {
  if (!aircraftMap) return;
  const segments = aircraftTrailSegments.get(key) || [];
  for (const segment of segments) aircraftMap.removeLayer(segment);
  aircraftTrailSegments.delete(key);
}
function removeTrailLayers() {
  if (!aircraftMap) return;
  for (const key of Array.from(aircraftTrailSegments.keys())) removeTrailLayersForAircraft(key);
}
function formatTrailLastSeen(timestamp) {
  const milliseconds = Number(timestamp);
  if (!Number.isFinite(milliseconds) || milliseconds <= 0) return 'Unknown';
  return new Intl.DateTimeFormat([], {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short'
  }).format(new Date(milliseconds));
}

const trailRouteHoverCache = new Map();

async function updateTrailTooltipRoute(segment, tooltipHeader, flight) {
  const callsign = String(flight || '').trim().toUpperCase();
  if (!callsign) return;

  segment.setTooltipContent(`${tooltipHeader}<br>From / To: Looking up…`);

  let routePromise = trailRouteHoverCache.get(callsign);
  if (!routePromise) {
    routePromise = requestAirlabsDiagnosticRoute(callsign);
    trailRouteHoverCache.set(callsign, routePromise);
  }

  try {
    const result = await routePromise;
    if (!result.matched) {
      trailRouteHoverCache.delete(callsign);
      segment.setTooltipContent(
        `${tooltipHeader}<br>From / To: Unavailable`
      );
      return;
    }

    const origin = escapeHtml(formatAirlabsAirport(result.departure_iata, result.departure_icao));
    const destination = escapeHtml(formatAirlabsAirport(result.arrival_iata, result.arrival_icao));
    const source = result.cache_hit ? 'AirLabs (cached)' : 'AirLabs';
    segment.setTooltipContent(
      `${tooltipHeader}<br>From: ${origin}<br>To: ${destination}<br>Source: ${source}`
    );
  } catch (error) {
    trailRouteHoverCache.delete(callsign);
    segment.setTooltipContent(`${tooltipHeader}<br>From / To: Lookup unavailable`);
  }
}

function addTrailSegment(key, prior, current) {
  const segment = L.polyline(
    [[prior.lat, prior.lon], [current.lat, current.lon]],
    {color: trailColor(current.altitude), weight: 3, opacity: 0.86}
  ).addTo(aircraftMap);

  const flight = String(current.flight || prior.flight || '').trim();
  const identifier = flight || String(current.hex || prior.hex || key || '').toUpperCase();
  const identifierLabel = flight ? 'Flight' : 'Aircraft';
  const lastSeen = formatTrailLastSeen(current.time || prior.time);
  if (identifier) {
    const tooltipHeader =
      `<strong>${identifierLabel}: ${escapeHtml(identifier)}</strong><br>` +
      `Last Seen: ${escapeHtml(lastSeen)}`;
    const tooltipHtml = tooltipHeader +
      (flight ? '<br>From / To: Hover to look up' : '<br>From / To: Unavailable without callsign');
    segment.bindTooltip(tooltipHtml, {
      sticky: true,
      direction: 'top',
      opacity: 0.94,
      className: 'trail-hover-label'
    });
    if (flight) {
      segment.on('tooltipopen', () => updateTrailTooltipRoute(segment, tooltipHeader, flight));
    }
  }

  const segments = aircraftTrailSegments.get(key) || [];
  segments.push(segment);
  while (segments.length > 1440) aircraftMap.removeLayer(segments.shift());
  aircraftTrailSegments.set(key, segments);
}
function renderStoredTrails(activeKeys = null) {
  if (!aircraftMap) return;
  removeTrailLayers();
  aircraftLastPositions.clear();
  pruneTrailHistory();
  if (aircraftTrailDisplayMode === 'active' && !activeKeys) return;
  const allowedKeys = activeKeys ? new Set(Array.from(activeKeys, key => String(key))) : null;
  for (const [key, points] of aircraftTrailHistory.entries()) {
    if (allowedKeys && !allowedKeys.has(String(key))) continue;
    for (let index = 1; index < points.length; index += 1) {
      addTrailSegment(key, points[index - 1], points[index]);
    }
    if (points.length) {
      const last = points[points.length - 1];
      aircraftLastPositions.set(key, [last.lat, last.lon]);
    }
  }
}
function recordTrailPoint(key, point, altitude, aircraft) {
  const points = aircraftTrailHistory.get(key) || [];
  const previous = points.length ? points[points.length - 1] : null;
  if (previous && previous.lat === point[0] && previous.lon === point[1]) return;
  const current = {
    lat: point[0],
    lon: point[1],
    altitude: altitude,
    time: Date.now(),
    flight: aircraft && aircraft.flight ? String(aircraft.flight).trim() : '',
    hex: aircraft && aircraft.hex ? String(aircraft.hex).toUpperCase() : String(key).toUpperCase(),
    track: aircraft ? aircraft.track : null
  };
  if (previous && (aircraftTrailDisplayMode !== 'active' || aircraftMapMarkers.has(key))) addTrailSegment(key, previous, current);
  points.push(current);
  aircraftTrailHistory.set(key, points);
  aircraftLastPositions.set(key, point);
  saveTrailHistory();
}
async function loadTrailHistoryFromServer(restoreCleared = false) {
  try {
    const response = await fetch('/api/trails/history', {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const serverTrails = data.trails || {};
    const serverPointCount = Object.values(serverTrails)
      .reduce((total, points) => total + (Array.isArray(points) ? points.length : 0), 0);

    if (restoreCleared && serverPointCount > 0) {
      aircraftTrailClearedAt = 0;
      localStorage.removeItem(TRAIL_CLEARED_AT_KEY);
    }

    let restoredPointCount = 0;
    let hiddenByClearCount = 0;
    const beforeCount = Array.from(aircraftTrailHistory.values())
      .reduce((total, points) => total + points.length, 0);

    for (const [key, points] of Object.entries(serverTrails)) {
      if (!Array.isArray(points)) continue;
      const eligible = points.filter(point => {
        const allowed = restoreCleared || Number(point.time) >= aircraftTrailClearedAt;
        if (!allowed) hiddenByClearCount += 1;
        return allowed;
      });
      const existing = aircraftTrailHistory.get(key) || [];
      const merged = [...existing, ...eligible]
        .sort((left, right) => Number(left.time) - Number(right.time));
      const unique = [];
      const seen = new Set();
      for (const point of merged) {
        const signature = `${point.time}|${point.lat}|${point.lon}`;
        if (!seen.has(signature)) {
          seen.add(signature);
          unique.push(point);
        }
      }
      if (unique.length) {
        aircraftTrailHistory.set(key, unique);
      }
    }

    if (restoreCleared) {
      aircraftTrailDisplayMode = 'history';
      aircraftTrailRetentionMinutes = 240;
      if (el('trailRetention')) el('trailRetention').value = '240';
    }
    saveTrailHistory();
    renderStoredTrails(restoreCleared ? null : new Set(aircraftMapMarkers.keys()));

    const afterCount = Array.from(aircraftTrailHistory.values())
      .reduce((total, points) => total + points.length, 0);
    restoredPointCount = Math.max(0, afterCount - beforeCount);

    if (!serverPointCount) {
      setMessage('mapMessage', 'No saved positioned aircraft trail history yet.', '');
    } else if (restoreCleared) {
      setMessage('mapMessage',
        `Restored history: ${serverPointCount} stored points across ${Object.keys(serverTrails).length} aircraft; ${restoredPointCount} points were newly added to this map.`,
        'good');
    } else if (hiddenByClearCount) {
      setMessage('mapMessage',
        `History has ${serverPointCount} stored points, but ${hiddenByClearCount} pre-clear points remain hidden. Click Restore History to display them again.`,
        'warning');
    } else {
      setMessage('mapMessage',
        `Loaded history: ${serverPointCount} stored points across ${Object.keys(serverTrails).length} aircraft; ${restoredPointCount} points were newly added.`,
        'good');
    }
  } catch (error) {
    setMessage('mapMessage', `Trail history unavailable: ${error.message}`, 'error');
  }
}

function changeTrailRetention() {
  const value = el('trailRetention').value;
  if (value === 'active') {
    aircraftTrailDisplayMode = 'active';
    aircraftTrailRetentionMinutes = 240;
    saveTrailHistory();
    renderStoredTrails(new Set(aircraftMapMarkers.keys()));
    setMessage('mapMessage', 'Trails show only while aircraft are visible or active. History is retained for up to 4 hours and can be restored.', 'good');
    return;
  }
  aircraftTrailDisplayMode = 'history';
  aircraftTrailRetentionMinutes = Math.min(240, Math.max(15, Number(value) || 240));
  saveTrailHistory();
  renderStoredTrails();
  setMessage('mapMessage', `Showing stored trails from the last ${aircraftTrailRetentionMinutes} minutes.`, 'good');
}

function updateAircraftMap(aircraftRecords) {
  if (!aircraftMap) return;
  const positioned = aircraftRecords.filter(item => isAircraftRecordActive(item) && Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lon)));
  const visibleIds = new Set();

  for (const aircraft of positioned) {
    const key = String(aircraft.hex || aircraft.flight || `${aircraft.lat},${aircraft.lon}`);
    const point = [Number(aircraft.lat), Number(aircraft.lon)];
    visibleIds.add(key);
    const altitude = altitudeFeet(aircraft);
    const color = trailColor(altitude);
    recordTrailPoint(key, point, altitude, aircraft);

    let marker = aircraftMapMarkers.get(key);
    if (!marker) {
      marker = L.marker(point, {
        icon: aircraftMapIcon(aircraft),
        keyboard: false,
        riseOnHover: true
      }).addTo(aircraftMap);
      aircraftMapMarkers.set(key, marker);
    } else {
      marker.setLatLng(point);
      marker.setIcon(aircraftMapIcon(aircraft));
    }
    marker.bindPopup(aircraftPopup(aircraft));
  }

  for (const [key, marker] of aircraftMapMarkers.entries()) {
    if (!visibleIds.has(key)) {
      aircraftMap.removeLayer(marker);
      aircraftMapMarkers.delete(key);
      aircraftLastPositions.delete(key);
      // ACTIVE_TRAIL_CLEANUP_V3: when marker/icon is removed from the active display,
      // remove that aircraft's displayed trail layers too. Stored history remains intact.
      removeTrailLayersForAircraft(key);
    }
  }

  const mapStatusNode = el('mapMessage');
  if (!positioned.length) {
    setMessage('mapMessage', 'No positioned aircraft currently reported by readsb.', '');
  } else if (
    mapStatusNode &&
    /^(Waiting for aircraft positions|Displaying \d+ aircraft with positions)/.test(
      String(mapStatusNode.textContent || '').trim()
    )
  ) {
    setMessage('mapMessage', '', '');
  }

  if (aircraftMapFirstFit && receiverMapLocation && positioned.length) {
    const points = positioned.map(item => [Number(item.lat), Number(item.lon)]);
    if (receiverMapLocation) points.push(receiverMapLocation);
    aircraftMap.fitBounds(points, {padding: [30, 30], maxZoom: 11});
    aircraftMapFirstFit = false;
  }
}
function fitAircraftMap() {
  if (!aircraftMap) return;
  const points = Array.from(aircraftMapMarkers.values()).map(marker => marker.getLatLng());
  if (receiverMapLocation) points.push(L.latLng(receiverMapLocation[0], receiverMapLocation[1]));
  if (points.length) aircraftMap.fitBounds(points, {padding: [30, 30], maxZoom: 12});
}
function centerReceiverMap() {
  if (aircraftMap && receiverMapLocation) aircraftMap.setView(receiverMapLocation, 10);
}
function clearAircraftTrails() {
  if (!aircraftMap) return;

  removeTrailLayers();
  aircraftLastPositions.clear();
  aircraftTrailHistory.clear();

  aircraftTrailClearedAt = Date.now();
  localStorage.setItem(TRAIL_CLEARED_AT_KEY, String(aircraftTrailClearedAt));
  localStorage.removeItem(TRAIL_STORAGE_KEY);

  setMessage(
    'mapMessage',
    'Display cleared. Trail history is still stored for up to 4 hours; click Restore History to show it again.',
    'good'
  );
}

async function eraseTrailHistory() {
  const confirmed = window.confirm(
    'Erase all stored aircraft trail history collected so far? This cannot be restored.'
  );
  if (!confirmed) return;

  removeTrailLayers();
  aircraftLastPositions.clear();
  aircraftTrailHistory.clear();
  aircraftTrailClearedAt = Date.now();
  localStorage.setItem(TRAIL_CLEARED_AT_KEY, String(aircraftTrailClearedAt));
  localStorage.removeItem(TRAIL_STORAGE_KEY);

  setMessage('mapMessage', 'Erasing browser and stored aircraft trails...', 'warning');
  try {
    const response = await fetch('/api/trails/clear', {method: 'POST', cache: 'no-store'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    aircraftTrailClearedAt = Number(result.cleared_utc_ms || aircraftTrailClearedAt);
    localStorage.setItem(TRAIL_CLEARED_AT_KEY, String(aircraftTrailClearedAt));
    setMessage(
      'mapMessage',
      'Stored history erased. Only new post-erase movement will be retained.',
      'good'
    );
  } catch (error) {
    setMessage(
      'mapMessage',
      `Display cleared, but stored history erase failed: ${error.message}`,
      'error'
    );
  }
}

function updateAudioButtons(status) {
  const live = Boolean(status && status.live_audio_running);
  const busy = Boolean(status && status.audio_busy);
  el('startLive').disabled = busy || live;
  el('stopLive').disabled = !live;
  el('capture10').disabled = busy || live;
  el('autoNoaa').disabled = busy || live;
  const state = el('audioState');
  state.textContent = live ? 'Live' : (busy ? 'Busy' : 'Ready');
  state.className = 'value ' + ((busy || live) ? 'busy' : 'ready');
}

function renderLocation(location) {
  if (!location) {
    setMessage('locationMessage', 'No receiver location configured. Enter the antenna location and save it.', 'warning');
    return;
  }
  el('locationName').value = location.name || '';
  el('locationLatitude').value = location.latitude;
  el('locationLongitude').value = location.longitude;
  el('locationRadius').value = location.airband_radius_miles;
  setMessage('locationMessage',
    `Saved: ${location.name} (${Number(location.latitude).toFixed(6)}, ${Number(location.longitude).toFixed(6)}) · ${location.airband_radius_miles} mile radius.`,
    'good');
  if (el('airbandRadiusMessage')) {
    setMessage('airbandRadiusMessage', `Current Airband scan radius: ${Number(location.airband_radius_miles).toFixed(1)} miles.`, 'good');
  }
  setReceiverOnMap(location);
}


function sourceLabelForAircraft(aircraft) {
  const source = String(aircraft && aircraft.source || '').toLowerCase();
  const sources = Array.isArray(aircraft && aircraft.sources) ? aircraft.sources : [];
  if (sources.includes('adsb_1090') && sources.includes('uat_978')) return '1090+UAT';
  if (source.includes('uat_978')) return 'UAT';
  if (source.includes('adsb_1090')) return '1090';
  return '';
}
function renderTrafficSources(status) {
  const sourceStatus = status && (status.traffic_sources || status);
  const adsbToggle = el('trafficSource1090');
  const uatToggle = el('trafficSourceUat978');
  if (!sourceStatus || !adsbToggle || !uatToggle) return;
  const adsb = sourceStatus.adsb_1090 || {};
  const uat = sourceStatus.uat_978 || {};
  const adsbEnabled = sourceStatus.adsb_1090_enabled != null ? Boolean(sourceStatus.adsb_1090_enabled) : Boolean(adsb.enabled);
  const uatEnabled = sourceStatus.uat_978_enabled != null ? Boolean(sourceStatus.uat_978_enabled) : Boolean(uat.enabled);
  adsbToggle.checked = adsbEnabled;
  uatToggle.checked = uatEnabled;
  const parts = [
    `1090 ${adsbEnabled ? 'on' : 'off'}${adsb.running ? ' / running' : ''}`,
    `UAT ${uatEnabled ? 'on' : 'off'}${uat.running ? ' / running' : ''}`
  ];
  if (uat.collector_error) parts.push(`UAT collector: ${uat.collector_error}`);
  setMessage('trafficSourceMessage', `Unified aircraft feed: ${parts.join(' · ')}`, (adsbEnabled || uatEnabled) ? 'good' : 'warning');
}
async function loadTrafficSources() {
  try {
    renderTrafficSources(await jsonRequest('/api/settings/traffic-sources'));
  } catch (error) {
    setMessage('trafficSourceMessage', `Traffic source settings unavailable: ${error.message}`, 'error');
  }
}
async function saveTrafficSources() {
  const payload = {
    adsb_1090_enabled: Boolean(el('trafficSource1090') && el('trafficSource1090').checked),
    uat_978_enabled: Boolean(el('trafficSourceUat978') && el('trafficSourceUat978').checked)
  };
  if (!payload.adsb_1090_enabled && !payload.uat_978_enabled) {
    setMessage('trafficSourceMessage', 'At least one aircraft traffic source should remain enabled.', 'warning');
  }
  try {
    setMessage('trafficSourceMessage', 'Applying traffic source settings…', 'warning');
    const result = await jsonRequest('/api/settings/traffic-sources', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    renderTrafficSources(result);
    await updateStatus();
    await updateAircraft();
  } catch (error) {
    setMessage('trafficSourceMessage', `Traffic source update failed: ${error.message}`, 'error');
  }
}

async function updateStatus() {
  try {
    const status = requireObjectResponse(await jsonRequest('/api/status'), 'Receiver status');
    setText('stationName', status.noaa_station || 'NOAA Weather');
    setText('stationDetail',
      `NOAA: ${(Number(status.noaa_frequency_hz) / 1000000).toFixed(3)} MHz NFM · Audio RTL-SDR S/N: ${status.audio_receiver_serial || '—'}`);
    setText('messageCount', formattedNumber(status.messages));
    setText('aircraftCount', formattedNumber(status.aircraft_count));
    setText('positionCount', formattedNumber(status.aircraft_with_position));
    renderTrafficSources(status);
    updateAudioButtons(status);
    if (!el('locationName').dataset.edited) renderLocation(status.receiver_location);
  } catch (error) {
    setMessage('audioMessage', `Status failed: ${error.message}`, 'error');
  }
}

function detailValue(id, value) {
  el(id).textContent = value == null || String(value).trim() === '' ? '—' : String(value);
}
function formatAirport(airport) {
  if (!airport) return 'Unavailable';
  const code = airport.iata_code || airport.icao_code || '';
  const name = airport.name || airport.municipality || '';
  const place = airport.municipality && airport.name ? ` — ${airport.municipality}` : '';
  return `${name}${code ? ` (${code})` : ''}${place}` || 'Unavailable';
}
function closeAircraftDetails() {
  el('aircraftDetailOverlay').classList.remove('open');
}
function createDetailLink(text, url) {
  const link = document.createElement('a');
  link.textContent = text;
  link.href = url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  return link;
}
function updateTailNumberActions(registration) {
  const actions = el('aircraftLookupActions');
  actions.replaceChildren();
  const tail = String(registration || '').trim().toUpperCase();
  if (!tail) return;

  actions.appendChild(createDetailLink(
    `ADSBDB Tail Lookup: ${tail}`,
    `https://api.adsbdb.com/v0/aircraft/${encodeURIComponent(tail)}`
  ));

  if (/^N[0-9A-Z]{1,5}$/.test(tail)) {
    actions.appendChild(createDetailLink(
      'FAA N-Number Inquiry',
      'https://registry.faa.gov/aircraftinquiry/search/nnumberinquiry'
    ));
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.textContent = `Copy ${tail} for FAA Search`;
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(tail);
        setMessage('aircraftDetailStatus', `${tail} copied. Paste it into the FAA N-Number Inquiry form.`, 'good');
      } catch (_) {
        setMessage('aircraftDetailStatus', `FAA search tail number: ${tail}`, 'warning');
      }
    });
    actions.appendChild(copy);
  }
}
function likelyTailNumber(value) {
  const text = String(value || '').trim().toUpperCase().replace(/\s+/g, '');
  return /^N[0-9A-Z]{1,5}$/.test(text) ||
    /^[A-Z]{1,2}-[A-Z0-9]{2,6}$/.test(text) ||
    /^[A-Z]{2,5}[0-9]{1,5}$/.test(text);
}
function setAircraftPhotoCandidates(urls, description, options = {}) {
  const image = el('aircraftPhoto');
  const message = el('aircraftPhotoMessage');
  const actions = el('aircraftPhotoActions');
  const attribution = el('aircraftPhotoAttribution');
  const candidates = Array.from(new Set((Array.isArray(urls) ? urls : [])
    .map(value => String(value || '').trim())
    .filter(value => /^https?:\/\//i.test(value))));
  const fallback = typeof options.fallback === 'function' ? options.fallback : null;
  const sourceUrl = String(options.sourceUrl || '').trim();
  const sourceLinkLabel = options.sourceLinkLabel || 'Open Photograph Source';
  const defaultCaption = 'Exact-aircraft photos use ADSBDB when available; generic type fallback photos are labeled and sourced from Wikimedia Commons.';

  actions.replaceChildren();
  image.style.display = 'none';
  image.removeAttribute('src');
  image.referrerPolicy = 'no-referrer';
  image.decoding = 'async';
  message.style.display = 'block';
  message.textContent = description || 'No photograph available for this aircraft.';
  if (attribution) attribution.textContent = options.initialCaption || defaultCaption;

  const finishOrFallback = () => {
    if (fallback) { fallback(); return; }
    message.textContent = description || 'No photograph available for this aircraft.';
    if (sourceUrl) actions.appendChild(createDetailLink(sourceLinkLabel, sourceUrl));
    else if (candidates.length) actions.appendChild(createDetailLink('Open Aircraft Photograph', candidates[0]));
  };
  if (!candidates.length) { finishOrFallback(); return; }

  let index = 0;
  const tryNext = () => {
    if (index >= candidates.length) { finishOrFallback(); return; }
    const candidate = candidates[index++];
    image.onload = () => {
      message.style.display = 'none';
      image.style.display = 'block';
      actions.replaceChildren();
      actions.appendChild(createDetailLink(sourceUrl ? sourceLinkLabel : 'Open Full Photograph', sourceUrl || candidates[candidates.length - 1]));
      if (attribution && options.caption) attribution.textContent = options.caption;
    };
    image.onerror = tryNext;
    image.src = candidate;
  };
  tryNext();
}

async function fetchLocalAircraftByHex(rawHex) {
  const hex = String(rawHex || '').replace(/[^0-9A-Fa-f]/g, '').toUpperCase();
  if (hex.length !== 6) return null;
  try {
    const response = await fetch(`/api/aircraft/hex?hex=${encodeURIComponent(hex)}`, {cache: 'no-store'});
    if (!response.ok) return null;
    const payload = await response.json();
    return payload && payload.matched && payload.aircraft ? payload.aircraft : null;
  } catch (_) {
    return null;
  }
}
function localAircraftOperatorName(aircraft) {
  if (!aircraft || typeof aircraft !== 'object') return '';
  return String(
    aircraft.operator ||
    aircraft.registered_owner ||
    aircraft.owner_operator ||
    aircraft.ownOp ||
    ''
  ).trim();
}
function localAircraftRegistration(aircraft) {
  if (!aircraft || typeof aircraft !== 'object') return '';
  return String(aircraft.registration || aircraft.reg || '').trim().toUpperCase();
}
function localAircraftModelText(aircraft) {
  if (!aircraft || typeof aircraft !== 'object') return '';
  const type = String(aircraft.type || aircraft.icao_type || '').trim();
  const model = String(aircraft.model || '').trim();
  const description = String(aircraft.description || '').trim();
  if (model && type && !model.toUpperCase().includes(type.toUpperCase())) return `${model} (${type})`;
  return description || model || type;
}

async function fetchAircraftEnrichment(identifier, callsign = '') {
  if (!identifier) return null;
  let url = `https://api.adsbdb.com/v0/aircraft/${encodeURIComponent(identifier)}`;
  if (callsign) url += `?callsign=${encodeURIComponent(callsign)}`;
  const response = await fetch(url, {cache: 'no-store'});
  if (!response.ok) return null;
  const result = await response.json();
  return result.response && typeof result.response === 'object' ? result.response : null;
}
/* Step 69: Wikimedia Commons generic aircraft-type photo fallback */
let aircraftDetailPhotoRequestSequence = 0;
function genericAircraftPhotoSearchTerm(aircraft) {
  if (!aircraft || typeof aircraft !== 'object') return '';
  const manufacturer = String(aircraft.manufacturer || '').trim();
  const type = String(aircraft.type || aircraft.icao_type || '').trim();
  if (!type || type.toLowerCase() === 'unavailable') return '';
  return manufacturer && !type.toUpperCase().includes(manufacturer.toUpperCase()) ? `${manufacturer} ${type}` : type;
}
async function fetchGenericAircraftTypePhoto(aircraft) {
  const searchTerm = genericAircraftPhotoSearchTerm(aircraft);
  if (!searchTerm) return null;
  const params = new URLSearchParams({
    action: 'query', format: 'json', origin: '*', generator: 'search',
    gsrsearch: `${searchTerm} aircraft filetype:bitmap`, gsrnamespace: '6', gsrlimit: '8',
    prop: 'imageinfo', iiprop: 'url|mime', iiurlwidth: '720'
  });
  const response = await fetch(`https://commons.wikimedia.org/w/api.php?${params.toString()}`, {cache: 'force-cache'});
  if (!response.ok) return null;
  const payload = await response.json();
  const pages = Object.values(payload.query && payload.query.pages ? payload.query.pages : {})
    .filter(page => page.imageinfo && page.imageinfo[0] && page.imageinfo[0].thumburl)
    .filter(page => /^image\//i.test(String(page.imageinfo[0].mime || 'image/unknown')));
  if (!pages.length) return null;
  const unwanted = /(logo|diagram|drawing|cockpit|interior|seat|map|badge)/i;
  const page = pages.find(item => !unwanted.test(String(item.title || ''))) || pages[0];
  const info = page.imageinfo[0];
  return {
    searchTerm,
    thumbnailUrl: info.thumburl,
    sourceUrl: info.descriptionurl || `https://commons.wikimedia.org/wiki/${encodeURIComponent(String(page.title || '').replace(/ /g, '_'))}`
  };
}
async function applyGenericAircraftTypePhotoFallback(aircraft, requestSequence) {
  const searchTerm = genericAircraftPhotoSearchTerm(aircraft);
  if (!searchTerm || requestSequence !== aircraftDetailPhotoRequestSequence) return;
  el('aircraftPhotoMessage').textContent = `Searching for a generic ${searchTerm} photo…`;
  try {
    const result = await fetchGenericAircraftTypePhoto(aircraft);
    if (requestSequence !== aircraftDetailPhotoRequestSequence) return;
    if (!result) {
      setAircraftPhotoCandidates([], `No exact photograph or generic ${searchTerm} type photo was found.`);
      return;
    }
    setAircraftPhotoCandidates([result.thumbnailUrl], `A generic ${result.searchTerm} photo could not be displayed.`, {
      sourceUrl: result.sourceUrl,
      sourceLinkLabel: 'Open Wikimedia Commons Source',
      initialCaption: `Loading generic ${result.searchTerm} type photo from Wikimedia Commons…`,
      caption: `Generic ${result.searchTerm} type photo — not this specific aircraft. Source: Wikimedia Commons.`
    });
  } catch (_) {
    if (requestSequence === aircraftDetailPhotoRequestSequence) {
      setAircraftPhotoCandidates([], `Generic ${searchTerm} photo lookup unavailable.`);
    }
  }
}

/* Step 68: callsign ICAO-prefix operator fallback lookup */
function airlinePrefixFromCallsign(value) {
  const callsign = String(value || '').trim().toUpperCase().replace(/\s+/g, '');
  if (likelyTailNumber(callsign)) return '';
  const match = callsign.match(/^([A-Z]{3})[0-9][A-Z0-9]*$/);
  return match ? match[1] : '';
}
function routeOperatorFromAdsbdb(route) {
  if (!route || !route.airline || typeof route.airline !== 'object') return null;
  const name = String(route.airline.name || '').trim();
  if (!name) return null;
  return {
    name,
    icao: String(route.airline.icao || '').trim().toUpperCase(),
    iata: String(route.airline.iata || '').trim().toUpperCase(),
    source: 'ADSBDB route airline'
  };
}
let localOperatorPrefixLookupPromise = null;
async function loadLocalOperatorPrefixLookup() {
  if (!localOperatorPrefixLookupPromise) {
    localOperatorPrefixLookupPromise = fetch('/api/operator-prefixes.json', {cache: 'no-store'})
      .then(response => response.ok ? response.json() : {operators: {}})
      .catch(() => ({operators: {}}));
  }
  return localOperatorPrefixLookupPromise;
}
function operatorMatchFromRecord(prefix, record, source) {
  if (!record) return null;
  const normalized = typeof record === 'string' ? {name: record} : record;
  const name = String(normalized.name || normalized.operator || '').trim();
  if (!name) return null;
  return {
    name,
    icao: String(normalized.icao || prefix).trim().toUpperCase(),
    iata: String(normalized.iata || '').trim().toUpperCase(),
    telephony: String(normalized.telephony || '').trim(),
    category: String(normalized.category || '').trim(),
    source
  };
}
async function fetchLocalOperatorByCallsignPrefix(callsign) {
  const prefix = airlinePrefixFromCallsign(callsign);
  if (!prefix) return null;
  const payload = await loadLocalOperatorPrefixLookup();
  const operators = payload && payload.operators && typeof payload.operators === 'object' ? payload.operators : {};
  return operatorMatchFromRecord(prefix, operators[prefix], 'local ICAO-prefix table');
}
async function fetchAdsbdbOperatorByCallsignPrefix(callsign) {
  const prefix = airlinePrefixFromCallsign(callsign);
  if (!prefix) return null;
  const response = await fetch(`https://api.adsbdb.com/v0/airline/${encodeURIComponent(prefix)}`, {cache: 'no-store'});
  if (!response.ok) return null;
  const payload = await response.json();
  const rows = payload && payload.response;
  const candidates = Array.isArray(rows) ? rows : (rows && typeof rows === 'object' ? [rows] : []);
  const exact = candidates.find(item => String(item.icao || '').toUpperCase() === prefix) || candidates[0];
  return operatorMatchFromRecord(prefix, exact, 'ADSBDB ICAO-prefix fallback');
}
async function fetchOperatorByCallsignPrefix(callsign) {
  const localMatch = await fetchLocalOperatorByCallsignPrefix(callsign);
  if (localMatch) return localMatch;
  return fetchAdsbdbOperatorByCallsignPrefix(callsign);
}
function displayOperatorMatch(match) {
  if (!match || !match.name) return false;
  const code = match.icao || match.iata || '';
  let qualifier = '';
  if (match.source === 'local ICAO-prefix table') qualifier = ` — ${code || 'prefix'} local fallback`;
  else if (match.source === 'ADSBDB ICAO-prefix fallback') qualifier = ` — ${code || 'prefix'} ADSBDB fallback`;
  const extra = match.telephony ? ` (${match.telephony})` : '';
  detailValue('detailOperator', `${match.name}${extra}${qualifier}`);
  return true;
}
async function applyAirlabsRouteToDetails(flight) {
  const callsign = String(flight || '').trim().toUpperCase();
  if (!callsign) {
    detailValue('detailRouteSource', 'No callsign broadcast');
    return;
  }
  try {
    const result = await requestAirlabsDiagnosticRoute(callsign);
    if (!result.configured) {
      detailValue('detailRouteSource', 'AirLabs not configured');
      return;
    }
    if (!result.matched) {
      detailValue('detailRouteSource', 'AirLabs — no route match');
      return;
    }
    detailValue('detailOrigin', formatAirlabsAirport(result.departure_iata, result.departure_icao));
    detailValue('detailDestination', formatAirlabsAirport(result.arrival_iata, result.arrival_icao));
    detailValue('detailRouteSource', result.cache_hit ? 'AirLabs Flight Information API (cached)' : 'AirLabs Flight Information API');
    if (result.flight_iata) detailValue('detailFlight', `${callsign} / ${result.flight_iata}`);
  } catch (error) {
    detailValue('detailRouteSource', `AirLabs unavailable: ${error.message}`);
  }
}

async function showAircraftDetails(aircraft) {
  const flight = aircraft.flight ? String(aircraft.flight).trim().toUpperCase() : '';
  const rawHex = String(aircraft.hex || '').replace(/^~/, '').toUpperCase();
  const broadcastTail = likelyTailNumber(flight) ? flight : '';
  const airlinePrefix = airlinePrefixFromCallsign(flight);
  const title = flight || rawHex || 'Aircraft Details';
  const photoRequestSequence = ++aircraftDetailPhotoRequestSequence;

  el('aircraftDetailTitle').textContent = title;
  el('aircraftDetailOverlay').classList.add('open');
  detailValue('detailFlight', flight || 'Not broadcast');
  detailValue('detailHex', rawHex || 'Not broadcast');
  detailValue('detailRouteSource', 'Checking AirLabs…');
  detailValue('detailRegistration', broadcastTail || 'Loading…');
  detailValue('detailManufacturer', 'Loading…');
  detailValue('detailModel', 'Loading…');
  detailValue('detailOperator', 'Loading…');
  detailValue('detailOrigin', flight && !broadcastTail ? 'Loading…' : 'Route unavailable');
  detailValue('detailDestination', flight && !broadcastTail ? 'Loading…' : 'Route unavailable');
  detailValue('detailAltitude', aircraft.alt_baro == null ? '—' : `${aircraft.alt_baro} ft`);
  const speed = aircraft.gs == null ? '—' : `${aircraft.gs} kt`;
  const track = aircraft.track == null ? '—' : `${aircraft.track}°`;
  detailValue('detailMovement', `${speed} / ${track}`);
  updateTailNumberActions(broadcastTail);
  setAircraftPhotoCandidates([], 'Loading available aircraft photograph…');
  setMessage('aircraftDetailStatus', 'Loading aircraft and route lookup information…', 'warning');

  if (!rawHex && !broadcastTail) {
    setMessage('aircraftDetailStatus', 'No ICAO hex or tail number is available for aircraft lookup.', 'warning');
    detailValue('detailRegistration', 'Unavailable');
    detailValue('detailManufacturer', 'Unavailable');
    detailValue('detailModel', 'Unavailable');
    detailValue('detailOperator', 'Unavailable');
    setAircraftPhotoCandidates([], 'No aircraft photograph available.');
    return;
  }

  try {
    const localAircraft = rawHex ? await fetchLocalAircraftByHex(rawHex) : null;
    let payload = await fetchAircraftEnrichment(rawHex || broadcastTail, flight && !broadcastTail ? flight : '');
    let enrichedAircraft = payload ? payload.aircraft || null : null;
    let route = payload ? payload.flightroute || null : null;
    let operatorIdentified = false;

    // For private/general aviation, readsb often broadcasts the tail number as
    // flight. Use it as a second public aircraft-record lookup when Mode-S
    // did not yield an aircraft match.
    if (!enrichedAircraft && broadcastTail && broadcastTail !== rawHex) {
      payload = await fetchAircraftEnrichment(broadcastTail, '');
      enrichedAircraft = payload ? payload.aircraft || null : null;
      route = route || (payload ? payload.flightroute || null : null);
    }

    if (enrichedAircraft) {
      const registration = enrichedAircraft.registration || localAircraftRegistration(localAircraft) || broadcastTail || '';
      detailValue('detailRegistration', registration || 'Unavailable');
      detailValue('detailManufacturer', enrichedAircraft.manufacturer || (localAircraft && localAircraft.manufacturer) || 'Unavailable');
      detailValue('detailModel', enrichedAircraft.type || enrichedAircraft.icao_type || localAircraftModelText(localAircraft) || 'Unavailable');
      const registeredOwner = String(enrichedAircraft.registered_owner || localAircraftOperatorName(localAircraft) || '').trim();
      if (registeredOwner) {
        detailValue('detailOperator', registeredOwner);
        operatorIdentified = true;
      } else {
        detailValue('detailOperator', airlinePrefix ? 'Searching callsign prefix…' : 'Unavailable');
      }
      updateTailNumberActions(registration);
      setAircraftPhotoCandidates(
        [enrichedAircraft.url_photo_thumbnail, enrichedAircraft.url_photo],
        'No exact photograph available for this aircraft.',
        {fallback: () => applyGenericAircraftTypePhotoFallback(enrichedAircraft, photoRequestSequence)}
      );
    } else if (localAircraft) {
      const registration = localAircraftRegistration(localAircraft) || broadcastTail || '';
      const localModel = localAircraftModelText(localAircraft);
      const localOperator = localAircraftOperatorName(localAircraft);
      detailValue('detailRegistration', registration || 'Unavailable');
      detailValue('detailManufacturer', localAircraft.manufacturer || 'Unavailable');
      detailValue('detailModel', localModel || 'Unavailable');
      detailValue('detailOperator', localOperator || (airlinePrefix ? 'Searching callsign prefix…' : 'Unavailable'));
      operatorIdentified = Boolean(localOperator);
      updateTailNumberActions(registration || broadcastTail);
      setAircraftPhotoCandidates([], 'No exact aircraft photograph available from the local ICAO hex database.', {
        fallback: () => applyGenericAircraftTypePhotoFallback(localAircraft, photoRequestSequence)
      });
    } else {
      detailValue('detailRegistration', broadcastTail || 'Unavailable');
      detailValue('detailManufacturer', 'Unavailable');
      detailValue('detailModel', 'Unavailable');
      detailValue('detailOperator', airlinePrefix ? 'Searching callsign prefix…' : 'Unavailable');
      updateTailNumberActions(broadcastTail);
      setAircraftPhotoCandidates([], 'No photograph available for this aircraft.');
    }

    if (route) {
      detailValue('detailFlight', route.callsign || flight || 'Unavailable');
      detailValue('detailOrigin', formatAirport(route.origin));
      detailValue('detailDestination', formatAirport(route.destination));
    } else {
      detailValue('detailOrigin', 'Route unavailable');
      detailValue('detailDestination', 'Route unavailable');
    }

    if (!operatorIdentified) {
      operatorIdentified = displayOperatorMatch(routeOperatorFromAdsbdb(route));
    }
    if (!operatorIdentified && airlinePrefix) {
      try {
        const fallbackOperator = await fetchOperatorByCallsignPrefix(flight);
        operatorIdentified = displayOperatorMatch(fallbackOperator);
        if (!operatorIdentified) detailValue('detailOperator', `No operator match for ${airlinePrefix}`);
      } catch (operatorError) {
        detailValue('detailOperator', `${airlinePrefix} lookup unavailable`);
      }
    }

    if (enrichedAircraft || route || localAircraft) {
      setMessage('aircraftDetailStatus', localAircraft && !enrichedAircraft
        ? 'Aircraft lookup complete using the local ICAO hex database.'
        : 'Aircraft lookup complete. Tail-number actions are available below the photo.', 'good');
    } else {
      setMessage('aircraftDetailStatus', 'No public aircraft, local aircraft, or route match was found for this target.', 'warning');
    }
  } catch (error) {
    detailValue('detailRegistration', broadcastTail || 'Lookup unavailable');
    detailValue('detailManufacturer', 'Lookup unavailable');
    detailValue('detailModel', 'Lookup unavailable');
    detailValue('detailOperator', 'Lookup unavailable');
    detailValue('detailOrigin', 'Lookup unavailable');
    detailValue('detailDestination', 'Lookup unavailable');
    updateTailNumberActions(broadcastTail);
    setAircraftPhotoCandidates([], 'Photograph lookup unavailable.');
    setMessage('aircraftDetailStatus', `Public detail lookup unavailable: ${error.message}`, 'error');
  }
  await applyAirlabsRouteToDetails(flight);
}

async function updateAircraft() {
  try {
    const data = await jsonRequest('/api/aircraft.json');
    const body = el('aircraftRows');
    const aircraft = Array.isArray(data.aircraft) ? data.aircraft : [];
    const activeAircraft = aircraft
      .filter(isAircraftRecordActive)
      .sort((left, right) => {
        // PI_AIRCRAFT_ALPHABETICAL_SORT_V1:
        // Sort by displayed callsign. Aircraft without a callsign follow
        // callsign entries and are sorted by ICAO hex.
        const leftFlight = String(left && left.flight || '').trim().toUpperCase();
        const rightFlight = String(right && right.flight || '').trim().toUpperCase();

        if (leftFlight && rightFlight) {
          const byFlight = leftFlight.localeCompare(rightFlight, undefined, {
            numeric: true,
            sensitivity: 'base'
          });
          if (byFlight) return byFlight;
        } else if (leftFlight) {
          return -1;
        } else if (rightFlight) {
          return 1;
        }

        const leftHex = String(left && left.hex || '').trim().toUpperCase();
        const rightHex = String(right && right.hex || '').trim().toUpperCase();

        return leftHex.localeCompare(rightHex, undefined, {
          numeric: true,
          sensitivity: 'base'
        });
      });
    if (data && data.source_counts) {
      setText('messageCount', formattedNumber(Number(data.messages || 0)));
      setText('aircraftCount', formattedNumber(activeAircraft.length));
      setText('positionCount', formattedNumber(activeAircraft.filter(item => Number.isFinite(Number(item.lat)) && Number.isFinite(Number(item.lon))).length));
      const adsbCount = Number(data.source_counts.adsb_1090 || 0);
      const uatCount = Number(data.source_counts.uat_978 || 0);
      const enabled = data.source_enabled || {};
      setMessage('trafficSourceMessage', `Unified aircraft feed: 1090 ${enabled.adsb_1090 ? 'on' : 'off'} (${adsbCount}) · UAT ${enabled.uat_978 ? 'on' : 'off'} (${uatCount})`, (enabled.adsb_1090 || enabled.uat_978) ? 'good' : 'warning');
    }
    updateAircraftMap(activeAircraft);
    // ACTIVE_AIRCRAFT_LIST_ALL_RECORDS_V1:
    // Keep the scrollable list synchronized with every active map marker.
    const visibleAircraft = activeAircraft;
    body.replaceChildren();
    if (!visibleAircraft.length) {
      body.innerHTML = '<tr><td colspan="4" class="empty">No current aircraft records.</td></tr>';
      return;
    }
    for (const item of visibleAircraft) {
      const row = document.createElement('tr');
      row.className = 'active-plane-row';
      row.title = 'Click for aircraft and flight details';
      row.addEventListener('click', () => showAircraftDetails(item));
      const flight = item.flight ? item.flight.trim() : '';
      const sourceLabel = sourceLabelForAircraft(item);
      const ident = flight || String(item.hex || '').toUpperCase();
      const values = [sourceLabel ? `${ident} · ${sourceLabel}` : ident, item.alt_baro, item.gs, item.seen];
      for (const value of values) {
        const cell = document.createElement('td');
        cell.textContent = value == null ? '' : value;
        row.appendChild(cell);
      }
      body.appendChild(row);
    }
  } catch (error) {
    el('aircraftRows').innerHTML = `<tr><td colspan="8" class="empty">Aircraft data failed: ${error.message}</td></tr>`;
  }
}

async function loadAirlabsSettings() {
  try {
    const status = await jsonRequest('/api/diagnostics/airlabs/status');
    el('airlabsApiKey').value = '';
    setMessage(
      'airlabsMessage',
      status.configured
        ? `AirLabs route lookup configured (${status.key_hint}). Cached successful routes: ${status.route_cache_entries || 0}; expires after ${Math.round((status.cache_ttl_seconds || 7200) / 3600)} hours.`
        : 'AirLabs is not configured. Paste an API key and save it here.',
      status.configured ? 'good' : 'warning'
    );
  } catch (error) {
    setMessage('airlabsMessage', `Unable to load AirLabs status: ${error.message}`, 'error');
  }
}
async function saveAirlabsKey() {
  const apiKey = el('airlabsApiKey').value.trim();
  if (!apiKey) {
    setMessage('airlabsMessage', 'Paste the AirLabs API key before saving.', 'warning');
    return;
  }
  try {
    const result = await jsonRequest('/api/diagnostics/airlabs/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({api_key: apiKey})
    });
    if (!result.configured) throw new Error('Pi could not read back the saved AirLabs key.');
    el('airlabsApiKey').value = '';
    setMessage('airlabsMessage', `AirLabs key saved on the Pi (${result.key_hint}).`, 'good');
  } catch (error) {
    setMessage('airlabsMessage', `AirLabs key save failed: ${error.message}`, 'error');
  }
}
async function clearAirlabsKey() {
  try {
    await jsonRequest('/api/diagnostics/airlabs/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({clear: true})
    });
    el('airlabsApiKey').value = '';
    setMessage('airlabsMessage', 'AirLabs key removed from the Pi.', 'good');
  } catch (error) {
    setMessage('airlabsMessage', `AirLabs key clear failed: ${error.message}`, 'error');
  }
}
function formatAirlabsAirport(iata, icao) {
  if (iata && icao) return `${iata} (${icao})`;
  return iata || icao || 'Unavailable';
}
async function requestAirlabsDiagnosticRoute(flight) {
  return await jsonRequest(`/api/diagnostics/airlabs/route?flight=${encodeURIComponent(flight || '')}`);
}
async function clearAirlabsRouteCache() {
  try {
    await jsonRequest('/api/diagnostics/airlabs/cache/clear', {method: 'POST'});
    setMessage('airlabsMessage', 'AirLabs successful-route cache cleared. The next popup lookup will query AirLabs again.', 'good');
  } catch (error) {
    setMessage('airlabsMessage', `AirLabs cache clear failed: ${error.message}`, 'error');
  }
}

async function testAirlabsKey() {
  const flight = el('airlabsTestFlight').value.trim().toUpperCase();
  if (!flight) {
    setMessage('airlabsMessage', 'Enter an active airline callsign such as UAL1234.', 'warning');
    return;
  }
  try {
    setMessage('airlabsMessage', `Testing AirLabs route lookup for ${flight}…`, 'warning');
    const result = await requestAirlabsDiagnosticRoute(flight);
    if (result.matched) {
      setMessage(
        'airlabsMessage',
        `${flight}: ${formatAirlabsAirport(result.departure_iata, result.departure_icao)} → ${formatAirlabsAirport(result.arrival_iata, result.arrival_icao)}.${result.cache_hit ? ' Cached result.' : ' Fresh AirLabs result cached for reuse.'}`,
        'good'
      );
    } else {
      setMessage('airlabsMessage', result.message || `No AirLabs route matched ${flight}.`, 'warning');
    }
  } catch (error) {
    setMessage('airlabsMessage', `Route lookup test failed: ${error.message}`, 'error');
  }
}

async function saveAirbandRadius() {
  const radiusMiles = Number(el('locationRadius').value);
  if (!Number.isFinite(radiusMiles) || radiusMiles <= 0 || radiusMiles > 500) {
    setMessage('airbandRadiusMessage', 'Enter an Airband radius greater than 0 and no more than 500 miles.', 'error');
    return;
  }

  const originalAirband = await readAirbandStatus();
  const restartScan = Boolean(originalAirband.airband_scan_running) && airbandBackgroundWanted && !liveListening;

  try {
    if (restartScan) {
      await showBusyAndPaint(
        'Applying Airband scan radius…',
        `Stopping background scan before rebuilding channels within ${radiusMiles.toFixed(1)} miles.`
      );
      airbandRestartSuspended = true;
      const stopped = await stopAirbandBackground(false, false);
      if (!stopped) throw new Error('Airband scanner did not release the receiver.');
    }

    const result = await jsonRequest('/api/settings/airband-radius', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({airband_radius_miles: radiusMiles})
    });
    renderLocation(result.receiver_location);
    setMessage(
      'airbandRadiusMessage',
      `Airband scan radius set to ${Number(result.receiver_location.airband_radius_miles).toFixed(1)} miles. Saved NOAA selection preserved.`,
      'good'
    );

    if (restartScan) {
      airbandRestartSuspended = false;
      await startAirbandBackground(false);
      setMessage(
        'airbandRadiusMessage',
        `Airband scan radius set to ${Number(result.receiver_location.airband_radius_miles).toFixed(1)} miles; background scan restarted with nearby channels only.`,
        'good'
      );
    }
  } catch (error) {
    setMessage('airbandRadiusMessage', `Airband radius update failed: ${error.message}`, 'error');
    if (restartScan && airbandBackgroundWanted && !liveListening) {
      airbandRestartSuspended = false;
      await startAirbandBackground(false);
    }
  } finally {
    airbandRestartSuspended = false;
    hideBusy();
    await refreshOperationMenu();
  }
}

async function saveLocation() {
  try {
    const payload = {
      name: el('locationName').value,
      latitude: el('locationLatitude').value,
      longitude: el('locationLongitude').value,
      airband_radius_miles: el('locationRadius').value
    };
    const result = await jsonRequest('/api/settings/receiver', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    delete el('locationName').dataset.edited;
    renderLocation(result.receiver_location);
  } catch (error) {
    setMessage('locationMessage', `Location save failed: ${error.message}`, 'error');
  }
}

async function captureNoaa() {
  setMessage('audioMessage', 'Capturing 10 seconds of NOAA audio while ADS-B continues…', 'warning');
  try {
    const response = await fetch(`/api/noaa/capture.wav?seconds=10&request=${Date.now()}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    if (audioObjectUrl) URL.revokeObjectURL(audioObjectUrl);
    audioObjectUrl = URL.createObjectURL(blob);
    el('audioPlayer').src = audioObjectUrl;
    el('audioPlayer').load();
    setMessage('audioMessage', 'NOAA capture complete. Press Play to listen.', 'good');
  } catch (error) {
    setMessage('audioMessage', `NOAA capture failed: ${error.message}`, 'error');
  }
}

async function pumpLiveAudio() {
  if (!liveListening || !liveAudioContext) return;
  try {
    if (liveAudioContext.state !== 'running') await liveAudioContext.resume();
    if (liveAudioContext.state !== 'running') {
      throw new Error(`Shared scanner audio output is ${liveAudioContext.state}; click Reconnect NOAA Audio.`);
    }
    const response = await fetch(`/api/noaa/live/audio.wav?from=${liveNextCursor}&samples=12000&request=${Date.now()}`, {cache: 'no-store'});
    if (response.status === 204) {
      livePumpTimer = window.setTimeout(pumpLiveAudio, 120);
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const sourceSamples = Number(response.headers.get('X-Source-Samples') || 0);
    const data = await response.arrayBuffer();
    const decoded = await liveAudioContext.decodeAudioData(data.slice(0));
    let energy = 0;
    let sampleCount = 0;
    for (let channel = 0; channel < decoded.numberOfChannels; channel += 1) {
      const samples = decoded.getChannelData(channel);
      const stride = Math.max(1, Math.floor(samples.length / 4096));
      for (let index = 0; index < samples.length; index += stride) {
        energy += samples[index] * samples[index];
        sampleCount += 1;
      }
    }
    noaaPlaybackLastChunkRms = sampleCount ? Math.sqrt(energy / sampleCount) : 0;
    const source = liveAudioContext.createBufferSource();
    source.buffer = decoded;
    source.connect(liveAudioContext.destination);
    const startAt = Math.max(liveAudioContext.currentTime + 0.04, liveNextPlayTime);
    source.start(startAt);
    liveNextPlayTime = startAt + decoded.duration;
    liveNextCursor += sourceSamples;
    noaaPlaybackChunksScheduled += 1;
    if (noaaPlaybackChunksScheduled === 1) {
      setMessage('audioMessage', `NOAA live audio playing through shared scanner output · stream RMS ${noaaPlaybackLastChunkRms.toFixed(4)}.`, 'good');
    }
    const bufferedSeconds = liveNextPlayTime - liveAudioContext.currentTime;
    livePumpTimer = window.setTimeout(pumpLiveAudio, bufferedSeconds > 1.4 ? 250 : 20);
  } catch (error) {
    liveListening = false;
    setMessage('audioMessage', `NOAA shared-output playback failed: ${error.message}. Click Reconnect NOAA Audio.`, 'error');
    await refreshOperationMenu();
  }
}

async function prepareAirbandAudio() {
  if (!airbandAudioContext) airbandAudioContext = new (window.AudioContext || window.webkitAudioContext)();
  await airbandAudioContext.resume();
  airbandAudioAuthorized = true;
}
function stopAirbandPlayback() {
  if (airbandPumpTimer) {
    window.clearTimeout(airbandPumpTimer);
    airbandPumpTimer = null;
  }
  airbandAudioCursor = 0;
  airbandNextPlayTime = airbandAudioContext ? airbandAudioContext.currentTime : 0;
  airbandPlayingHoldId = null;
}
async function pumpAirbandAudio(holdId) {
  if (!airbandAudioAuthorized || !airbandAudioContext || airbandPlayingHoldId !== holdId) return;
  try {
    if (airbandAudioContext.state !== 'running') await airbandAudioContext.resume();
    const response = await fetch(`/api/airband/scan/live/audio.wav?from=${airbandAudioCursor}&request=${Date.now()}`, {cache: 'no-store'});
    if (response.status === 204) {
      airbandPumpTimer = window.setTimeout(() => pumpAirbandAudio(holdId), 60);
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const sourceSamples = Number(response.headers.get('X-Source-Samples') || 0);
    airbandLastPlaybackMuted = response.headers.get('X-Airband-Squelch-Muted') === '1';
    const headerRms = Number(response.headers.get('X-Airband-Chunk-RMS'));
    airbandLastPlaybackRms = Number.isFinite(headerRms) ? headerRms : airbandLastPlaybackRms;
    const data = await response.arrayBuffer();
    const decoded = await airbandAudioContext.decodeAudioData(data.slice(0));
    const source = airbandAudioContext.createBufferSource();
    source.buffer = decoded;
    source.connect(airbandAudioContext.destination);
    const startAt = Math.max(airbandAudioContext.currentTime + 0.04, airbandNextPlayTime);
    source.start(startAt);
    airbandNextPlayTime = startAt + decoded.duration;
    airbandAudioCursor += Math.max(1, sourceSamples);
    const bufferedSeconds = airbandNextPlayTime - airbandAudioContext.currentTime;
    airbandPumpTimer = window.setTimeout(() => pumpAirbandAudio(holdId), bufferedSeconds > 1.4 ? 180 : 20);
  } catch (error) {
    setMessage('operationsMessage', `Airband live audio failed: ${error.message}`, 'error');
    stopAirbandPlayback();
  }
}

function renderBlockedAirbandFrequencies(status) {
  const target = el('airbandBlockedMessage');
  if (!target) return;
  const blocked = Array.isArray(status.airband_blocked_frequencies_hz) ? status.airband_blocked_frequencies_hz : [];
  target.textContent = blocked.length
    ? `Blocked: ${blocked.map(value => (Number(value) / 1000000).toFixed(3) + ' MHz').join(', ')}`
    : 'No frequencies blocked.';
}
function airbandSquelchDisplayLabel(status) {
  const squelch = Number(status && status.airband_playback_squelch_rms || 0);
  if (!Number.isFinite(squelch) || squelch <= 0) return 'off';
  const muted = Boolean(status && (
    status.airband_playback_squelch_muted ||
    status.airband_squelch_state === 'closed'
  ));
  const value = squelch.toFixed(0);
  return muted ? `${value} muted` : value;
}

function formatAirbandHoldScannerMessage(status) {
  const held = status.airband_hold_channel || status.airband_current_channel || {};
  const freq = Number.isFinite(Number(held.frequency_mhz))
    ? `${Number(held.frequency_mhz).toFixed(3)} MHz`
    : 'held channel';
  const state = status.airband_squelch_state || (status.airband_playback_squelch_muted ? 'closed' : 'open');
  const quiet = Number(status.airband_hold_quiet_seconds || 0);
  const remaining = status.airband_hold_release_remaining_seconds == null
    ? Math.max(0, 7 - quiet)
    : Number(status.airband_hold_release_remaining_seconds);
  const rms = status.airband_hold_rms_sample == null
    ? (airbandLastPlaybackRms == null ? '—' : Number(airbandLastPlaybackRms).toFixed(1))
    : Number(status.airband_hold_rms_sample).toFixed(1);
  const source = status.airband_open_squelch_static ? ' · open static' : '';
  const timer = state === 'closed'
    ? `quiet ${quiet.toFixed(1)}/7.0s · resume in ${remaining.toFixed(1)}s`
    : 'quiet 0.0/7.0s · timer reset';
  return `HOLD ${freq} AM · ${state.toUpperCase()} · squelch ${airbandSquelchDisplayLabel(status)} · RMS ${rms}${source} · ${timer}`;
}

function syncAirbandHoldAudio(status) {
  renderBlockedAirbandFrequencies(status);
  const holding = Boolean(status.airband_hold_active);
  el('airbandSkipHeld').disabled = !holding;
  el('airbandBlockHeld').disabled = !holding;
  if (!holding) {
    if (airbandPlayingHoldId !== null) stopAirbandPlayback();
    return;
  }

  const message = formatAirbandHoldScannerMessage(status);
  setMessage(
    'operationsMessage',
    message,
    status.airband_squelch_state === 'closed' || status.airband_playback_squelch_muted ? 'warning' : 'good'
  );
  setMessage(
    'airbandScanStatus',
    message,
    status.airband_squelch_state === 'closed' || status.airband_playback_squelch_muted ? 'warning' : 'good'
  );

  if (airbandAudioAuthorized && airbandAudioContext && airbandPlayingHoldId !== status.airband_hold_id) {
    stopAirbandPlayback();
    airbandPlayingHoldId = status.airband_hold_id;
    airbandAudioCursor = 0;
    airbandNextPlayTime = airbandAudioContext.currentTime + 0.08;
    pumpAirbandAudio(airbandPlayingHoldId);
  }
}

async function skipHeldAirbandChannel() {
  try {
    const result = await jsonRequest('/api/airband/scan/activity/skip', {method: 'POST'});
    stopAirbandPlayback();
    renderBlockedAirbandFrequencies(result);
    setMessage('operationsMessage', 'Held Airband channel skipped. Scanning resumed.', 'good');
  } catch (error) {
    setMessage('operationsMessage', `Skip failed: ${error.message}`, 'error');
  }
}
async function blockHeldAirbandChannel() {
  try {
    const result = await jsonRequest('/api/airband/scan/activity/block', {method: 'POST'});
    stopAirbandPlayback();
    renderBlockedAirbandFrequencies(result);
    setMessage('operationsMessage', `Blocked ${(Number(result.frequency_hz) / 1000000).toFixed(3)} MHz. Scanning resumed.`, 'good');
  } catch (error) {
    setMessage('operationsMessage', `Block failed: ${error.message}`, 'error');
  }
}
async function clearBlockedAirbandFrequencies() {
  try {
    const result = await jsonRequest('/api/airband/scan/blocks/clear', {method: 'POST'});
    renderBlockedAirbandFrequencies(result);
    setMessage('airbandBlockedMessage', 'Blocked frequency list cleared.', 'good');
  } catch (error) {
    setMessage('airbandBlockedMessage', `Unable to clear blocks: ${error.message}`, 'error');
  }
}

async function rescanSavedNoaaChannel() {
  if (operationTransitionActive) return;
  operationTransitionActive = true;
  setOperationButtonsDisabled(true);
  airbandRestartSuspended = true;
  closeMenu();

  try {
    await prepareNoaaAudioForStart(true);
    const status = requireObjectResponse(await jsonRequest('/api/status'), 'Receiver status');
    const airband = await readAirbandStatus();

    await showBusyAndPaint(
      'Rescanning NOAA Weather channels…',
      'Clearing the saved local channel and running one fast spectrum search across all seven NOAA frequencies.'
    );

    if (status.live_audio_running || liveListening) {
      await stopLive(true);
    }
    if (airband.airband_scan_running) {
      const released = await stopAirbandBackground(true, false);
      if (!released) throw new Error('Airband did not release the shared receiver.');
    }

    await autoNoaa(true);
    await hideBusyAfterMinimum(550);
    setMessage('locationMessage', 'NOAA local channel rescanned and saved for the current receiver location.', 'good');
  } catch (error) {
    hideBusy();
    airbandRestartSuspended = false;
    airbandBackgroundWanted = false;
    airbandPausedForNoaa = false;
    await releaseUnusedPreparedNoaaAudio();
    setMessage('locationMessage', `NOAA rescan failed: ${error.message}. Airband remains stopped.`, 'error');
  } finally {
    operationTransitionActive = false;
    setOperationButtonsDisabled(false);
    await refreshOperationMenu();
  }
}


function makeNoaaSilentWavUrl() {
  const sampleRate = 8000;
  const sampleCount = sampleRate;
  const buffer = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(buffer);
  const putText = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index));
  };
  putText(0, 'RIFF');
  view.setUint32(4, 36 + sampleCount * 2, true);
  putText(8, 'WAVE');
  putText(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  putText(36, 'data');
  view.setUint32(40, sampleCount * 2, true);
  return URL.createObjectURL(new Blob([buffer], {type: 'audio/wav'}));
}
function rmsFromNoaaWavArrayBuffer(buffer) {
  if (!buffer || buffer.byteLength <= 44) return 0;
  const view = new DataView(buffer);
  let sum = 0;
  let count = 0;
  for (let offset = 44; offset + 1 < buffer.byteLength; offset += 8) {
    const value = view.getInt16(offset, true) / 32768;
    sum += value * value;
    count += 1;
  }
  return count ? Math.sqrt(sum / count) : 0;
}
function resetNoaaHtmlAudioOutput() {
  noaaHtmlAudioGeneration += 1;
  noaaHtmlAudioQueue.forEach(item => URL.revokeObjectURL(item.url));
  noaaHtmlAudioQueue = [];
  noaaHtmlAudioFetchBusy = false;
  noaaHtmlAudioRealPlaybackStarted = false;
  if (noaaHtmlAudioElement) {
    noaaHtmlAudioElement.onended = null;
    noaaHtmlAudioElement.onerror = null;
    noaaHtmlAudioElement.pause();
    noaaHtmlAudioElement.removeAttribute('src');
    noaaHtmlAudioElement.load();
  }
  if (noaaHtmlAudioCurrentUrl) URL.revokeObjectURL(noaaHtmlAudioCurrentUrl);
  if (noaaHtmlAudioPrimerUrl) URL.revokeObjectURL(noaaHtmlAudioPrimerUrl);
  noaaHtmlAudioCurrentUrl = null;
  noaaHtmlAudioPrimerUrl = null;
  noaaHtmlAudioElement = null;
}
async function primeNoaaHtmlAudioOutput() {
  /* Step 76: preserve authorized NOAA HTML player during restart scan */
  if (noaaHtmlAudioElement && noaaHtmlAudioPrimerUrl && !noaaHtmlAudioRealPlaybackStarted) {
    noaaHtmlAudioElement.onended = null;
    noaaHtmlAudioElement.onerror = null;
    noaaHtmlAudioElement.volume = 0;
    noaaHtmlAudioElement.loop = true;
    noaaHtmlAudioElement.src = noaaHtmlAudioPrimerUrl;
    if (noaaHtmlAudioElement.paused) await noaaHtmlAudioElement.play();
    return;
  }
  resetNoaaHtmlAudioOutput();
  noaaHtmlAudioElement = new Audio();
  noaaHtmlAudioElement.preload = 'auto';
  noaaHtmlAudioElement.playsInline = true;
  noaaHtmlAudioElement.volume = 0;
  noaaHtmlAudioElement.loop = true;
  noaaHtmlAudioPrimerUrl = makeNoaaSilentWavUrl();
  noaaHtmlAudioElement.src = noaaHtmlAudioPrimerUrl;
  await noaaHtmlAudioElement.play();
}
async function playNextNoaaHtmlAudioChunk() {
  if (!liveListening || !noaaHtmlAudioElement || !noaaHtmlAudioQueue.length) return;
  const next = noaaHtmlAudioQueue.shift();
  if (noaaHtmlAudioCurrentUrl) URL.revokeObjectURL(noaaHtmlAudioCurrentUrl);
  noaaHtmlAudioCurrentUrl = next.url;
  noaaHtmlAudioElement.loop = false;
  noaaHtmlAudioElement.volume = 1;
  noaaHtmlAudioElement.src = next.url;
  noaaHtmlAudioElement.onended = () => {
    if (liveListening && noaaHtmlAudioQueue.length) {
      playNextNoaaHtmlAudioChunk().catch(error => {
        setMessage('audioMessage', `NOAA HTML playback failed: ${error.message}`, 'error');
      });
    }
  };
  await noaaHtmlAudioElement.play();
  noaaPlaybackChunksScheduled += 1;
  if (!noaaHtmlAudioRealPlaybackStarted) {
    noaaHtmlAudioRealPlaybackStarted = true;
    setMessage(
      'audioMessage',
      `NOAA live audio playing through HTML player · stream RMS ${next.rms.toFixed(4)}.`,
      'good'
    );
  }
}
async function fillNoaaHtmlAudioQueue() {
  if (!liveListening || !noaaHtmlAudioElement || noaaHtmlAudioFetchBusy) return;
  noaaHtmlAudioFetchBusy = true;
  const generation = noaaHtmlAudioGeneration;
  try {
    while (liveListening && generation === noaaHtmlAudioGeneration && noaaHtmlAudioQueue.length < 4) {
      const response = await fetch(`/api/noaa/live/audio.wav?from=${liveNextCursor}&samples=12000&request=${Date.now()}`, {cache: 'no-store'});
      if (response.status === 204) break;
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const sourceSamples = Number(response.headers.get('X-Source-Samples') || 0);
      const data = await response.arrayBuffer();
      noaaPlaybackLastChunkRms = rmsFromNoaaWavArrayBuffer(data);
      noaaHtmlAudioQueue.push({
        url: URL.createObjectURL(new Blob([data], {type: 'audio/wav'})),
        rms: noaaPlaybackLastChunkRms
      });
      liveNextCursor += sourceSamples;
    }
    if (!noaaHtmlAudioRealPlaybackStarted && noaaHtmlAudioQueue.length >= 2) {
      await playNextNoaaHtmlAudioChunk();
    } else if (noaaHtmlAudioRealPlaybackStarted && noaaHtmlAudioElement.paused && noaaHtmlAudioQueue.length) {
      await playNextNoaaHtmlAudioChunk();
    }
  } finally {
    noaaHtmlAudioFetchBusy = false;
  }
}

async function prepareNoaaAudioForStart(forceFreshContext = false) {
  /* Step 77: NOAA uses the proven shared Airband scanner audio output */
  // Live testing proved that Airband's browser audio output is audible while
  // separate NOAA outputs are silent. Arm that same output on this NOAA click.
  if (typeof resetNoaaHtmlAudioOutput === 'function') resetNoaaHtmlAudioOutput();
  await prepareAirbandAudio();
  liveAudioContext = airbandAudioContext;
  noaaAudioUsesAirbandContext = true;
  if (!liveAudioContext) throw new Error('Shared scanner audio output could not be created.');
  await liveAudioContext.resume();
  if (liveAudioContext.state !== 'running') {
    throw new Error(`Shared scanner audio output is ${liveAudioContext.state}. Click Reconnect NOAA Audio.`);
  }
  const primer = liveAudioContext.createBuffer(1, 1, liveAudioContext.sampleRate);
  const primerSource = liveAudioContext.createBufferSource();
  primerSource.buffer = primer;
  primerSource.connect(liveAudioContext.destination);
  primerSource.start();
  noaaAudioPreparedForStart = true;
  noaaPlaybackLastChunkRms = null;
  noaaPlaybackChunksScheduled = 0;
}

async function releaseUnusedPreparedNoaaAudio() {
  if (typeof resetNoaaHtmlAudioOutput === 'function') resetNoaaHtmlAudioOutput();
  noaaAudioPreparedForStart = false;
}

async function startLive() {
  try {
    await prepareNoaaAudioForStart(true);
    await jsonRequest('/api/noaa/live/start', {method: 'POST'});
    liveListening = true;
    noaaAudioPreparedForStart = false;
    noaaPlaybackChunksScheduled = 0;
    liveNextCursor = 0;
    liveNextPlayTime = liveAudioContext.currentTime + 0.20;
    setMessage('audioMessage', 'Live NOAA listening active. ADS-B continues.', 'good');
    await updateStatus();
    pumpLiveAudio();
  } catch (error) {
    await releaseUnusedPreparedNoaaAudio();
    setMessage('audioMessage', `Unable to start NOAA: ${error.message}`, 'error');
  }
}

async function stopLive(preserveAudioContext = false) {
  liveListening = false;
  noaaPlaybackChunksScheduled = 0;
  noaaPlaybackLastChunkRms = null;
  if (livePumpTimer) {
    window.clearTimeout(livePumpTimer);
    livePumpTimer = null;
  }
  if (typeof resetNoaaHtmlAudioOutput === 'function') resetNoaaHtmlAudioOutput();
  try { await jsonRequest('/api/noaa/live/stop', {method: 'POST'}); } catch (_) {}
  // Keep the shared scanner output available for the next explicit NOAA or
  // Airband action; no queued NOAA chunks remain after liveListening=false.
  liveAudioContext = airbandAudioContext || null;
  noaaAudioUsesAirbandContext = Boolean(liveAudioContext);
  noaaAudioPreparedForStart = false;
  setMessage('audioMessage', 'NOAA listening stopped.', '');
  await updateStatus();
}

async function attachExistingNoaaLive(status) {
  await prepareNoaaAudioForStart();
  liveListening = true;
  noaaAudioPreparedForStart = false;
  noaaPlaybackChunksScheduled = 0;
  liveNextCursor = 0;
  liveNextPlayTime = liveAudioContext.currentTime + 0.08;
  const selected = (Number(status.noaa_frequency_hz) / 1000000).toFixed(3);
  setMessage('audioMessage', `Reconnecting browser audio to NOAA ${selected} MHz…`, 'warning');
  pumpLiveAudio();
}

async function autoNoaa(forceRescan = false) {
  await prepareNoaaAudioForStart();
  const noaaEndpoint = forceRescan ? '/api/noaa/auto/rescan' : '/api/noaa/auto/start';
  setMessage(
    'surveyResult',
    forceRescan ? 'Rescanning NOAA channels and validating clear weather audio…' : 'Starting the saved NOAA channel, or rescanning if the receiver location changed…',
    'warning'
  );

  try {
    const status = await jsonRequest(noaaEndpoint, {method: 'POST'});
    liveListening = true;
    noaaAudioPreparedForStart = false;
    noaaPlaybackChunksScheduled = 0;
    liveNextCursor = 0;
    liveNextPlayTime = liveAudioContext.currentTime + 0.20;
    const selected = (Number(status.noaa_frequency_hz) / 1000000).toFixed(3);


    const carrierEvidence = status.survey && status.survey.selected_carrier_margin_db != null
      ? ` · carrier +${Number(status.survey.selected_carrier_margin_db).toFixed(1)} dB`
      : '';
    const audioEvidence = status.survey && status.survey.selected_audio_quality_db != null
      ? ` · audio quality ${Number(status.survey.selected_audio_quality_db).toFixed(1)} dB`
      : '';
    const savedChannelEvidence = status.saved_channel_reused ? ' · saved channel reused' : '';
    setMessage('surveyResult', `Selected ${selected} MHz${carrierEvidence}${audioEvidence} and started live listening.`, 'good');
    setMessage('audioMessage', `NOAA listening active on ${selected} MHz.`, 'good');
    pumpLiveAudio();
    await updateStatus();
    return status;
  } catch (error) {
    await releaseUnusedPreparedNoaaAudio();
    setMessage('surveyResult', `NOAA start failed: ${error.message}`, 'error');
    throw error;
  }
}

async function loadAirbandChannels() {
  try {
    const result = await jsonRequest('/api/airband/channels');
    const rows = el('airbandRows');
    rows.replaceChildren();
    setMessage('airbandListMessage',
      `Loaded ${result.channel_count} unique AM frequencies within ${result.radius_miles} miles; ${result.duplicate_records_removed || 0} duplicate records removed.`,
      'good');
    if (!result.channels.length) {
      rows.innerHTML = '<tr><td colspan="5" class="empty">No channels found within configured radius.</td></tr>';
      return;
    }
    for (const channel of result.channels.slice(0, 40)) {
      const row = document.createElement('tr');
      const values = [
        Number(channel.frequency_mhz).toFixed(3),
        channel.airport_id || channel.airport_name || '',
        channel.use || '',
        channel.distance_miles
      ];
      for (const value of values) {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.appendChild(cell);
      }
      const action = document.createElement('td');
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Test 10 sec';
      button.addEventListener('click', () => testAirbandCapture(channel));
      action.appendChild(button);
      row.appendChild(action);
      rows.appendChild(row);
    }
  } catch (error) {
    setMessage('airbandListMessage', `Airband list failed: ${error.message}`, 'error');
  }
}

async function testAirbandCapture(channel) {
  setMessage('airbandAudioMessage', `Capturing ${Number(channel.frequency_mhz).toFixed(3)} MHz AM diagnostic audio…`, 'warning');
  try {
    const response = await fetch(`/api/airband/capture.wav?frequency_hz=${channel.frequency_hz}&seconds=10&request=${Date.now()}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    el('airbandPlayer').src = url;
    el('airbandPlayer').load();
    setMessage('airbandAudioMessage', 'AM diagnostic capture complete. Live RF detection remains unvalidated.', 'good');
  } catch (error) {
    setMessage('airbandAudioMessage', `AM diagnostic failed: ${error.message}`, 'error');
  }
}

async function startExperimentalScan() {
  try {
    const scope = el('airbandScanScope').value;
    const result = await jsonRequest(`/api/airband/scan/activity/start?scope=${encodeURIComponent(scope)}`, {method: 'POST'});
    el('activityScanStart').disabled = true;
    el('activityScanStop').disabled = false;
    setMessage('airbandScanStatus',
      `Experimental scan started: ${result.channel_count} channels (${result.scan_scope || scope}). RF validation deferred.`,
      'warning');
    pollExperimentalScan();
  } catch (error) {
    setMessage('airbandScanStatus', `Experimental scan failed: ${error.message}`, 'error');
  }
}

async function stopExperimentalScan() {
  try { await jsonRequest('/api/airband/scan/activity/stop', {method: 'POST'}); } catch (_) {}
  el('activityScanStart').disabled = false;
  el('activityScanStop').disabled = true;
  setMessage('airbandScanStatus', 'Experimental RF scan stopped.', 'warning');
}

async function pollExperimentalScan() {
  try {
    const status = requireObjectResponse(await jsonRequest('/api/airband/scan/status'), 'Airband status');
    syncAirbandHoldAudio(status);
    if (!status.airband_scan_running) {
      el('activityScanStart').disabled = false;
      el('activityScanStop').disabled = true;
      refreshOperationMenu();
      return;
    }
    const channel = status.airband_current_channel;
    if (status.airband_hold_active) {
      setMessage(
        'airbandScanStatus',
        formatAirbandHoldScannerMessage(status),
        status.airband_squelch_state === 'closed' ? 'warning' : 'good'
      );
    } else if (status.airband_search_mode === 'fast_spectrum') {
      const bestCarrier = status.airband_spectrum_best_frequency_hz == null
        ? '—'
        : `${(Number(status.airband_spectrum_best_frequency_hz) / 1000000).toFixed(3)} MHz`;
      setMessage(
        'airbandScanStatus',
        `FAST 120–130 MHz: sweeps ${status.airband_spectrum_sweeps || 0}; ` +
        `carrier candidates ${status.airband_spectrum_candidate_count || 0}; ` +
        `best ${bestCarrier} / +${status.airband_spectrum_best_margin_db == null ? '—' : Number(status.airband_spectrum_best_margin_db).toFixed(1)} dB; ` +
        `AM validations ${status.airband_spectrum_validation_count || 0}.`,
        'warning'
      );
    } else {
      setMessage(
        'airbandScanStatus',
        `Scanner (${status.airband_scan_scope || 'priority'}): samples ${status.airband_channels_scanned || 0}` +
        (channel ? `; ${Number(channel.frequency_mhz).toFixed(3)} MHz` : '') +
        `; RMS ${status.airband_last_measurement_dbfs == null ? '—' : status.airband_last_measurement_dbfs}.`,
        'warning'
      );
    }
    window.setTimeout(pollExperimentalScan, 300);
  } catch (error) {
    setMessage('airbandScanStatus', `Airband scanner status failed: ${error.message}`, 'error');
  }
}

async function startAirbandTest() {
  try {
    await jsonRequest('/api/airband/test/start', {method: 'POST'});
    airbandTestPlayedEventId = 0;
    setMessage('airbandTestStatus', 'SIMULATED: Test scanner starting.', 'warning');
    pollAirbandTest();
  } catch (error) {
    setMessage('airbandTestStatus', `SIMULATED test failed: ${error.message}`, 'error');
  }
}

async function airbandTestCommand(command) {
  try {
    await jsonRequest(`/api/airband/test/${command}`, {method: 'POST'});
    pollAirbandTest();
  } catch (error) {
    setMessage('airbandTestStatus', `SIMULATED command failed: ${error.message}`, 'error');
  }
}

async function pollAirbandTest() {
  try {
    const status = await jsonRequest('/api/airband/test/status');
    const running = Boolean(status.airband_test_running);
    const state = status.airband_test_state || 'idle';
    el('airbandTestStart').disabled = running;
    el('airbandTestStop').disabled = !running;
    el('airbandTestHold').disabled = !running || state === 'held';
    el('airbandTestSkip').disabled = !running;
    el('airbandTestResume').disabled = !running || state !== 'held';

    let message = status.airband_test_message || 'SIMULATED: Test scanner idle.';
    if (status.airband_test_silence_remaining != null) {
      message += ` Silence remaining ${status.airband_test_silence_remaining} seconds.`;
    }
    setMessage('airbandTestStatus', message,
      (state === 'listening_simulated_activity' || state === 'held') ? 'good' : 'warning');

    if (state === 'listening_simulated_activity' && status.airband_test_event_id !== airbandTestPlayedEventId) {
      airbandTestPlayedEventId = status.airband_test_event_id;
      el('airbandTestPlayer').src = `/api/airband/test/audio.wav?event=${airbandTestPlayedEventId}`;
      el('airbandTestPlayer').load();
      try { await el('airbandTestPlayer').play(); } catch (_) {}
    }
    if (running) window.setTimeout(pollAirbandTest, 300);
  } catch (error) {
    setMessage('airbandTestStatus', `SIMULATED status failed: ${error.message}`, 'error');
  }
}

let airbandBackgroundWanted = false;
let airbandPausedForNoaa = false;
let airbandRestartSuspended = false;
let operationTransitionActive = false;
let operationsRefreshTimer = null;
let busyStartedAt = 0;
let busyElapsedTimer = null;

function showBusy(title, detail = '') {
  const overlay = el('busyOverlay');
  if (!overlay) return;
  el('busyTitle').textContent = title;
  el('busyDetail').textContent = detail || 'Preparing the shared audio receiver.';
  busyStartedAt = Date.now();
  if (el('busyElapsed')) el('busyElapsed').textContent = 'Elapsed: 0 seconds';
  overlay.classList.add('open');
  if (busyElapsedTimer) window.clearInterval(busyElapsedTimer);
  busyElapsedTimer = window.setInterval(() => {
    if (el('busyElapsed')) {
      const seconds = Math.floor((Date.now() - busyStartedAt) / 1000);
      el('busyElapsed').textContent = `Elapsed: ${seconds} second${seconds === 1 ? '' : 's'}`;
    }
  }, 250);
}
function updateBusy(title, detail = '') {
  if (el('busyTitle')) el('busyTitle').textContent = title;
  if (el('busyDetail')) el('busyDetail').textContent = detail;
}
function nextPaintFrame() {
  return new Promise(resolve => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
  });
}
async function showBusyAndPaint(title, detail = '') {
  showBusy(title, detail);
  await nextPaintFrame();
}
async function hideBusyAfterMinimum(milliseconds = 500) {
  const remaining = milliseconds - (Date.now() - busyStartedAt);
  if (remaining > 0) await new Promise(resolve => window.setTimeout(resolve, remaining));
  hideBusy();
}
function hideBusy() {
  if (busyElapsedTimer) {
    window.clearInterval(busyElapsedTimer);
    busyElapsedTimer = null;
  }
  const overlay = el('busyOverlay');
  if (overlay) overlay.classList.remove('open');
}
function setOperationButtonsDisabled(disabled) {
  el('noaaMenuToggle').disabled = disabled;
  el('airbandMenuToggle').disabled = disabled;
}
function delay(milliseconds) {
  return new Promise(resolve => window.setTimeout(resolve, milliseconds));
}
function openMenu() {
  el('appMenu').classList.add('open');
  el('menuBackdrop').classList.add('open');
  el('menuToggle').setAttribute('aria-expanded', 'true');
}
function closeMenu() {
  el('appMenu').classList.remove('open');
  el('menuBackdrop').classList.remove('open');
  el('menuToggle').setAttribute('aria-expanded', 'false');
  // V0.2 traffic-source controls: resume refresh after the operator closes
  // the drawer so checkboxes are not fighting the 2-second aircraft/status polls.
  window.setTimeout(() => {
    try { updateStatus(); } catch (_) {}
    try { updateAircraft(); } catch (_) {}
    try { refreshOperationMenu(); } catch (_) {}
    try { if (typeof loadTrafficSourceSettings === 'function') loadTrafficSourceSettings(); } catch (_) {}
  }, 80);
}
function toggleMenu() {
  if (el('appMenu').classList.contains('open')) closeMenu(); else openMenu();
}
async function readAirbandStatus() {
  try {
    return requireObjectResponse(await jsonRequest('/api/airband/scan/status'), 'Airband status');
  } catch (_) {
    return {};
  }
}
async function waitForAirbandStopped(timeoutMilliseconds = 15000) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    const status = await readAirbandStatus();
    if (!status.airband_scan_running) return true;
    updateBusy(
      'Stopping Airband background scan…',
      'Waiting for RTL-SDR audio receiver 00000162 to be released for NOAA Weather.'
    );
    await delay(250);
  }
  return false;
}
async function waitForNoaaRunning(timeoutMilliseconds = 12000) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    const status = requireObjectResponse(await jsonRequest('/api/status'), 'Receiver status');
    if (status.live_audio_running) return status;
    updateBusy(
      'Starting NOAA Weather audio…',
      'The local NOAA channel has been selected. Waiting for live audio buffering to begin.'
    );
    await delay(250);
  }
  return null;
}

function updateAirbandTuningDetail(airband, noaaActive) {
  const target = el('airbandTuningDetail');
  if (!target) return;

  target.className = '';
  if (noaaActive) {
    target.textContent = 'Airband Tuning: paused while NOAA is active';
    target.className = 'tuning-paused';
    return;
  }

  if (!airband || !airband.airband_scan_running) {
    target.textContent = 'Airband Tuning: stopped';
    return;
  }

  const channel = airband.airband_current_channel;
  if (channel && Number.isFinite(Number(channel.frequency_mhz))) {
    const description = channel.use ? ` · ${channel.use}` : '';
    target.textContent = `Airband Tuning: ${Number(channel.frequency_mhz).toFixed(3)} MHz AM${description}`;
    target.className = 'tuning-active';
  } else {
    target.textContent = 'Airband Tuning: scanning…';
    target.className = 'tuning-active';
  }
}

// AIRBAND_NORMAL_SCANNER_SQUELCH_UI_V2: UI displays squelch OPEN/CLOSED state, quiet timer, and remaining release time.
function formatAirbandHoldScannerMessage(status) {
  const held = status.airband_hold_channel || status.airband_current_channel || {};
  const freq = Number.isFinite(Number(held.frequency_mhz)) ? `${Number(held.frequency_mhz).toFixed(3)} MHz` : 'held channel';
  const squelch = Number(status.airband_playback_squelch_rms || 0);
  const squelchLabel = squelch <= 0 ? 'squelch off/open' : `squelch ${squelch.toFixed(0)} RMS`;
  const rms = status.airband_hold_rms_sample == null ? '—' : Number(status.airband_hold_rms_sample).toFixed(1);
  const state = status.airband_squelch_state || (status.airband_playback_squelch_muted ? 'closed' : 'open');
  const quiet = Number(status.airband_hold_quiet_seconds || 0);
  const remaining = status.airband_hold_release_remaining_seconds == null
    ? Math.max(0, 7 - quiet)
    : Number(status.airband_hold_release_remaining_seconds);
  const action = state === 'open'
    ? 'timer reset'
    : `resume scan in ${remaining.toFixed(1)}s`;
  return `HOLD ${freq} AM · ${state.toUpperCase()} · ${squelchLabel} · RMS ${rms} · quiet ${quiet.toFixed(1)}/7.0s · ${action}`;
}

async function refreshOperationMenu() {
  try {
    const status = requireObjectResponse(await jsonRequest('/api/status'), 'Receiver status');
    const airband = await readAirbandStatus();
    const noaaBackendActive = Boolean(status.live_audio_running && status.audio_mode === 'noaa_live');
    const noaaBrowserPlaying = Boolean(liveListening && liveAudioContext && noaaPlaybackChunksScheduled > 0);
    const noaaActive = Boolean(noaaBackendActive || liveListening);
    const airbandActive = Boolean(airband.airband_scan_running);
    updateAirbandTuningDetail(airband, noaaActive);
    syncAirbandHoldAudio(airband);

    el('noaaMenuToggle').textContent = noaaBackendActive && !noaaBrowserPlaying
      ? 'Reconnect NOAA Audio'
      : noaaActive ? 'Stop NOAA Weather' : 'Start NOAA Weather';
    el('noaaMenuToggle').className = noaaActive ? 'stop' : '';
    el('airbandMenuToggle').textContent = airbandActive ? 'Stop Airband Scanner' : 'Start Airband Scanner';
    el('airbandMenuToggle').className = airbandActive ? 'stop' : '';

    if (operationTransitionActive) return;
    if (airband.airband_hold_active) {
      setMessage(
        'operationsMessage',
        formatAirbandHoldScannerMessage(airband),
        airband.airband_squelch_state === 'closed' ? 'warning' : 'good'
      );
      return;
    }
    if (noaaBackendActive && !noaaBrowserPlaying) {
      setMessage('operationsMessage', 'NOAA receiver is active, but browser audio is not connected. Click Reconnect NOAA Audio.', 'warning');
    } else if (noaaActive) {
      setMessage('operationsMessage', 'NOAA Weather listening active. Airband scanner is paused while receiver 00000162 is in use.', 'good');
    } else if (airbandActive) {
      const searchLabel = airband.airband_search_mode === 'fast_spectrum' ? 'Fast Spectrum Search' : 'Traditional scan';
      setMessage('operationsMessage', `${searchLabel} running. It will open live AM audio after validated activity.`, 'warning');
    } else {
      setMessage('operationsMessage', 'NOAA and Airband scanner are stopped.', '');
    }
  } catch (error) {
    setMessage('operationsMessage', `Operation status temporarily unavailable: ${error.message}. Retrying automatically.`, 'warning');
  }
}
async function startAirbandBackground(showOverlay = true) {
  if (!airbandBackgroundWanted || airbandRestartSuspended || liveListening) return false;
  if (showOverlay) {
    await showBusyAndPaint(
      'Starting Airband Scanner…',
      'Preparing the shared audio receiver for AM scanning and live hold audio.'
    );
  }
  try {
    const existing = await readAirbandStatus();
    if (existing.airband_scan_running) return true;
    const scope = el('airbandScanScope').value || 'priority';
    const result = await jsonRequest(
      `/api/airband/scan/activity/start?scope=${encodeURIComponent(scope)}`,
      {method: 'POST'}
    );
    const modeLabel = result.airband_search_mode === 'fast_spectrum'
      ? 'Fast Spectrum Search 120–130 MHz'
      : `Traditional Audio Samples (${result.scan_scope || scope})`;
    setMessage(
      'airbandScanStatus',
      `Scanner active: ${modeLabel}; waiting for valid AM activity.`,
      'warning'
    );
    pollExperimentalScan();
    return true;
  } catch (error) {
    setMessage('airbandScanStatus', `Airband scanner could not start: ${error.message}`, 'error');
    return false;
  } finally {
    if (showOverlay) await hideBusyAfterMinimum(550);
    await refreshOperationMenu();
  }
}
async function stopAirbandBackground(changePreference = true, showOverlay = true) {
  if (changePreference) airbandBackgroundWanted = false;
  if (showOverlay) {
    await showBusyAndPaint(
      'Stopping Airband Scanner…',
      'Ending scan and releasing held audio.'
    );
  }
  try {
    await jsonRequest('/api/airband/scan/activity/stop', {method: 'POST'});
  } catch (_) {}
  stopAirbandPlayback();
  el('airbandSkipHeld').disabled = true;
  el('airbandBlockHeld').disabled = true;
  const released = await waitForAirbandStopped();
  /* Step 71: guarantee Airband menu stop releases busy overlay */
  if (showOverlay) await hideBusyAfterMinimum(550);
  await refreshOperationMenu();
  return released;
}
async function toggleNoaaMenuOperation() {
  if (operationTransitionActive) return;
  operationTransitionActive = true;
  setOperationButtonsDisabled(true);

  try {
    if (!liveListening) await prepareNoaaAudioForStart(true);
    const current = requireObjectResponse(await jsonRequest('/api/status'), 'Receiver status');
    if (current.live_audio_running && current.audio_mode === 'noaa_live' && !liveListening) {
      closeMenu();
      await showBusyAndPaint('Reconnect NOAA Audio…', 'Attaching browser playback to the active NOAA receiver stream.');
      await attachExistingNoaaLive(current);
      await hideBusyAfterMinimum(550);
      return;
    }
    if (current.live_audio_running || liveListening) {
      await showBusyAndPaint('Stopping NOAA Weather…', 'Releasing the shared audio receiver.');
      await stopLive();
      airbandRestartSuspended = false;
      airbandPausedForNoaa = false;
      airbandBackgroundWanted = false;
      await hideBusyAfterMinimum(550);
      return;
    }

    closeMenu();
    airbandRestartSuspended = true;
    const airband = await readAirbandStatus();
    airbandPausedForNoaa = airbandBackgroundWanted || Boolean(airband.airband_scan_running);

    await showBusyAndPaint(
      'Preparing NOAA Weather…',
      'Stopping Airband background scanning before searching NOAA frequencies.'
    );

    if (airband.airband_scan_running) {
      const released = await stopAirbandBackground(true, false);
      if (!released) throw new Error('Airband did not release the shared receiver.');
    }

    airbandBackgroundWanted = false;
    airbandPausedForNoaa = false;

    updateBusy(
      'Locating local NOAA Weather channel…',
      'Fast scanning all seven NOAA carriers, then validating clear weather audio.'
    );
    await autoNoaa();

    const started = await waitForNoaaRunning();
    if (!started) {
      throw new Error('NOAA live audio did not report running within 12 seconds.');
    }
    updateBusy(
      'NOAA Weather listening active',
      `Tuned to ${(Number(started.noaa_frequency_hz) / 1000000).toFixed(3)} MHz.`
    );
    await hideBusyAfterMinimum(550);
  } catch (error) {
    hideBusy();
    airbandRestartSuspended = false;
    airbandBackgroundWanted = false;
    airbandPausedForNoaa = false;
    await releaseUnusedPreparedNoaaAudio();
    setMessage('operationsMessage', `NOAA operation failed: ${error.message}. Airband remains stopped.`, 'error');
  } finally {
    operationTransitionActive = false;
    setOperationButtonsDisabled(false);
    await refreshOperationMenu();
  }
}
async function toggleAirbandMenuOperation() {
  if (operationTransitionActive) return;
  operationTransitionActive = true;
  setOperationButtonsDisabled(true);

  try {
    await prepareAirbandAudio();
    const airband = await readAirbandStatus();
    if (airband.airband_scan_running) {
      airbandRestartSuspended = true;
      await stopAirbandBackground(true, true);
      airbandRestartSuspended = false;
      return;
    }

    closeMenu();
    const status = requireObjectResponse(await jsonRequest('/api/status'), 'Receiver status');
    if (status.live_audio_running || liveListening) {
      await showBusyAndPaint('Stopping NOAA Weather…', 'Releasing the shared receiver for Airband scanning.');
      await stopLive();
    }

    airbandBackgroundWanted = true;
    airbandRestartSuspended = false;
    await startAirbandBackground(true);
  } catch (error) {
    hideBusy();
    setMessage('operationsMessage', `Airband operation failed: ${error.message}`, 'error');
  } finally {
    hideBusy(); // Step 71 safeguard: no menu operation may leave the spinner visible.
    operationTransitionActive = false;
    setOperationButtonsDisabled(false);
    await refreshOperationMenu();
  }
}
async function startDefaultBackgroundAirband() {
  airbandBackgroundWanted = false;
  airbandRestartSuspended = false;
  await refreshOperationMenu();
}

function bindControls() {
  el('aircraftDetailClose').addEventListener('click', closeAircraftDetails);
  el('aircraftDetailOverlay').addEventListener('click', event => {
    if (event.target === el('aircraftDetailOverlay')) closeAircraftDetails();
  });
  el('pickLocationOnMap').addEventListener('click', beginReceiverLocationPick);
  el('cancelLocationPick').addEventListener('click', cancelReceiverLocationPick);
  el('menuToggle').addEventListener('click', toggleMenu);
  el('menuBackdrop').addEventListener('click', closeMenu);
  el('noaaMenuToggle').addEventListener('click', toggleNoaaMenuOperation);
  el('airbandMenuToggle').addEventListener('click', toggleAirbandMenuOperation);
  el('airbandSkipHeld').addEventListener('click', skipHeldAirbandChannel);
  el('airbandBlockHeld').addEventListener('click', blockHeldAirbandChannel);
  el('clearAirbandBlocks').addEventListener('click', clearBlockedAirbandFrequencies);
  el('startLive').addEventListener('click', startLive);
  el('stopLive').addEventListener('click', stopLive);
  el('capture10').addEventListener('click', captureNoaa);
  el('autoNoaa').addEventListener('click', autoNoaa);
  el('saveLocation').addEventListener('click', saveLocation);
  el('saveAirbandRadius').addEventListener('click', saveAirbandRadius);
  if (el('saveTrafficSources')) el('saveTrafficSources').addEventListener('click', saveTrafficSources);
  el('saveAirlabsKey').addEventListener('click', saveAirlabsKey);
  el('clearAirlabsKey').addEventListener('click', clearAirlabsKey);
  el('testAirlabsKey').addEventListener('click', testAirlabsKey);
  el('clearAirlabsRouteCache').addEventListener('click', clearAirlabsRouteCache);
  el('rescanNoaaChannel').addEventListener('click', rescanSavedNoaaChannel);
  el('loadAirbandChannels').addEventListener('click', loadAirbandChannels);
  el('activityScanStart').addEventListener('click', startExperimentalScan);
  el('activityScanStop').addEventListener('click', stopExperimentalScan);
  el('airbandTestStart').addEventListener('click', startAirbandTest);
  el('airbandTestStop').addEventListener('click', () => airbandTestCommand('stop'));
  el('airbandTestHold').addEventListener('click', () => airbandTestCommand('hold'));
  el('airbandTestSkip').addEventListener('click', () => airbandTestCommand('skip'));
  el('airbandTestResume').addEventListener('click', () => airbandTestCommand('resume'));
  el('fitAircraftMap').addEventListener('click', fitAircraftMap);
  el('centerReceiverMap').addEventListener('click', centerReceiverMap);
  el('clearAircraftTrails').addEventListener('click', clearAircraftTrails);
  el('erasePiTrails').addEventListener('click', eraseTrailHistory);
  el('loadPiTrails').addEventListener('click', () => loadTrailHistoryFromServer(true));
  el('trailRetention').addEventListener('change', changeTrailRetention);
  for (const id of ['locationName', 'locationLatitude', 'locationLongitude', 'locationRadius']) {
    el(id).addEventListener('input', () => { el('locationName').dataset.edited = 'true'; });
  }
}

window.addEventListener('storage', event => {
  if (event.key === TRAIL_CLEARED_AT_KEY) {
    aircraftTrailClearedAt = Number(event.newValue || '0');
    loadTrailHistory();
    renderStoredTrails();
    setMessage('mapMessage', 'Stored aircraft trails were cleared in another tracker tab.', 'good');
  }
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && el('aircraftDetailOverlay').classList.contains('open')) {
    closeAircraftDetails();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  initializeAircraftMap();
  loadTrailHistory();
  el('trailRetention').value = aircraftTrailDisplayMode === 'active' ? 'active' : String(aircraftTrailRetentionMinutes);
  renderStoredTrails(new Set(aircraftMapMarkers.keys()));
  bindControls();
  loadAirlabsSettings();
  loadTrafficSources();
  loadTrailHistoryFromServer();
  updateStatus();
  updateAircraft();
  const refreshWhenMenuClosed = (label, callback) => () => {
    const menu = el('appMenu');
    if (menu && menu.classList.contains('open')) {
      window.__trafficSourceRefreshPaused = {paused: true, label, at: new Date().toISOString()};
      return;
    }
    window.__trafficSourceRefreshPaused = {paused: false, label, at: new Date().toISOString()};
    return callback();
  };
  window.setInterval(refreshWhenMenuClosed('status', updateStatus), 2000);
  window.setInterval(refreshWhenMenuClosed('aircraft', updateAircraft), 2000);
  window.setInterval(refreshWhenMenuClosed('operations', refreshOperationMenu), 2500);
  window.setTimeout(startDefaultBackgroundAirband, 900);
});

;

/* Step 51: Airband sensitivity and RF gain controls */
(() => {
  const byId = (id) => document.getElementById(id);
  const tuningMessage = () => byId("airbandTuningMessage");
  const fmt = (value) => value == null ? "—" : Number(value).toFixed(1);

  async function loadAirbandTuning() {
    const response = await fetch("/api/settings/airband-scan", {cache: "no-store"});
    if (!response.ok) throw new Error("Unable to load Airband tuning settings.");
    const settings = await response.json();
    byId("airbandActivityThreshold").value = String(settings.airband_activity_threshold_rms);
    byId("airbandRfGain").value = Number(settings.airband_rf_gain_db).toFixed(1);
    byId("airbandSearchMode").value = settings.airband_search_mode || "fast_spectrum";
    byId("airbandSpectrumMargin").value = String(settings.airband_spectrum_margin_db == null ? 8 : settings.airband_spectrum_margin_db);
    renderBlockedAirbandFrequencies(settings);
    const search = settings.airband_search_mode === "fast_spectrum" ? "Fast 120–130 MHz" : "Traditional";
    tuningMessage().textContent = `${search} · Trigger ${fmt(settings.airband_activity_threshold_rms)} RMS · Gain ${fmt(settings.airband_rf_gain_db)} dB · Carrier +${fmt(settings.airband_spectrum_margin_db)} dB.`;
  }

  async function saveAirbandTuning() {
    const payload = {
      airband_activity_threshold_rms: Number(byId("airbandActivityThreshold").value),
      airband_rf_gain_db: Number(byId("airbandRfGain").value),
      airband_search_mode: byId("airbandSearchMode").value,
      airband_spectrum_margin_db: Number(byId("airbandSpectrumMargin").value)
    };
    const response = await fetch("/api/settings/airband-scan", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "Unable to save Airband tuning settings.");
    const search = result.airband_search_mode === "fast_spectrum" ? "Fast 120–130 MHz" : "Traditional";
    tuningMessage().textContent = `Applied: ${search} · trigger ${fmt(result.airband_activity_threshold_rms)} RMS · gain ${fmt(result.airband_rf_gain_db)} dB · carrier +${fmt(result.airband_spectrum_margin_db)} dB. Restart scanner to change search mode.`;
  }

  async function refreshAirbandMeasurement() {
    try {
      const response = await fetch("/api/airband/scan/status", {cache: "no-store"});
      if (!response.ok) return;
      const status = await response.json();
      const trigger = status.airband_activity_threshold_rms;
      const gain = status.airband_rf_gain_db;
      const last = status.airband_last_measurement_dbfs;
      const best = status.airband_best_rms_sample;
      const search = status.airband_search_mode === "fast_spectrum" ? "Fast" : "Traditional";
      if (last != null) {
        const hit = Number(last) >= Number(trigger) ? "HIT" : "below trigger";
        tuningMessage().textContent = `${search} · Last ${fmt(last)} RMS / trigger ${fmt(trigger)} (${hit}) · best ${fmt(best)} · gain ${fmt(gain)} dB`;
      } else if (status.airband_search_mode === "fast_spectrum") {
        tuningMessage().textContent = `Fast · carrier trigger +${fmt(status.airband_spectrum_margin_db)} dB · gain ${fmt(gain)} dB · awaiting AM validation.`;
      }
    } catch (error) {
      void error;
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    if (!byId("saveAirbandTuning")) return;
    byId("saveAirbandTuning").addEventListener("click", async () => {
      try { await saveAirbandTuning(); } catch (error) { tuningMessage().textContent = error.message; }
    });
    loadAirbandTuning().catch((error) => { tuningMessage().textContent = error.message; });
    setInterval(refreshAirbandMeasurement, 2000);
  });
})();

;

/* Step 57: map scanner controls and Airband apply layout */
(() => {
  const byId = (id) => document.getElementById(id);
  const setMapState = (value) => {
    const target = byId("mapAirbandActionState");
    if (target) target.textContent = value;
  };
  async function scannerAction(action) {
    const response = await fetch(`/api/airband/scan/activity/${action}`, {method: "POST"});
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `Unable to ${action} held frequency.`);
    setMapState(action === "block" ? "Blocked; scanning resumes" : "Skipped; scanning resumes");
  }
  async function refreshMapScannerControls() {
    try {
      const response = await fetch("/api/airband/scan/status", {cache: "no-store"});
      if (!response.ok) return;
      const status = await response.json();
      const holding = Boolean(status.airband_hold_active);
      const skip = byId("mapAirbandSkipHeld");
      const block = byId("mapAirbandBlockHeld");
      if (skip) skip.disabled = !holding;
      if (block) block.disabled = !holding;
      if (holding) {
        const channel = status.airband_hold_channel || {};
        const mhz = Number(channel.frequency_mhz || (Number(channel.frequency_hz || 0) / 1000000)).toFixed(3);
        setMapState(`HOLD ${mhz} MHz`);
      } else if (status.airband_scan_running) {
        setMapState("Scanning — controls enable on hold");
      } else {
        setMapState("Scanner stopped");
      }
    } catch (error) {
      void error;
    }
  }
  window.addEventListener("DOMContentLoaded", () => {
    const skip = byId("mapAirbandSkipHeld");
    const block = byId("mapAirbandBlockHeld");
    if (!skip || !block) return;
    skip.addEventListener("click", () => scannerAction("skip").catch((error) => setMapState(error.message)));
    block.addEventListener("click", () => scannerAction("block").catch((error) => setMapState(error.message)));
    refreshMapScannerControls();
    window.setInterval(refreshMapScannerControls, 500);
  });
})();

;

/* Step 67: live Airband squelch controls below map */
(() => {
  const byId = (id) => document.getElementById(id);
  function renderSquelch(status) {
    const level = Number(status.airband_playback_squelch_rms || 0);
    const muted = Boolean(status.airband_playback_squelch_muted);
    const holding = Boolean(status.airband_hold_active);
    const value = byId("mapAirbandSquelchValue");
    if (value) {
      value.textContent = level <= 0 ? "Off" : `${level.toFixed(0)} RMS${muted ? " mute" : ""}`;
      value.classList.toggle("muted", muted);
    }
    const down = byId("mapAirbandSquelchDown");
    const up = byId("mapAirbandSquelchUp");
    if (down) down.disabled = !holding || level <= 0;
    if (up) up.disabled = !holding || level >= 5000;
  }
  async function adjustSquelch(deltaRms) {
    const response = await fetch("/api/settings/airband-playback-squelch", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({delta_rms: deltaRms})
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "Unable to adjust Airband squelch.");
    renderSquelch(result);
  }
  async function refreshSquelch() {
    try {
      const response = await fetch("/api/airband/scan/status", {cache: "no-store"});
      if (!response.ok) return;
      renderSquelch(await response.json());
    } catch (error) {
      void error;
    }
  }
  window.addEventListener("DOMContentLoaded", () => {
    const down = byId("mapAirbandSquelchDown");
    const up = byId("mapAirbandSquelchUp");
    if (!down || !up) return;
    down.addEventListener("click", () => adjustSquelch(-100).catch(() => {}));
    up.addEventListener("click", () => adjustSquelch(100).catch(() => {}));
    refreshSquelch();
    window.setInterval(refreshSquelch, 450);
  });
})();

;

/* Step 80: NOAA browser diagnostic trace recorder */
(() => {
  const KEY = 'rtl.adsb.noaa.debug.trace.v1';
  const MAX = 1200;
  let enabled = false, events = [], seq = 0, chunkSeq = 0, lastState = '';
  let watchedMedia = null;
  const watchedContexts = new WeakSet();
  const originalFetch = window.fetch.bind(window);
  const at = () => new Date().toISOString();
  const get = id => document.getElementById(id);
  const cleanError = e => e ? {name:String(e.name || 'Error'), message:String(e.message || e), stack:String(e.stack || '').slice(0,800)} : null;
  function cloneSafe(value) { try { return JSON.parse(JSON.stringify(value)); } catch (_) { return String(value); } }
  function displayState() {
    const node = get('noaaDebugState');
    if (!node) return;
    node.textContent = enabled ? `Recording · ${events.length} events` : `${events.length} events saved`;
    node.classList.toggle('recording', enabled);
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(events)); } catch (_) {} }
  function log(type, data = {}) {
    if (!enabled && type !== 'trace.begin') return;
    events.push({seq: ++seq, at: at(), type, data: cloneSafe(data)});
    if (events.length > MAX) events.splice(0, events.length - MAX);
    save(); displayState();
    console.debug('[NOAA TRACE]', type, data);
  }
  function contextState(ctx) {
    return ctx ? {state:ctx.state, time:Number(ctx.currentTime || 0).toFixed(3), sampleRate:ctx.sampleRate} : null;
  }
  function mediaState(media) {
    return media ? {paused:media.paused, ended:media.ended, muted:media.muted, volume:media.volume, currentTime:Number(media.currentTime || 0).toFixed(3), readyState:media.readyState, networkState:media.networkState, error:media.error ? media.error.code : null} : null;
  }
  function watchRuntimeObjects() {
    let media = null, liveCtx = null, airCtx = null;
    try {
      media = typeof noaaHtmlAudioElement === 'undefined' ? null : noaaHtmlAudioElement;
      liveCtx = typeof liveAudioContext === 'undefined' ? null : liveAudioContext;
      airCtx = typeof airbandAudioContext === 'undefined' ? null : airbandAudioContext;
    } catch (_) {}
    if (media && media !== watchedMedia) {
      watchedMedia = media;
      log('media.attach', mediaState(media));
      ['loadstart','loadeddata','canplay','play','playing','pause','waiting','stalled','ended','emptied','error','volumechange'].forEach(name => {
        media.addEventListener(name, () => log(`media.${name}`, mediaState(media)));
      });
    }
    [['live', liveCtx], ['airband', airCtx]].forEach(([label, ctx]) => {
      if (!ctx || watchedContexts.has(ctx)) return;
      watchedContexts.add(ctx);
      log('context.attach', {label, ...contextState(ctx)});
      ctx.addEventListener('statechange', () => log('context.statechange', {label, ...contextState(ctx)}));
    });
  }
  function snapshot(reason) {
    if (!enabled) return;
    const state = {reason};
    try {
      state.liveListening = typeof liveListening === 'undefined' ? 'missing' : Boolean(liveListening);
      state.liveNextCursor = typeof liveNextCursor === 'undefined' ? 'missing' : liveNextCursor;
      state.liveNextPlayTime = typeof liveNextPlayTime === 'undefined' ? 'missing' : liveNextPlayTime;
      state.chunksScheduled = typeof noaaPlaybackChunksScheduled === 'undefined' ? 'missing' : noaaPlaybackChunksScheduled;
      state.lastChunkRms = typeof noaaPlaybackLastChunkRms === 'undefined' ? 'missing' : noaaPlaybackLastChunkRms;
      state.usesAirbandContext = typeof noaaAudioUsesAirbandContext === 'undefined' ? 'missing' : Boolean(noaaAudioUsesAirbandContext);
      state.liveContext = contextState(typeof liveAudioContext === 'undefined' ? null : liveAudioContext);
      state.airbandContext = contextState(typeof airbandAudioContext === 'undefined' ? null : airbandAudioContext);
      state.htmlPlayer = mediaState(typeof noaaHtmlAudioElement === 'undefined' ? null : noaaHtmlAudioElement);
      state.htmlQueueLength = typeof noaaHtmlAudioQueue === 'undefined' ? 'missing' : noaaHtmlAudioQueue.length;
    } catch (error) { state.error = cleanError(error); }
    const encoded = JSON.stringify(state);
    if (encoded !== lastState) { lastState = encoded; log('app.state', state); }
    watchRuntimeObjects();
  }
  function wavSample(buffer) {
    if (!buffer || buffer.byteLength < 46) return {bytes:buffer ? buffer.byteLength : 0};
    try {
      const view = new DataView(buffer);
      let sum = 0, count = 0, peak = 0;
      for (let offset = 44; offset + 1 < buffer.byteLength; offset += 16) {
        const value = view.getInt16(offset, true);
        sum += value * value; peak = Math.max(peak, Math.abs(value)); count += 1;
      }
      return {bytes:buffer.byteLength, sampledRms:count ? Math.sqrt(sum / count).toFixed(2) : '0', sampledPeak:peak};
    } catch (error) { return {bytes:buffer.byteLength, error:String(error.message || error)}; }
  }
  function statusSubset(path, value) {
    if (!value || typeof value !== 'object') return value;
    if (path === '/api/status') return {audio_mode:value.audio_mode, live_audio_running:value.live_audio_running, noaa_frequency_hz:value.noaa_frequency_hz, noaa_station:value.noaa_station, audio_busy:value.audio_busy, noaa_live_active:value.noaa_live_active};
    return value;
  }
  window.fetch = async function(resource, options) {
    const raw = typeof resource === 'string' ? resource : (resource && resource.url ? resource.url : String(resource));
    let u;
    try { u = new URL(raw, location.href); } catch (_) { return originalFetch(resource, options); }
    const path = u.pathname;
    const interesting = path === '/api/status' || path.startsWith('/api/noaa/') || path.startsWith('/api/airband/scan/');
    if (!enabled || !interesting) return originalFetch(resource, options);
    const method = String((options && options.method) || (resource && resource.method) || 'GET').toUpperCase();
    const begun = performance.now();
    log('fetch.begin', {method, path, query:u.search});
    try {
      const response = await originalFetch(resource, options);
      const meta = {method, path, status:response.status, elapsedMs:Math.round(performance.now() - begun)};
      if (path === '/api/noaa/live/audio.wav') {
        const index = ++chunkSeq;
        response.clone().arrayBuffer().then(data => log('fetch.noaaAudioChunk', {...meta, chunk:index, sourceSamples:response.headers.get('X-Source-Samples'), ...wavSample(data)}))
          .catch(error => log('fetch.noaaAudioChunk.error', {...meta, error:cleanError(error)}));
      } else {
        response.clone().json().then(data => log('fetch.response', {...meta, response:statusSubset(path, data)}))
          .catch(error => log('fetch.response.nonJson', {...meta, error:cleanError(error)}));
      }
      return response;
    } catch (error) {
      log('fetch.error', {method, path, elapsedMs:Math.round(performance.now() - begun), error:cleanError(error)});
      throw error;
    }
  };
  function observeBufferScheduling() {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx || !Ctx.prototype || Ctx.prototype.__noaaTraceOriginalCreate) return;
    const originalCreate = Ctx.prototype.createBufferSource;
    Ctx.prototype.__noaaTraceOriginalCreate = originalCreate;
    Ctx.prototype.createBufferSource = function(...args) {
      const ctx = this;
      const source = originalCreate.apply(ctx, args);
      const originalStart = source.start.bind(source);
      source.start = function(when, ...remaining) {
        if (enabled) log('webaudio.buffer.start', {context:contextState(ctx), scheduledAt:typeof when === 'number' ? Number(when).toFixed(3) : 'immediate', duration:source.buffer ? Number(source.buffer.duration).toFixed(3) : null});
        return originalStart(when, ...remaining);
      };
      return source;
    };
  }
  /* Step 82: locate Diagnostics host for NOAA trace controls */
  function findNoaaDiagnosticsHost(anchor) {
    const preferredIds = [
      'diagnosticsContent', 'diagnosticsPanel', 'diagnosticPanel',
      'diagnosticsSection', 'diagnostics', 'diagnosticContent'
    ];
    for (const id of preferredIds) {
      const candidate = get(id);
      if (candidate) return candidate;
    }

    const labels = Array.from(document.querySelectorAll(
      'summary, legend, h1, h2, h3, h4, .section-title, .menu-title, .panel-title, .card-title'
    ));
    for (const label of labels) {
      const value = String(label.textContent || '').trim();
      if (!/^diagnostics?(?:\s|$)/i.test(value)) continue;
      const details = label.closest('details');
      if (details) return details;
      const container = label.closest(
        'fieldset, section, .config-section, .menu-section, .settings-section, .panel, .card'
      );
      if (container) return container;
      if (label.parentElement) return label.parentElement;
    }

    const menu = anchor.closest(
      'details, .config-panel, .operations-panel, .menu-panel, .settings-panel'
    ) || anchor.parentElement || document.body;
    let fallback = get('noaaDiagnosticsFallback');
    if (!fallback) {
      fallback = document.createElement('details');
      fallback.id = 'noaaDiagnosticsFallback';
      fallback.className = 'menu-section';
      fallback.innerHTML = '<summary>Diagnostics</summary>';
      menu.appendChild(fallback);
    }
    return fallback;
  }

  function installControls() {
    const anchor = get('noaaMenuToggle');
    if (!anchor || get('noaaDebugTools')) return;
    const tools = document.createElement('div');
    tools.id = 'noaaDebugTools';
    tools.className = 'noaa-debug-tools';
    tools.innerHTML = '<button type="button" id="noaaDebugBegin">Begin NOAA Trace</button><button type="button" id="noaaDebugDownload">Download Log</button><button type="button" id="noaaDebugClear">Clear</button><span id="noaaDebugState" class="noaa-debug-state">0 events saved</span>';
    findNoaaDiagnosticsHost(anchor).appendChild(tools);
    get('noaaDebugBegin').addEventListener('click', () => {
      events = []; seq = 0; chunkSeq = 0; lastState = ''; enabled = true;
      log('trace.begin', {userAgent:navigator.userAgent, location:location.href});
      snapshot('begin');
    });
    get('noaaDebugClear').addEventListener('click', () => {
      enabled = false; events = []; seq = 0; chunkSeq = 0; lastState = '';
      try { localStorage.removeItem(KEY); } catch (_) {}
      displayState();
    });
    get('noaaDebugDownload').addEventListener('click', () => {
      snapshot('download');
      const blob = new Blob([JSON.stringify({generatedAt:at(), eventCount:events.length, note:'Browser NOAA playback trace only; no keys intentionally recorded.', events}, null, 2)], {type:'application/json'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `N0JCG_AIR_TRAFFIC_CENTER_NOAA_Browser_Trace_${at().replace(/[:.]/g, '-')}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    displayState();
  }
  function initialize() {
    installControls();
    observeBufferScheduling();
    try {
      const stored = localStorage.getItem(KEY);
      if (stored) events = JSON.parse(stored) || [];
      seq = events.reduce((n, item) => Math.max(n, Number(item.seq || 0)), 0);
    } catch (_) {}
    displayState();
    document.addEventListener('click', event => {
      if (!enabled) return;
      const button = event.target && event.target.closest ? event.target.closest('button') : null;
      if (!button) return;
      const label = String(button.textContent || '').trim();
      if (/NOAA|Airband|Reconnect|Scanner|Stop/i.test(label)) log('ui.button', {id:button.id || null, label});
    }, true);
    window.addEventListener('error', event => log('window.error', {message:event.message, source:event.filename, line:event.lineno}));
    window.addEventListener('unhandledrejection', event => log('window.unhandledrejection', {error:cleanError(event.reason)}));
    setInterval(() => snapshot('interval'), 400);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();

;

/* Step 81: start NOAA chunk pump when live state has no first request */
(() => {
  let activeSinceMs = 0;
  let lastKickMs = 0;
  let kickInFlight = false;
  let reportedKick = false;

  function noaaLiveNeedsFirstChunk() {
    try {
      return typeof liveListening !== 'undefined' && liveListening === true &&
        typeof liveAudioContext !== 'undefined' && Boolean(liveAudioContext) &&
        typeof noaaPlaybackChunksScheduled !== 'undefined' && Number(noaaPlaybackChunksScheduled) === 0 &&
        typeof liveNextCursor !== 'undefined' && Number(liveNextCursor) === 0;
    } catch (_) {
      return false;
    }
  }

  async function startMissingNoaaPump() {
    if (kickInFlight || !noaaLiveNeedsFirstChunk()) return;
    kickInFlight = true;
    lastKickMs = performance.now();
    try {
      // The existing stream scheduler handles fetch, decode, queue depth and
      // all subsequent polling. This call only starts its missing first cycle.
      if (typeof liveNextPlayTime !== 'undefined' && liveAudioContext) {
        liveNextPlayTime = liveAudioContext.currentTime + 0.06;
      }
      if (!reportedKick && typeof setMessage === 'function') {
        setMessage('audioMessage', 'NOAA stream is live; starting browser audio feed…', '');
        reportedKick = true;
      }
      await pumpLiveAudio();
    } catch (error) {
      console.error('NOAA playback bootstrap failed', error);
      if (typeof setMessage === 'function') {
        setMessage('audioMessage', `NOAA playback bootstrap failed: ${error.message || error}`, 'error');
      }
    } finally {
      kickInFlight = false;
    }
  }

  window.setInterval(() => {
    if (!noaaLiveNeedsFirstChunk()) {
      activeSinceMs = 0;
      lastKickMs = 0;
      reportedKick = false;
      return;
    }
    const now = performance.now();
    if (!activeSinceMs) activeSinceMs = now;
    // Normal startup gets a brief opportunity to start its own first chunk.
    // Intervention occurs only for the traced stall condition.
    if (now - activeSinceMs >= 750 && (!lastKickMs || now - lastKickMs >= 1000)) {
      startMissingNoaaPump();
    }
  }, 125);
})();

;

/* Step 83: saved NOAA channel reused until location change or manual rescan */


// Aircraft marker double-click capture hardening for app.js.
// Leaflet can replace marker DOM icons during marker updates, so this stamps
// and rebinds marker icons each update and disables map double-click zoom.
function rtpV34DisableMapDoubleClickZoom(){
  try{
    const dz=state&&state.map&&state.map.doubleClickZoom;
    if(dz&&typeof dz.disable==="function")dz.disable();
  }catch(_e){}
}
function rtpV34EventPath(event){
  try{if(event&&typeof event.composedPath==="function")return event.composedPath();}catch(_e){}
  const path=[];
  let node=event&&event.target;
  while(node){path.push(node);node=node.parentNode;}
  return path;
}
function rtpV34MarkerFromDblclickEvent(event){
  const path=rtpV34EventPath(event);
  for(const node of path){
    if(!node)continue;
    if(node.__rtpV34AircraftMarker)return node.__rtpV34AircraftMarker;
    if(node.__rtpV33AircraftMarker)return node.__rtpV33AircraftMarker;
    const hex=(node.dataset&&(node.dataset.aircraftHex||node.dataset.hex||node.dataset.icao))||node.getAttribute?.("data-aircraft-hex")||node.getAttribute?.("data-hex")||node.getAttribute?.("data-icao");
    if(hex&&state&&state.markers){
      const h=String(hex).toUpperCase();
      const marker=state.markers.get(h)||state.markers.get(h.toLowerCase())||state.markers.get(String(hex));
      if(marker)return marker;
    }
  }
  return null;
}
function rtpV34StopDblclick(event){
  try{if(event&&typeof L!=="undefined"&&L.DomEvent)L.DomEvent.stop(event);}catch(_e){}
  try{if(event&&event.originalEvent&&typeof L!=="undefined"&&L.DomEvent)L.DomEvent.stop(event.originalEvent);}catch(_e){}
  const original=(event&&event.originalEvent)||event;
  try{if(original&&original.preventDefault)original.preventDefault();}catch(_e){}
  try{if(original&&original.stopPropagation)original.stopPropagation();}catch(_e){}
  try{if(original&&original.stopImmediatePropagation)original.stopImmediatePropagation();}catch(_e){}
  return false;
}
function rtpV34OpenAircraftFromMarker(marker,event){
  rtpV34StopDblclick(event);
  rtpV34DisableMapDoubleClickZoom();
  if(!marker)return false;
  const hex=marker.__rtpV34AircraftHex||marker.__rtpV33AircraftHex;
  const record=marker.__rtpV34AircraftRecord||marker.__rtpV33AircraftRecord||((state.rows&&hex)?state.rows.get(hex):null);
  try{
    if(typeof rtpV33OpenAircraftDetailsFromMap==="function"){
      rtpV33OpenAircraftDetailsFromMap(hex,record,event);
      return false;
    }
  }catch(_e){}
  try{if(hex&&typeof selectAircraft==="function")selectAircraft(hex);}catch(_e){}
  try{if(typeof renderSelected==="function")renderSelected();}catch(_e){}
  return false;
}
function rtpV34BindAircraftMarkerDblclick(marker,hex,a){
  rtpV34DisableMapDoubleClickZoom();
  if(!marker)return marker;
  marker.__rtpV34AircraftHex=hex;
  marker.__rtpV34AircraftRecord=a;
  marker.__rtpV33AircraftHex=hex;
  marker.__rtpV33AircraftRecord=a;
  try{
    if(typeof marker.off==="function")marker.off("dblclick");
    if(typeof marker.on==="function")marker.on("dblclick",event=>rtpV34OpenAircraftFromMarker(marker,event));
  }catch(_e){}
  const iconEl=marker._icon;
  if(iconEl){
    iconEl.__rtpV34AircraftMarker=marker;
    iconEl.__rtpV33AircraftMarker=marker;
    try{iconEl.dataset.aircraftHex=String(hex||"");}catch(_e){}
    try{iconEl.setAttribute("data-aircraft-hex",String(hex||""));}catch(_e){}
    try{iconEl.classList.add("rtp-aircraft-marker");}catch(_e){}
    try{if(typeof L!=="undefined"&&L.DomEvent)L.DomEvent.disableClickPropagation(iconEl);}catch(_e){}
    try{if(typeof L!=="undefined"&&L.DomEvent)L.DomEvent.disableScrollPropagation(iconEl);}catch(_e){}
    if(!iconEl.__rtpV34AircraftDblclickBound){
      iconEl.__rtpV34AircraftDblclickBound=true;
      iconEl.addEventListener("dblclick",event=>rtpV34OpenAircraftFromMarker(marker,event),true);
      iconEl.addEventListener("mousedown",event=>{
        if(event&&event.detail>=2)rtpV34StopDblclick(event);
      },true);
    }
  }
  try{
    window.__rtpV34DblclickStatus={
      installed:true,
      lastBindHex:hex,
      markerCount:state&&state.markers?state.markers.size:null,
      doubleClickZoomEnabled:state&&state.map&&state.map.doubleClickZoom&&typeof state.map.doubleClickZoom.enabled==="function"?state.map.doubleClickZoom.enabled():null
    };
  }catch(_e){}
  return marker;
}
function rtpV34InstallAircraftMapDblclickCapture(){
  rtpV34DisableMapDoubleClickZoom();
  try{
    const container=state&&state.map&&typeof state.map.getContainer==="function"?state.map.getContainer():null;
    if(container&&!container.__rtpV34AircraftDblclickCaptureBound){
      container.__rtpV34AircraftDblclickCaptureBound=true;
      container.addEventListener("dblclick",event=>{
        const marker=rtpV34MarkerFromDblclickEvent(event);
        if(marker)return rtpV34OpenAircraftFromMarker(marker,event);
        rtpV34StopDblclick(event);
        return false;
      },true);
    }
  }catch(_e){}
  try{
    window.__rtpV34DblclickStatus={
      installed:true,
      markerCount:state&&state.markers?state.markers.size:null,
      doubleClickZoomEnabled:state&&state.map&&state.map.doubleClickZoom&&typeof state.map.doubleClickZoom.enabled==="function"?state.map.doubleClickZoom.enabled():null
    };
  }catch(_e){}
}
try{document.addEventListener("DOMContentLoaded",()=>setTimeout(rtpV34InstallAircraftMapDblclickCapture,250));}catch(_e){}

/* RTP_WEATHER_RADAR_HISTORY_MENU_V1_START */
(() => {
  'use strict';
  if (window.__rtpWeatherRadarHistoryMenuV1Installed) return;
  window.__rtpWeatherRadarHistoryMenuV1Installed = true;

  const ENABLED_KEY = 'rtlAdsbWeatherRadarEnabledV1';
  const OPACITY_KEY = 'rtlAdsbWeatherRadarOpacityV1';
  const HISTORY_KEY = 'rtlAdsbWeatherRadarHistoryMinutesV1';
  const SPEED_KEY = 'rtlAdsbWeatherRadarPlaybackSpeedV5';
  const LOOP_KEY = 'rtlAdsbWeatherRadarLoopV1';

  const WEATHER_MAPS_URL = 'https://api.rainviewer.com/public/weather-maps.json';
  const REFRESH_MS = 5 * 60 * 1000;
  const MIN_OPACITY = 15;
  const MAX_OPACITY = 85;
  const DEFAULT_OPACITY = 45;
  const DEFAULT_HISTORY_MINUTES = 60;
  const DEFAULT_SPEED_MS = 750;
  const NEWEST_FRAME_HOLD_MS = 15000;
  const MAX_NATIVE_ZOOM = 7;

  let radarHost = '';
  let radarFrames = [];
  let radarLayer = null;
  let pendingRadarLayer = null;
  let radarTransitionId = 0;
  let currentFrameIndex = -1;
  let refreshTimer = null;
  let playbackTimer = null;
  let playbackRunning = false;
  let loadingFrames = false;
  let controlsBound = false;
  // WEATHER_RADAR_REFRESH_AUTOPLAY_RACE_V3:
  // Prevent boot() and its retry timer from starting concurrent frame loads.
  let startupTriggered = false;

  function byId(id) {
    try { return document.getElementById(id); } catch (_) { return null; }
  }

  function mapInstance() {
    try {
      if (typeof aircraftMap !== 'undefined' && aircraftMap) return aircraftMap;
    } catch (_) {}
    return null;
  }

  // WEATHER_RADAR_AUTOPLAY_DEFAULT_V1:
  // New browsers start with radar enabled. An explicit Show Radar off setting
  // remains respected. Pause is session-only, so reload starts playback again.
  function radarEnabled() {
    const stored = localStorage.getItem(ENABLED_KEY);
    return stored == null ? true : stored === '1';
  }

  function currentOpacity() {
    const stored = Number(localStorage.getItem(OPACITY_KEY) || DEFAULT_OPACITY);
    if (!Number.isFinite(stored)) return DEFAULT_OPACITY;
    return Math.max(MIN_OPACITY, Math.min(MAX_OPACITY, Math.round(stored)));
  }

  function historyMinutes() {
    const stored = Number(localStorage.getItem(HISTORY_KEY) || DEFAULT_HISTORY_MINUTES);
    return stored === 120 ? 120 : 60;
  }

  function playbackSpeedMs() {
    const stored = Number(localStorage.getItem(SPEED_KEY) || DEFAULT_SPEED_MS);
    return [450, 750, 1200].includes(stored) ? stored : DEFAULT_SPEED_MS;
  }

  function playbackLoops() {
    const stored = localStorage.getItem(LOOP_KEY);
    return stored == null ? true : stored === '1';
  }

  function setRadarStatus(message, kind) {
    const status = byId('weatherRadarStatus');
    if (status) {
      status.textContent = message;
      status.className = `message compact-message ${kind || ''}`.trim();
      return;
    }
    try {
      if (typeof setMessage === 'function') setMessage('mapMessage', message, kind || '');
    } catch (_) {}
  }

  function ensureRadarPane(map) {
    if (!map || typeof map.createPane !== 'function') return 'tilePane';

    // WEATHER_RADAR_NO_TILE_FADE_V1:
    // Leaflet's fade animation makes a fully buffered radar frame appear pale
    // before reaching the requested opacity. Disable that map-level tile fade
    // so the ready layer swaps in immediately at its configured opacity.
    try {
      map.options.fadeAnimation = false;
      map._fadeAnimated = false;
      const container = typeof map.getContainer === 'function' ? map.getContainer() : null;
      if (container && container.classList) container.classList.remove('leaflet-fade-anim');
    } catch (_) {}

    let pane = null;
    try { pane = map.getPane('weatherRadarPane'); } catch (_) {}
    if (!pane) {
      pane = map.createPane('weatherRadarPane');
      pane.style.zIndex = '300';
      pane.style.pointerEvents = 'none';
    }
    try { pane.classList.add('weather-radar-no-fade'); } catch (_) {}
    return 'weatherRadarPane';
  }

  function frameTileUrl(frame) {
    if (!frame || !radarHost || !frame.path) return '';
    return `${radarHost}${frame.path}/256/{z}/{x}/{y}/2/1_1.png`;
  }

  function ensureRadarLayer() {
    const map = mapInstance();
    const frame = radarFrames[currentFrameIndex] || radarFrames[radarFrames.length - 1];
    if (!map || typeof L === 'undefined' || !L.tileLayer || !frame) return null;

    if (!radarLayer) {
      radarLayer = L.tileLayer(frameTileUrl(frame), {
        pane: ensureRadarPane(map),
        opacity: currentOpacity() / 100,
        maxNativeZoom: MAX_NATIVE_ZOOM,
        maxZoom: 19,
        updateWhenIdle: false,
        keepBuffer: 2,
        crossOrigin: true,
        attribution: 'Radar: RainViewer'
      });
    }

    try {
      if (!map.hasLayer(radarLayer)) radarLayer.addTo(map);
    } catch (_) {
      try { radarLayer.addTo(map); } catch (_error) { return null; }
    }
    return radarLayer;
  }

  function relativeFrameText(index) {
    const frame = radarFrames[index];
    if (!frame) return 'No frame';
    const newest = radarFrames[radarFrames.length - 1];
    const minutesAgo = newest
      ? Math.max(0, Math.round((Number(newest.time) - Number(frame.time)) / 60))
      : 0;
    const timeText = new Date(Number(frame.time) * 1000).toLocaleTimeString([], {
      hour: 'numeric',
      minute: '2-digit'
    });
    return minutesAgo === 0 ? `${timeText} · Latest` : `${timeText} · ${minutesAgo} min ago`;
  }

  function updateControls() {
    const enabled = radarEnabled();
    const timeline = byId('weatherRadarTimeline');
    const toggle = byId('weatherRadarToggle');
    const opacityInput = byId('weatherRadarOpacity');
    const opacityValue = byId('weatherRadarOpacityValue');
    const history = byId('weatherRadarHistory');
    const speed = byId('weatherRadarSpeed');
    const loop = byId('weatherRadarLoop');
    const play = byId('weatherRadarPlay');
    const pause = byId('weatherRadarPause');
    const frameTime = byId('weatherRadarFrameTime');

    if (toggle) toggle.checked = enabled;
    if (opacityInput) opacityInput.value = String(currentOpacity());
    if (opacityValue) opacityValue.textContent = `${currentOpacity()}%`;
    if (history) history.value = String(historyMinutes());
    if (speed) speed.value = String(playbackSpeedMs());
    if (loop) loop.checked = playbackLoops();

    if (timeline) {
      timeline.min = '0';
      timeline.max = String(Math.max(0, radarFrames.length - 1));
      timeline.value = String(Math.max(0, currentFrameIndex));
      timeline.disabled = !enabled || radarFrames.length < 2;
    }

    if (play) play.disabled = !enabled || radarFrames.length < 2 || playbackRunning;
    if (pause) pause.disabled = !playbackRunning;
    if (frameTime) frameTime.textContent = relativeFrameText(currentFrameIndex);
  }

  function stopPlayback(announce) {
    playbackRunning = false;
    if (playbackTimer) {
      window.clearTimeout(playbackTimer);
      playbackTimer = null;
    }
    updateControls();
    if (announce) setRadarStatus('Radar playback paused.', '');
  }

  // WEATHER_RADAR_BUFFERED_TRANSITIONS_V1:
  // Keep the displayed layer visible until every tile in the replacement
  // layer has loaded. The playback timer starts only after the swap.
  function showFrame(index, announce) {
    if (!radarFrames.length) return Promise.resolve(false);
    const targetIndex = Math.max(0, Math.min(radarFrames.length - 1, Number(index) || 0));
    const frame = radarFrames[targetIndex];
    const map = mapInstance();
    if (!map || typeof L === 'undefined' || !L.tileLayer || !frame) {
      return Promise.resolve(false);
    }

    const transitionId = ++radarTransitionId;
    if (pendingRadarLayer) {
      try { if (map.hasLayer(pendingRadarLayer)) map.removeLayer(pendingRadarLayer); } catch (_) {}
      pendingRadarLayer = null;
    }

    const previousLayer = radarLayer;
    const targetOpacity = currentOpacity() / 100;
    const nextLayer = L.tileLayer(frameTileUrl(frame), {
      pane: ensureRadarPane(map),
      opacity: previousLayer ? 0 : targetOpacity,
      maxNativeZoom: MAX_NATIVE_ZOOM,
      maxZoom: 19,
      updateWhenIdle: false,
      keepBuffer: 2,
      crossOrigin: true,
      attribution: 'Radar: RainViewer'
    });
    pendingRadarLayer = nextLayer;

    return new Promise(resolve => {
      let settled = false;
      let fallbackTimer = null;

      const finishTransition = () => {
        if (settled) return;
        settled = true;
        if (fallbackTimer) window.clearTimeout(fallbackTimer);

        if (transitionId !== radarTransitionId) {
          try { if (map.hasLayer(nextLayer)) map.removeLayer(nextLayer); } catch (_) {}
          resolve(false);
          return;
        }

        try { nextLayer.setOpacity(targetOpacity); } catch (_) {}
        if (previousLayer && previousLayer !== nextLayer) {
          try { if (map.hasLayer(previousLayer)) map.removeLayer(previousLayer); } catch (_) {}
        }
        radarLayer = nextLayer;
        pendingRadarLayer = null;
        currentFrameIndex = targetIndex;
        updateControls();
        if (announce) {
          setRadarStatus(`Showing radar frame ${relativeFrameText(currentFrameIndex)}.`, 'good');
        }
        resolve(true);
      };

      try {
        nextLayer.once('load', finishTransition);
        nextLayer.addTo(map);
      } catch (_) {
        if (pendingRadarLayer === nextLayer) pendingRadarLayer = null;
        resolve(false);
        return;
      }

      // A provider or network error must not freeze playback indefinitely.
      fallbackTimer = window.setTimeout(finishTransition, 6000);
    });
  }

  function schedulePlaybackStep() {
    if (!playbackRunning) return;
    const newest = currentFrameIndex === radarFrames.length - 1;
    playbackTimer = window.setTimeout(() => {
      playbackTimer = null;
      if (!playbackRunning || !radarFrames.length) return;

      let next = currentFrameIndex + 1;
      if (next >= radarFrames.length) {
        if (!playbackLoops()) {
          stopPlayback(false);
          showFrame(radarFrames.length - 1, false);
          setRadarStatus('Radar playback complete. Showing the latest frame.', 'good');
          return;
        }
        next = 0;
      }

      void showFrame(next, false).then(() => {
        if (playbackRunning) schedulePlaybackStep();
      });
    }, newest ? NEWEST_FRAME_HOLD_MS : playbackSpeedMs());
  }

  function startPlayback() {
    if (!radarEnabled() || radarFrames.length < 2 || playbackRunning) return;
    if (playbackTimer) {
      window.clearTimeout(playbackTimer);
      playbackTimer = null;
    }
    const restartAtOldest = currentFrameIndex >= radarFrames.length - 1;
    playbackRunning = true;
    updateControls();
    setRadarStatus(
      `Playing ${historyMinutes()} minutes of radar history. ${radarFrames.length} frames loaded.`,
      'good'
    );
    if (restartAtOldest) {
      void showFrame(0, false).then(() => {
        if (playbackRunning) schedulePlaybackStep();
      });
    } else {
      schedulePlaybackStep();
    }
  }

  function selectedFrameTime() {
    const frame = radarFrames[currentFrameIndex];
    return frame ? Number(frame.time) : null;
  }

  function filterFrames(frames) {
    const sorted = frames
      .filter(frame => frame && Number.isFinite(Number(frame.time)) && frame.path)
      .map(frame => ({time: Number(frame.time), path: String(frame.path)}))
      .sort((left, right) => left.time - right.time);

    if (!sorted.length) return [];
    const newestTime = sorted[sorted.length - 1].time;
    const minimumTime = newestTime - historyMinutes() * 60;
    const filtered = sorted.filter(frame => frame.time >= minimumTime);
    return filtered.length ? filtered : sorted.slice(-1);
  }

  async function loadRadarFrames(options) {
    const settings = Object.assign({
      forceLatest: false,
      preserveTime: true
    }, options || {});

    if (loadingFrames) return false;
    loadingFrames = true;
    const previousTime = settings.preserveTime ? selectedFrameTime() : null;
    const wasNewest = currentFrameIndex >= radarFrames.length - 1;
    setRadarStatus('Loading recent weather radar frames…', 'warning');

    try {
      const response = await fetch(`${WEATHER_MAPS_URL}?rtp=${Date.now()}`, {cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const payload = await response.json();
      const host = String(payload && payload.host || '').trim();
      const past = payload && payload.radar && Array.isArray(payload.radar.past)
        ? payload.radar.past
        : [];

      if (!host || !past.length) throw new Error('RainViewer returned no past radar frames.');

      radarHost = host.replace(/\/+$/, '');
      radarFrames = filterFrames(past);
      if (!radarFrames.length) throw new Error('No radar frames matched the selected history range.');

      if (settings.forceLatest || wasNewest || previousTime == null) {
        currentFrameIndex = radarFrames.length - 1;
      } else {
        let bestIndex = 0;
        let bestDistance = Number.POSITIVE_INFINITY;
        radarFrames.forEach((frame, index) => {
          const distance = Math.abs(frame.time - previousTime);
          if (distance < bestDistance) {
            bestDistance = distance;
            bestIndex = index;
          }
        });
        currentFrameIndex = bestIndex;
      }

      if (radarEnabled()) showFrame(currentFrameIndex, false);
      updateControls();

      const generated = Number(payload.generated);
      const generatedText = Number.isFinite(generated)
        ? new Date(generated * 1000).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})
        : 'now';

      setRadarStatus(
        `Loaded ${radarFrames.length} radar frames. Latest: ${relativeFrameText(radarFrames.length - 1)}. Refreshed ${generatedText}.`,
        'good'
      );
      return true;
    } catch (error) {
      setRadarStatus(`Weather radar update failed: ${error.message || error}`, 'error');
      return false;
    } finally {
      loadingFrames = false;
      updateControls();
    }
  }

  function stopRefreshTimer() {
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  function startRefreshTimer() {
    stopRefreshTimer();
    refreshTimer = window.setInterval(() => {
      if (radarEnabled()) loadRadarFrames({preserveTime: true});
    }, REFRESH_MS);
  }

  async function setEnabled(enabled, announce) {
    const active = Boolean(enabled);
    localStorage.setItem(ENABLED_KEY, active ? '1' : '0');

    if (!active) {
      stopPlayback(false);
      stopRefreshTimer();
      const map = mapInstance();
      radarTransitionId += 1;
      try {
        if (map && pendingRadarLayer && map.hasLayer(pendingRadarLayer)) map.removeLayer(pendingRadarLayer);
        if (map && radarLayer && map.hasLayer(radarLayer)) map.removeLayer(radarLayer);
      } catch (_) {}
      pendingRadarLayer = null;
      updateControls();
      if (announce) setRadarStatus('Weather radar overlay disabled.', '');
      return true;
    }

    const loaded = radarFrames.length
      ? true
      : await loadRadarFrames({forceLatest: true, preserveTime: false});

    if (!loaded && !radarFrames.length) {
      localStorage.setItem(ENABLED_KEY, '0');
      updateControls();
      return false;
    }

    showFrame(currentFrameIndex >= 0 ? currentFrameIndex : radarFrames.length - 1, false);
    startRefreshTimer();
    if (radarFrames.length >= 2) startPlayback();
    else updateControls();
    if (announce && !playbackRunning) {
      setRadarStatus('Weather radar overlay enabled on the latest frame.', 'good');
    }
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
    updateControls();
  }

  function setHistory(value) {
    localStorage.setItem(HISTORY_KEY, Number(value) === 120 ? '120' : '60');
    stopPlayback(false);
    if (radarEnabled()) loadRadarFrames({forceLatest: true, preserveTime: false});
    else updateControls();
  }

  function bindControls() {
    if (controlsBound) return true;
    const toggle = byId('weatherRadarToggle');
    const opacity = byId('weatherRadarOpacity');
    const refresh = byId('weatherRadarRefresh');
    const play = byId('weatherRadarPlay');
    const pause = byId('weatherRadarPause');
    const history = byId('weatherRadarHistory');
    const speed = byId('weatherRadarSpeed');
    const loop = byId('weatherRadarLoop');
    const timeline = byId('weatherRadarTimeline');

    if (toggle) toggle.addEventListener('change', () => setEnabled(toggle.checked, true));
    if (opacity) opacity.addEventListener('input', () => setOpacity(opacity.value));
    if (refresh) refresh.addEventListener('click', () => {
      stopPlayback(false);
      loadRadarFrames({forceLatest: true, preserveTime: false});
    });
    if (play) play.addEventListener('click', startPlayback);
    if (pause) pause.addEventListener('click', () => stopPlayback(true));
    if (history) history.addEventListener('change', () => setHistory(history.value));
    if (speed) speed.addEventListener('change', () => {
      const parsed = Number(speed.value);
      localStorage.setItem(SPEED_KEY, String([450, 750, 1200].includes(parsed) ? parsed : DEFAULT_SPEED_MS));
      if (playbackRunning) {
        if (playbackTimer) window.clearTimeout(playbackTimer);
        playbackTimer = null;
        schedulePlaybackStep();
      }
      updateControls();
    });
    if (loop) loop.addEventListener('change', () => {
      localStorage.setItem(LOOP_KEY, loop.checked ? '1' : '0');
      updateControls();
    });
    if (timeline) timeline.addEventListener('input', () => {
      stopPlayback(false);
      showFrame(Number(timeline.value), true);
    });

    controlsBound = true;
    updateControls();
    return true;
  }

  function install() {
    if (!mapInstance()) return false;
    bindControls();

    if (!startupTriggered) {
      startupTriggered = true;
      // Radar animation is the page-refresh default. Turning Show Radar off
      // remains effective for the current page; a reload starts it again.
      localStorage.setItem(ENABLED_KEY, '1');
      updateControls();
      void setEnabled(true, false);
    } else {
      updateControls();
    }

    window.__rtpWeatherRadarHistoryMenuV1 = {
      installed: true,
      refreshIntervalMs: REFRESH_MS,
      api: WEATHER_MAPS_URL,
      get enabled() { return radarEnabled(); },
      get frameCount() { return radarFrames.length; },
      get currentFrameIndex() { return currentFrameIndex; },
      get playbackRunning() { return playbackRunning; },
      refresh: () => loadRadarFrames({forceLatest: true, preserveTime: false}),
      enable: () => setEnabled(true, false),
      play: startPlayback,
      pause: () => stopPlayback(false)
    };
    return true;
  }

  function boot() {
    // Try synchronously first. Only create a retry timer when the map is not
    // ready yet; never leave a second install pending after startup begins.
    if (install()) return;

    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      if (install() || attempts >= 120) window.clearInterval(timer);
    }, 250);
  }

  window.addEventListener('storage', event => {
    if ([ENABLED_KEY, OPACITY_KEY, HISTORY_KEY, SPEED_KEY, LOOP_KEY].includes(event.key)) {
      updateControls();
      if (event.key === ENABLED_KEY) setEnabled(radarEnabled(), false);
      if (event.key === OPACITY_KEY && radarLayer) {
        try { radarLayer.setOpacity(currentOpacity() / 100); } catch (_) {}
      }
    }
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
/* RTP_WEATHER_RADAR_HISTORY_MENU_V1_END */

/* RTP_MAP_RADAR_PLAYBACK_TOGGLE_V1_START */
(() => {
  'use strict';
  if (window.__rtpMapRadarPlaybackToggleV1Installed) return;
  window.__rtpMapRadarPlaybackToggleV1Installed = true;

  const BUTTON_ID = 'mapWeatherRadarPlaybackToggle';
  let clickBound = false;
  let actionRunning = false;

  function radarApi() {
    const api = window.__rtpWeatherRadarHistoryMenuV1;
    return api && api.installed ? api : null;
  }

  function buttonNode() {
    return document.getElementById(BUTTON_ID);
  }

  function updateButton() {
    const button = buttonNode();
    if (!button) return false;

    const api = radarApi();
    const playing = Boolean(api && api.playbackRunning);

    button.textContent = playing ? 'Pause Radar' : 'Play Radar';
    button.classList.toggle('stop', playing);
    button.disabled = actionRunning || !api;
    button.setAttribute('aria-pressed', playing ? 'true' : 'false');
    button.title = playing
      ? 'Pause weather radar playback'
      : 'Resume recent weather radar history';
    return Boolean(api);
  }

  async function togglePlayback() {
    const api = radarApi();
    if (!api || actionRunning) return;

    actionRunning = true;
    updateButton();

    try {
      if (api.playbackRunning) {
        api.pause();
        return;
      }

      if (!api.enabled) {
        const enabled = await api.enable();
        if (!enabled) return;
      }

      if (!api.frameCount) {
        const loaded = await api.refresh();
        if (!loaded) return;
      }

      api.play();
    } catch (error) {
      try {
        if (typeof setMessage === 'function') {
          setMessage(
            'mapMessage',
            `Radar playback failed: ${error.message || error}`,
            'error'
          );
        }
      } catch (_) {}
    } finally {
      actionRunning = false;
      updateButton();
    }
  }

  function install() {
    const button = buttonNode();
    if (!button) return false;

    if (!clickBound) {
      button.addEventListener('click', togglePlayback);
      clickBound = true;
    }

    updateButton();
    return true;
  }

  function boot() {
    let attempts = 0;
    const installTimer = window.setInterval(() => {
      attempts += 1;
      if ((install() && radarApi()) || attempts >= 160) {
        window.clearInterval(installTimer);
      }
    }, 250);

    install();
    window.setInterval(updateButton, 250);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
/* RTP_MAP_RADAR_PLAYBACK_TOGGLE_V1_END */

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
    try { document.title = 'N0JCG AIR TRAFFIC CENTER — Map'; } catch (_) {}
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

// MAP_POPOUT_KIOSK_DEFAULTS_V3_START
// Kiosk URL defaults for the map-only pop-out window.
(function(){
  'use strict';
  if (window.__rtlAdsbMapPopoutKioskDefaultsV3Installed) return;
  window.__rtlAdsbMapPopoutKioskDefaultsV3Installed = true;

  const POPOUT_PARAM = 'map_popout';
  const DEFAULT_RECEIVER_RADIUS_MILES = 30;
  const PLANE_AUTOFIT_MIN_INTERVAL_MS = 6000;
  const RADIO_RADIUS_APPLY_MIN_INTERVAL_MS = 15000;

  let originalUpdateAircraftMap = null;
  let updateAircraftMapWrapped = false;
  let originalRenderLocation = null;
  let renderLocationWrapped = false;
  let receiverRadiusFitApplied = false;
  let lastReceiverSignature = '';
  let lastPlaneAutoFitAt = 0;
  let lastRadioRadiusSignature = '';
  let lastRadioRadiusApplyAt = 0;

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

    // Kiosk default for pop-out: receiver-centered 30-mile view.
    return 'receiver';
  }

  function numericRadiusFromParams(names, fallback) {
    const params = urlParams();
    for (const name of names) {
      const raw = params.get(name);
      if (raw == null || raw === '') continue;
      const parsed = Number(raw);
      if (Number.isFinite(parsed) && parsed >= 5 && parsed <= 500) return parsed;
    }
    return fallback;
  }

  function configuredRadiusMiles() {
    return numericRadiusFromParams(['map_radius_miles', 'radius_miles', 'radius'], DEFAULT_RECEIVER_RADIUS_MILES);
  }

  function configuredRadioRadiusMiles() {
    // Preserve the saved Airband radius unless the kiosk URL explicitly
    // supplies a separate radio/scanner radius.
    return numericRadiusFromParams(
      ['radio_radius_miles', 'airband_radius_miles', 'scan_radius_miles'],
      null
    );
  }

  function formatRadiusForInput(radius) {
    const value = Number(radius);
    if (!Number.isFinite(value)) return String(DEFAULT_RECEIVER_RADIUS_MILES);
    return String(Math.round(value * 10) / 10).replace(/\.0$/, '');
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

  function dispatchRadiusEvents(input) {
    try { input.dispatchEvent(new Event('input', {bubbles: true})); } catch (_) {}
    try { input.dispatchEvent(new Event('change', {bubbles: true})); } catch (_) {}
  }

  function syncRadioRadiusControl(force) {
    if (!isMapPopoutWindow()) return false;

    const radius = configuredRadioRadiusMiles();
    if (radius == null) return true;
    const desired = formatRadiusForInput(radius);
    let changed = false;

    try {
      const input = document.getElementById('locationRadius');
      if (!input) return false;
      if (String(input.value || '').trim() !== desired) {
        input.value = desired;
        changed = true;
        dispatchRadiusEvents(input);
      }
      document.body.dataset.mapPopoutRadioRadiusMiles = desired;
    } catch (_) {
      return false;
    }

    const now = Date.now();
    const signature = desired;
    if (!force && !changed && signature === lastRadioRadiusSignature) return true;
    if (!force && now - lastRadioRadiusApplyAt < RADIO_RADIUS_APPLY_MIN_INTERVAL_MS) return true;

    lastRadioRadiusSignature = signature;
    lastRadioRadiusApplyAt = now;

    // Prefer the app's existing Apply Radius button so this stays compatible with
    // the current backend API and any future validation logic. The click is harmless
    // if the handler is not installed yet; waitAndInstall retries for several seconds.
    try {
      const button = document.getElementById('saveAirbandRadius');
      if (button && typeof button.click === 'function' && !button.disabled) {
        button.click();
        return true;
      }
    } catch (_) {}

    return true;
  }

  function applyConfiguredKioskView(force) {
    if (!isMapPopoutWindow()) return;

    try {
      document.body.classList.add('map-popout-kiosk-defaults-v3');
      document.body.dataset.mapPopoutFit = configuredFitMode();
      document.body.dataset.mapPopoutRadiusMiles = String(configuredRadiusMiles());
      const radioRadius = configuredRadioRadiusMiles();
      if (radioRadius == null) delete document.body.dataset.mapPopoutRadioRadiusMiles;
      else document.body.dataset.mapPopoutRadioRadiusMiles = String(radioRadius);
    } catch (_) {}

    syncRadioRadiusControl(force);
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

  function wrapRenderLocationForRadioRadius() {
    if (!isMapPopoutWindow() || renderLocationWrapped) return;
    try {
      if (typeof renderLocation !== 'function') return;
      originalRenderLocation = renderLocation;
      renderLocation = function(location) {
        const result = originalRenderLocation.apply(this, arguments);
        window.setTimeout(() => syncRadioRadiusControl(true), 0);
        window.setTimeout(() => applyConfiguredKioskView(true), 200);
        return result;
      };
      renderLocationWrapped = true;
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
    wrapRenderLocationForRadioRadius();
    applyConfiguredKioskView(true);
    invalidateAircraftMapSoon();
  }

  function waitAndInstall() {
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      installKioskDefaults();
      const radioRadiusReady = configuredRadioRadiusMiles() == null || Boolean(lastRadioRadiusSignature);
      if ((mapReady() && currentReceiverLocation() && radioRadiusReady) || attempts >= 160) {
        if (attempts >= 160 || receiverRadiusFitApplied || configuredFitMode() === 'planes') {
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
// MAP_POPOUT_KIOSK_DEFAULTS_V3_END


/* menu refresh pause: UI polling is intentionally paused while the configuration menu drawer is open. */

/* RTP_UI_AUDIO_STOP_GUARD_V1: prevent refresh/polling from accidentally stopping shared audio receiver modes. */
(() => {
  'use strict';
  if (window.__rtpUiAudioStopGuardV1Installed) return;
  window.__rtpUiAudioStopGuardV1Installed = true;

  const STOP_PATHS = new Set([
    '/api/noaa/live/stop',
    '/api/airband/scan/activity/stop'
  ]);
  const CONTROL_BUTTON_IDS = new Set([
    'noaaMenuToggle',
    'airbandMenuToggle',
    'activityScanStop',
    'stopLive',
    'rescanNoaaChannel',
    'saveAirbandRadius',
    'saveLocation',
    'airbandSkipHeld',
    'airbandBlockHeld',
    'clearAirbandBlocks'
  ]);
  const TRUST_WINDOW_MS = 12000;
  const originalFetch = window.fetch.bind(window);

  let lastTrustedAction = {at: 0, id: '', type: ''};
  window.__piAudioStopGuard = {
    installed: true,
    blockedStops: [],
    allowedStops: [],
    lastTrustedAction
  };

  function requestPath(input) {
    try {
      const raw = typeof input === 'string' ? input : String(input && input.url || '');
      return new URL(raw, window.location.href).pathname;
    } catch (_) {
      return '';
    }
  }

  function requestMethod(input, init) {
    const method = init && init.method ? init.method : (input && input.method ? input.method : 'GET');
    return String(method || 'GET').toUpperCase();
  }

  function nearestControlId(target) {
    let node = target;
    while (node && node !== document) {
      try {
        if (node.id && CONTROL_BUTTON_IDS.has(node.id)) return node.id;
      } catch (_) {}
      node = node.parentNode;
    }
    return '';
  }

  function markTrusted(event) {
    const id = nearestControlId(event && event.target);
    if (!id) return;
    lastTrustedAction = {
      at: Date.now(),
      id,
      type: event.type || 'user',
      iso: new Date().toISOString()
    };
    window.__piAudioStopGuard.lastTrustedAction = lastTrustedAction;
  }

  function isTrustedStopAllowed() {
    return Date.now() - Number(lastTrustedAction.at || 0) <= TRUST_WINDOW_MS;
  }

  document.addEventListener('pointerdown', markTrusted, true);
  document.addEventListener('click', markTrusted, true);
  document.addEventListener('keydown', event => {
    if (event && (event.key === 'Enter' || event.key === ' ')) markTrusted(event);
  }, true);

  window.fetch = function guardedAudioControlFetch(input, init) {
    const method = requestMethod(input, init);
    const path = requestPath(input);
    if (method === 'POST' && STOP_PATHS.has(path)) {
      const allowed = isTrustedStopAllowed();
      const audit = {
        path,
        method,
        allowed,
        trustedAction: Object.assign({}, lastTrustedAction),
        iso: new Date().toISOString()
      };
      if (!allowed) {
        window.__piAudioStopGuard.blockedStops.push(audit);
        window.__piAudioStopGuard.blockedStops = window.__piAudioStopGuard.blockedStops.slice(-20);
        try {
          if (typeof setMessage === 'function') {
            setMessage(
              'operationsMessage',
              `Blocked unattended ${path} request; scanner/audio stop must come from an operator action.`,
              'warning'
            );
          }
        } catch (_) {}
        return Promise.resolve(new Response(
          JSON.stringify({
            error: 'blocked_untrusted_ui_stop',
            path,
            message: 'Audio stop was blocked because it did not follow a recent operator action.'
          }),
          {
            status: 409,
            headers: {'Content-Type': 'application/json'}
          }
        ));
      }

      window.__piAudioStopGuard.allowedStops.push(audit);
      window.__piAudioStopGuard.allowedStops = window.__piAudioStopGuard.allowedStops.slice(-20);
      const nextInit = Object.assign({}, init || {});
      const headers = new Headers(nextInit.headers || (input && input.headers) || {});
      headers.set('X-PI-Audio-Stop-Guard', `allowed;action=${lastTrustedAction.id || 'unknown'};age_ms=${Date.now() - Number(lastTrustedAction.at || 0)}`);
      nextInit.headers = headers;
      return originalFetch(input, nextInit);
    }
    return originalFetch(input, init);
  };
})();
