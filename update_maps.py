#!/usr/bin/env python3
"""
Update index.html map functions:
  1. initAndaluciaMap  → province fill/highlight (no dot markers)
  2. initMuniMap       → async vector map via Overpass API (province backdrop + municipality polygon)
"""
import re, os

BASE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(BASE, 'index.html')

with open(HTML, encoding='utf-8') as f:
    html = f.read()

# ── 1. Add CSS for loading overlay and update map heights ────────────────────
CSS_INSERT = """
.map-loading-overlay{position:absolute;bottom:10px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.55);color:#fff;padding:3px 12px;border-radius:12px;font-size:.73rem;z-index:1000;pointer-events:none;white-space:nowrap;font-family:Montserrat,sans-serif}
.map-container{position:relative}
"""

# Insert before closing </style>
html = html.replace('</style>', CSS_INSERT + '</style>', 1)
print("CSS added")

# ── 2. Update section title "Mapa del municipio" ─────────────────────────────
html = html.replace(
    '>Mapa del municipio<',
    '>Localización en la provincia<'
)
print("Section title updated")

# ── 3. Add PROV_ISO and cache after let mapAndalucia line ────────────────────
CACHE_BLOCK = """
// Province ISO codes (OSM admin_level=6 names)
const PROV_ISO = {
  'Almería':'Almería','Cádiz':'Cádiz','Córdoba':'Córdoba','Granada':'Granada',
  'Huelva':'Huelva','Jaén':'Jaén','Málaga':'Málaga','Sevilla':'Sevilla'
};
const _muniGeoCache = {};
"""

html = html.replace(
    'let mapAndalucia = null, mapMuni = null;',
    'let mapAndalucia = null, mapMuni = null;\n' + CACHE_BLOCK
)
print("PROV_ISO and cache added")

# ── 4. Replace initAndaluciaMap function ─────────────────────────────────────
OLD_INIT_ANDALUCIA_START = '// ─── MAP: ANDALUCÍA CON MUNICIPIOS ────────────────────────────────'
OLD_INIT_ANDALUCIA_END   = '// ─── MAP: MUNICIPALITY ZOOM ───────────────────────────────────────'

NEW_INIT_ANDALUCIA = r"""// ─── MAP 1: ANDALUCÍA — PROVINCIA RESALTADA ─────────────────────
function initAndaluciaMap(m) {
  const el = document.getElementById('map-andalucia');
  el.style.height = '220px';

  mapAndalucia = L.map('map-andalucia', {
    zoomControl:false, attributionControl:false,
    dragging:false, scrollWheelZoom:false,
    doubleClickZoom:false, boxZoom:false, keyboard:false
  });

  const activeProv = (m.provincia || '').trim();

  const provLayer = L.geoJSON(ANDALUCIA_GEOJSON, {
    style: feature => {
      const isActive = feature.properties.name === activeProv;
      return {
        fillColor: isActive ? '#007932' : '#c8e6d0',
        fillOpacity: isActive ? 0.78 : 0.42,
        color: '#005a25',
        weight: isActive ? 2.5 : 0.8,
        opacity: 0.85
      };
    }
  }).addTo(mapAndalucia);

  mapAndalucia.fitBounds(provLayer.getBounds(), {padding:[6,6]});

  // Text note only when municipality unknown
  const targets = parseMultiMuni(m.municipio);
  if (!m.municipio || m.municipio === '—' || targets.length === 0) {
    addMapNote(el, 'Municipio no especificado');
  }
}

"""

# Find the block to replace
idx_start = html.find(OLD_INIT_ANDALUCIA_START)
idx_end   = html.find(OLD_INIT_ANDALUCIA_END)
if idx_start == -1 or idx_end == -1:
    print("ERROR: could not find initAndaluciaMap block")
else:
    html = html[:idx_start] + NEW_INIT_ANDALUCIA + html[idx_end:]
    print("initAndaluciaMap replaced")

# ── 5. Replace initMuniMap function ──────────────────────────────────────────
OLD_MUNI_START = '// ─── MAP: MUNICIPALITY ZOOM ───────────────────────────────────────'

# Find end of initMuniMap (just before next // ─── block or end of script)
OLD_MUNI_END_PATTERN = re.compile(r'(// ─── [A-Z])', re.DOTALL)

idx_muni_start = html.find(OLD_MUNI_START)
# Find next section comment after this one
tail = html[idx_muni_start + len(OLD_MUNI_START):]
m_end = OLD_MUNI_END_PATTERN.search(tail)
if m_end:
    idx_muni_end = idx_muni_start + len(OLD_MUNI_START) + m_end.start()
else:
    # Go to closing script tag
    idx_muni_end = html.find('</script>', idx_muni_start)

