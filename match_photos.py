#!/usr/bin/env python3
"""
Match local photos to monument records.
Uses keyword matching with proper-noun priority to avoid false positives.
Output: foto_mapping.json  { "INDEX": "relative/path/to/photo.jpg" }
"""
import os, json, re, unicodedata

BASE = os.path.dirname(os.path.abspath(__file__))
FOTO_DIR = os.path.join(BASE, "Recursos", "Fotos")

STOPWORDS = {
    'de', 'del', 'la', 'las', 'los', 'el', 'en', 'y', 'a', 'al',
    'un', 'una', 'unos', 'unas', 'con', 'por', 'para', 'the', 'of', 'and'
}

# Generic monument-type words that appear in many filenames (not useful for discrimination)
GENERIC = {
    'dolmen', 'necropolis', 'castillo', 'iglesia', 'convento', 'palacio',
    'mezquita', 'puerta', 'alcazar', 'alcazaba', 'torre', 'muralla', 'murallas',
    'santuario', 'basilica', 'catedral', 'monasterio', 'conjunto', 'yacimiento',
    'ermita', 'teatro', 'templo', 'anfiteatro', 'banos', 'foro', 'acueducto',
    'puente', 'plaza', 'ayuntamiento', 'hospital', 'cueva', 'tholos', 'dolmenes',
    'neolitico', 'romano', 'romana', 'medieval', 'visigodo', 'arabe', 'arabes',
    'cristiano', 'islamico', 'ibero', 'iberos', 'fenicio', 'romano', 'romana',
    'capilla', 'oratorio', 'patio', 'salon', 'sala', 'palacete', 'parroquia',
    'recinto', 'reconstruccion', 'ruinas', 'ciudad', 'poblado', 'villa',
    'asentamiento', 'enclave', 'complejo', 'parque', 'museo', 'patrimonio',
    'arquitectura', 'arquitectonico', 'baluarte', 'fortification', 'fuerte',
    'fortaleza', 'castros', 'aqueducto', 'termas', 'mausoleo', 'sepulcro',
    'necrópolis', 'cámara', 'camara', 'sepulcral', 'sepultura',
    'retiro', 'jardines', 'jardin', 'fuente', 'parque',
}

def normalize(s):
    s = s.lower()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def key_words(s):
    return set(w for w in normalize(s).split() if len(w) >= 4 and w not in STOPWORDS)

def specific_words(ws):
    """Words that are not generic monument types."""
    return ws - GENERIC

# ── load monuments ────────────────────────────────────────────────────────────
with open(os.path.join(BASE, 'datos_monumentos.json')) as f:
    monumentos = json.load(f)

# ── build photo index ────────────────────────────────────────────────────────
SKIP_EXTS = {'.ds_store', '.gif'}

folder_photos = {}
for root, dirs, files in os.walk(FOTO_DIR):
    dirs[:] = sorted([d for d in dirs if d != '__MACOSX'])
    folder = os.path.relpath(root, FOTO_DIR)
    entries = []
    for fname in sorted(files):
        if fname.startswith('.') or fname.startswith('_'):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext in SKIP_EXTS:
            continue
        rel = os.path.relpath(os.path.join(root, fname), BASE)
        entries.append((fname, normalize(fname), rel))
    if entries:
        folder_photos[folder] = entries

print("Photo folders:")
for k, v in folder_photos.items():
    print(f"  {k}: {len(v)} photos")

