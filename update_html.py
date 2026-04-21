#!/usr/bin/env python3
"""
Update index.html with:
  1. New logo from 'Estilo de la App/Imagen 20-4-26 a las 18.44.jpeg'
  2. PWA manifest (manifest.json) for desktop app icon
  3. local_photo field in MONUMENTOS data (from foto_mapping.json)
  4. Image priority: local_photo > IAPH > "no disponible"
"""
import os, json, re, base64, shutil

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Copy new logo to simple path ─────────────────────────────────────────────
new_logo_src = os.path.join(BASE, 'Estilo de la App', 'Imagen 20-4-26 a las 18.44.jpeg')
new_logo_dst = os.path.join(BASE, 'logo.jpeg')
shutil.copy2(new_logo_src, new_logo_dst)
print(f"Logo copied → logo.jpeg ({os.path.getsize(new_logo_dst):,} bytes)")

# Encode new logo as base64 for inline embedding (favicon + header)
with open(new_logo_dst, 'rb') as f:
    new_logo_b64 = base64.b64encode(f.read()).decode('ascii')
new_logo_data_uri = f'data:image/jpeg;base64,{new_logo_b64}'
print(f"Logo b64 length: {len(new_logo_b64):,} chars")

# ── Create manifest.json ──────────────────────────────────────────────────────
manifest = {
    "name": "Historia de la Arquitectura de Andalucía",
    "short_name": "Arq. Andalucía",
    "description": "Catálogo general del patrimonio histórico arquitectónico de Andalucía",
    "start_url": "./index.html",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#007932",
    "orientation": "portrait-primary",
    "icons": [
        {
            "src": "logo.jpeg",
            "sizes": "192x192",
            "type": "image/jpeg",
            "purpose": "any maskable"
        },
        {
            "src": "logo.jpeg",
            "sizes": "512x512",
            "type": "image/jpeg",
            "purpose": "any maskable"
        }
    ]
}
manifest_path = os.path.join(BASE, 'manifest.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"manifest.json created")

# ── Load foto mapping ─────────────────────────────────────────────────────────
with open(os.path.join(BASE, 'foto_mapping.json'), encoding='utf-8') as f:
    foto_mapping = json.load(f)
print(f"Photo mapping: {len(foto_mapping)} entries")

# ── Load MONUMENTOS from current datos_monumentos.json ───────────────────────
with open(os.path.join(BASE, 'datos_monumentos.json'), encoding='utf-8') as f:
    monumentos = json.load(f)

# Add local_photo field and URL-encode the path
def path_to_url(rel_path):
    """Convert a relative OS path to a URL-safe path."""
    parts = rel_path.replace('\\', '/').split('/')
    encoded = '/'.join(p.replace(' ', '%20').replace('(', '%28').replace(')', '%29')
                        .replace('ó', '%C3%B3').replace('é', '%C3%A9').replace('á', '%C3%A1')
                        .replace('ú', '%C3%BA').replace('í', '%C3%AD').replace('ñ', '%C3%B1')
                        .replace('Á', '%C3%81').replace('É', '%C3%89').replace('Í', '%C3%8D')
                        .replace('Ó', '%C3%93').replace('Ú', '%C3%9A').replace('Ñ', '%C3%91')
                        .replace('ü', '%C3%BC').replace('ª', '%C2%AA')
                        .replace("'", '%27').replace(',', '%2C')
                        for p in parts)
    return encoded

for i, m in enumerate(monumentos):
    foto = foto_mapping.get(str(i))
    if foto:
        m['local_photo'] = path_to_url(foto)
    else:
        m['local_photo'] = None

matched = sum(1 for m in monumentos if m.get('local_photo'))
print(f"Monuments with local_photo: {matched}/{len(monumentos)}")

# ── Read current index.html ───────────────────────────────────────────────────
html_path = os.path.join(BASE, 'index.html')
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()
original_size = len(html)
print(f"Original HTML: {original_size:,} chars")

# ── 1. Replace favicon (the existing base64 data URI in link rel=icon) ───────
# Pattern: <link rel="icon" type="image/jpeg" href="data:image/jpeg;base64,...">
html = re.sub(
    r'<link rel="icon"[^>]+href="data:image/[^"]*"[^>]*>',
    f'<link rel="icon" type="image/jpeg" href="{new_logo_data_uri}">',
    html
)
print("Favicon updated")

# ── 2. Add manifest + apple-touch-icon after the favicon link ────────────────
if 'rel="manifest"' not in html:
    html = html.replace(
        '<link rel="icon"',
        '<link rel="manifest" href="manifest.json">\n<link rel="apple-touch-icon" href="logo.jpeg">\n<meta name="mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-title" content="Arq. Andalucía">\n<link rel="icon"',
        1
    )
    print("PWA manifest tags added")

# ── 3. Replace header logo img src ───────────────────────────────────────────
# The header logo is: <img src="data:image/jpeg;base64,..." alt="Logo" class="header-logo">
html = re.sub(
    r'(<img\s[^>]*class="header-logo"[^>]*src=")data:image/[^"]*(")',
    rf'\g<1>{new_logo_data_uri}\g<2>',
    html
)
# Also handle src before class
html = re.sub(
    r'(<img\s[^>]*src=")data:image/[^"]*("[^>]*class="header-logo")',
    rf'\g<1>{new_logo_data_uri}\g<2>',
    html
)
print("Header logo src updated")

# ── 4. Replace MONUMENTOS data with updated version ──────────────────────────
new_monumentos_json = json.dumps(monumentos, ensure_ascii=False, separators=(',', ':'))
html = re.sub(
    r'const MONUMENTOS = \[.*?\];',
    f'const MONUMENTOS = {new_monumentos_json};',
    html,
    flags=re.DOTALL
)
print("MONUMENTOS data updated")

# ── 5. Replace loadIAPHImage function with local_photo priority ───────────────
old_fn = '''function loadIAPHImage(m) {
  const container = document.getElementById('m-img-container');

  if (m.img_url) {
    // Test if image loads, otherwise show placeholder
    container.className = 'img-wrap';
    container.innerHTML = `
      <img src="${m.img_url}" alt="${esc(m.nombre)}" class="monument-img"
        onerror="showNoImage(this.parentNode, '${esc(m.nombre)}')"
        onload="">
      <div class="img-caption">
        📷 Catálogo General del Patrimonio Histórico de Andalucía · IAPH
      </div>`;
  } else {
    showNoImage(container, m.nombre);
  }
}'''

new_fn = '''function loadIAPHImage(m) {
  const container = document.getElementById('m-img-container');

  if (m.local_photo) {
    // Priority 1: local photo from Recursos/Fotos
    container.className = 'img-wrap';
    container.innerHTML = `
      <img src="${m.local_photo}" alt="${esc(m.nombre)}" class="monument-img"
        onerror="tryIAPHFallback(this, '${esc(m.img_url||'')}', '${esc(m.nombre)}')">
      <div class="img-caption">
        🏛️ Archivo docente de Historia de la Arquitectura de Andalucía
      </div>`;
  } else if (m.img_url) {
    // Priority 2: IAPH/CGPHA image
    container.className = 'img-wrap';
    container.innerHTML = `
      <img src="${m.img_url}" alt="${esc(m.nombre)}" class="monument-img"
        onerror="showNoImage(this.parentNode, '${esc(m.nombre)}')">
      <div class="img-caption">
        📷 Catálogo General del Patrimonio Histórico de Andalucía · IAPH
      </div>`;
  } else {
    showNoImage(container, m.nombre);
  }
}

function tryIAPHFallback(img, iaph_url, nombre) {
  const container = img.parentNode;
  if (iaph_url) {
    container.innerHTML = `
      <img src="${iaph_url}" alt="${nombre}" class="monument-img"
        onerror="showNoImage(this.parentNode, '${nombre}')">
      <div class="img-caption">
        📷 Catálogo General del Patrimonio Histórico de Andalucía · IAPH
      </div>`;
  } else {
    showNoImage(container, nombre);
  }
}'''

if old_fn in html:
    html = html.replace(old_fn, new_fn)
    print("loadIAPHImage function updated")
else:
    # Try to find and replace just the function body
    html = re.sub(
        r'function loadIAPHImage\(m\)\s*\{.*?(?=\nfunction|\n// )',
        new_fn + '\n',
        html,
        flags=re.DOTALL
    )
    print("loadIAPHImage function updated (fallback regex)")

# ── Write updated HTML ────────────────────────────────────────────────────────
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

final_size = len(html)
print(f"\nUpdated HTML: {final_size:,} chars ({final_size/1024:.0f} KB)")
print(f"Change: {final_size - original_size:+,} chars")
print("Done!")