NEW_MUNI_MAP = r"""// ─── MAP 2: PROVINCIA — MUNICIPIO RESALTADO (vectorial) ──────────
async function initProvMuniMap(m) {
  const container = document.getElementById('map-muni-container');
  const el = document.getElementById('map-muni');
  el.style.height = '260px';

  const targets = parseMultiMuni(m.municipio);

  if (!m.municipio || m.municipio === '—' || targets.length === 0) {
    container.innerHTML = `
      <div class="no-muni-note">
        <span>📍</span>
        <div>Municipio no especificado para esta obra</div>
      </div>`;
    return;
  }

  mapMuni = L.map('map-muni', {
    zoomControl:false, attributionControl:false,
    dragging:false, scrollWheelZoom:false,
    doubleClickZoom:false, boxZoom:false, keyboard:false
  });

  // Province backdrop from embedded GeoJSON
  const activeProv = (m.provincia || '').trim();
  const provFeat = ANDALUCIA_GEOJSON.features.find(f => f.properties.name === activeProv);
  let provLayer = null;
  if (provFeat) {
    provLayer = L.geoJSON(provFeat, {
      style: () => ({
        fillColor: '#e8f5ee', fillOpacity: 0.55,
        color: '#007932', weight: 2, opacity: 0.9
      })
    }).addTo(mapMuni);
    mapMuni.fitBounds(provLayer.getBounds(), {padding:[8,8]});
  }

  // Loading overlay
  const overlay = document.createElement('div');
  overlay.className = 'map-loading-overlay';
  overlay.textContent = '⏳ Cargando municipio…';
  el.appendChild(overlay);

  // Fetch each municipality polygon via Overpass API
  let plotted = 0;
  const muniLayers = [];

  for (const muniName of targets) {
    const cacheKey = `${activeProv}::${muniName}`;
    let geoData = _muniGeoCache[cacheKey];

    if (geoData === undefined) {
      try {
        // Query Overpass for admin_level=8 relation within province
        const overpassQ =
          `[out:json];` +
          `area["admin_level"="6"]["name"="${activeProv}"]["boundary"="administrative"]->.prov;` +
          `(relation["admin_level"="8"]["name"="${muniName}"]["boundary"="administrative"](area.prov););` +
          `out geom;`;
        const url = 'https://overpass-api.de/api/interpreter?data=' + encodeURIComponent(overpassQ);
        const resp = await fetch(url);
        if (resp.ok) {
          const json = await resp.json();
          geoData = overpassToGeoJSON(json);
        }
        _muniGeoCache[cacheKey] = geoData || null;
      } catch(e) {
        _muniGeoCache[cacheKey] = null;
      }
    }

    if (geoData && geoData.features && geoData.features.length > 0) {
      const layer = L.geoJSON(geoData, {
        style: () => ({
          fillColor: '#c8952a', fillOpacity: 0.62,
          color: '#7a4a00', weight: 2.5, opacity: 1
        })
      }).addTo(mapMuni);
      layer.bindTooltip(muniName, {permanent:false, className:'muni-tooltip'});
      muniLayers.push(layer);
      plotted++;
    }
  }

  // Remove loading overlay
  if (overlay.parentNode) overlay.remove();

  if (plotted > 0) {
    // Zoom to show all plotted municipalities
    if (muniLayers.length === 1) {
      mapMuni.fitBounds(muniLayers[0].getBounds(), {padding:[18,18]});
    } else {
      const combined = muniLayers.reduce((b,l) => b.extend(l.getBounds()), L.latLngBounds());
      mapMuni.fitBounds(combined, {padding:[12,12]});
    }
  } else {
    // Municipality polygon not found — fall back to centroid dot + note
    let fallbackPlotted = 0;
    targets.forEach(muniName => {
      const c = getMuniCenter(muniName);
      if (c) {
        L.circleMarker([c.lat, c.lon], {
          radius:9, fillColor:'#c8952a', color:'#7a4a00',
          weight:2.5, fillOpacity:0.85
        }).addTo(mapMuni).bindTooltip(muniName);
        fallbackPlotted++;
      }
    });
    if (provLayer) mapMuni.fitBounds(provLayer.getBounds(), {padding:[8,8]});
    if (fallbackPlotted === 0) {
      addMapNote(el, targets.join(', ') + ': municipio no localizado');
    }
  }
}

// Convert Overpass JSON (with geometry) to GeoJSON FeatureCollection
function overpassToGeoJSON(overpass) {
  const features = [];
  for (const el of (overpass.elements || [])) {
    if (el.type !== 'relation') continue;
    // Collect outer way coordinates
    const outerRings = [], innerRings = [];
    for (const member of (el.members || [])) {
      if (member.type !== 'way' || !member.geometry) continue;
      const coords = member.geometry.map(p => [p.lon, p.lat]);
      if (member.role === 'outer') outerRings.push(coords);
      else if (member.role === 'inner') innerRings.push(coords);
    }
    if (outerRings.length === 0) continue;
    let geometry;
    if (outerRings.length === 1) {
      const ring = [...outerRings[0]];
      // Close ring
      if (ring[0][0] !== ring[ring.length-1][0] || ring[0][1] !== ring[ring.length-1][1]) ring.push(ring[0]);
      const holes = innerRings.map(r => {
        if (r[0][0] !== r[r.length-1][0] || r[0][1] !== r[r.length-1][1]) r.push(r[0]);
        return r;
      });
      geometry = {type:'Polygon', coordinates:[ring, ...holes]};
    } else {
      geometry = {
        type:'MultiPolygon',
        coordinates: outerRings.map(r => {
          if (r[0][0] !== r[r.length-1][0] || r[0][1] !== r[r.length-1][1]) r.push(r[0]);
          return [r];
        })
      };
    }
    features.push({type:'Feature', geometry, properties:{name: el.tags && el.tags.name || ''}});
  }
  return {type:'FeatureCollection', features};
}

"""

if idx_muni_start == -1:
    print("ERROR: could not find initMuniMap block start")
else:
    html = html[:idx_muni_start] + NEW_MUNI_MAP + html[idx_muni_end:]
    print("initMuniMap replaced with initProvMuniMap")

# ── 6. Update openModal to call initProvMuniMap ──────────────────────────────
html = html.replace(
    'initMuniMap(m.municipio, m.provincia);',
    'initProvMuniMap(m);'
)
print("openModal updated to call initProvMuniMap")

# ── 7. Write updated HTML ────────────────────────────────────────────────────
with open(HTML, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\nDone! HTML: {len(html):,} chars ({len(html)/1024:.0f} KB)")