# ── tema → folder ─────────────────────────────────────────────────────────────
def get_search_folders(m):
    tema = normalize(m.get('tema') or '')
    r = []
    if any(k in tema for k in ['primeros', 'calcolitico', 'megalit', 'argar', 'bronce',
                                 'tartessos', 'colonizacion', 'iberos', 'roma ',
                                 'romano', 'visigodo', 'bizantino', 'mozarabe']):
        r.append('Tema 9')
    if any(k in tema for k in ['islamico', 'cristiano medieval', 'mudejar',
                                 'gotico', 'tardorromanico', 'medieval']):
        r.append('Tema 10')
    if 'renacimiento' in tema or 'frontera medieval' in tema:
        r.append('Tema 11 RENACIMIENTO')
    if 'barroco' in tema:
        r.append('Tema 11 Barroco')
    if 'ilustracion' in tema:
        r.append('Tema 12 Ilustración')
    if any(k in tema for k in ['s  xix', 'tema 13', 'modernismo', 'eclecticismo',
                                 'regionalismo', 'movimiento moderno', 'racionalismo',
                                 'franquista', 'organicismo', 'posmodernismo',
                                 'ingenieria']):
        r.append('Tema 13 Siglo XX')
    if any(k in tema for k in ['tema 14', 'expo', 'rehabilitacion', 'contemporaneo']):
        r.append('Tema 14')
    if any(k in tema for k in ['tema 15', 'high tech', 'infraestructura', 'espacio publico',
                                 'arq  educativa', 'arq  sanitaria', 'vivienda']):
        r.append('Tema 15')
    if not r:
        r = list(folder_photos.keys())
    return r


NON_PHOTO_WORDS = ['plano', 'planta', 'esquema', 'recreac', 'comparativa',
                   'periodiz', 'evolucion', 'ritual', 'centuriatio', 'organizacion',
                   'nucleos', 'detalle atlas', 'mapa']

def score_match(monument_name, filename):
    mw = key_words(monument_name)
    fw = key_words(filename)

    if not mw or not fw:
        return 0.0

    common = mw & fw
    if not common:
        return 0.0

    mw_specific = specific_words(mw)
    common_specific = specific_words(common)

    # If monument has specific (non-generic) words, require at least one to match
    if mw_specific and not common_specific:
        return 0.0  # No specific words matched — likely false positive

    # Coverage of all monument keywords
    coverage = len(common) / len(mw)

    # Coverage of specific keywords only (if any exist)
    if mw_specific:
        spec_coverage = len(common_specific) / len(mw_specific)
    else:
        spec_coverage = coverage  # All words are generic; use overall coverage

    # Use specific coverage as the primary score
    score = spec_coverage

    # Bonus: ALL keywords matched
    if common == mw:
        score += (0.4 if len(mw) >= 2 else 0.2)

    # Photo extension bonus
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    if ext in ('jpg', 'jpeg', 'webp'):
        score += 0.05

    # Penalty for diagram/plan images
    fn_lower = filename.lower()
    for bad in NON_PHOTO_WORDS:
        if bad in fn_lower:
            score -= 0.5
            break

    return max(0.0, score)

# ── match ─────────────────────────────────────────────────────────────────────
mapping = {}
stats = {'matched': 0, 'unmatched': 0}
THRESHOLD = 0.5

for i, m in enumerate(monumentos):
    nombre = m.get('nombre', '')
    if not nombre:
        stats['unmatched'] += 1
        continue

    folders = get_search_folders(m)
    best_score = 0.0
    best_path = None

    for folder in folders:
        photos = folder_photos.get(folder, [])
        for fname, fnorm, frel in photos:
            s = score_match(nombre, fname)
            if s > best_score:
                best_score = s
                best_path = frel

    if best_score >= THRESHOLD:
        mapping[str(i)] = best_path
        stats['matched'] += 1
    else:
        stats['unmatched'] += 1

print(f"\nMatching: {stats['matched']} matched, {stats['unmatched']} unmatched")

# Show sample matches across ranges
for label, start, end in [("first 40", 0, 40), ("200-220", 200, 220),
                            ("400-420", 400, 420), ("600-620", 600, 620)]:
    print(f"\n--- {label} ---")
    for i in range(start, min(end, len(monumentos))):
        nombre = monumentos[i].get('nombre', '')
        if str(i) in mapping:
            print(f"  [{i:3d}] {nombre[:38]:38s} → {os.path.basename(mapping[str(i)])[:55]}")
        else:
            print(f"  [{i:3d}] {nombre[:38]:38s} → (no match)")

out = os.path.join(BASE, 'foto_mapping.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)
print(f"\nSaved {len(mapping)} mappings → {out}")
