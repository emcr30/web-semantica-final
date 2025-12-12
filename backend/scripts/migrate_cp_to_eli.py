"""
Migration script to convert Código Penal URIs to ELI URIs and save migrated graph.

Replaces subjects and objects that use:
 - http://codigopenal.pe/  -> https://leyes.peru/eli/codigo-penal/<year>
 - http://codigopenal.pe/articulo/<num> -> https://leyes.peru/eli/codigo-penal/<year>/articulo/<num>

Saves output to `data/cp_eli.ttl` (creates `data/` if needed).

Usage:
  & .venv\Scripts\Activate.ps1
  python backend\scripts\migrate_cp_to_eli.py

The script backs up the original `Ontologia/legal_working.ttl` to `Ontologia/legal_working.ttl.bak`.
"""
import os
import re
from rdflib import Graph, URIRef, Literal

BASE = os.path.dirname(os.path.dirname(__file__))
WORKING = os.path.join(BASE, '..', 'Ontologia', 'legal_working.ttl')
WORKING = os.path.normpath(WORKING)
BACKUP = WORKING + '.bak'
OUT_DIR = os.path.join(os.path.dirname(BASE), 'data')
OUT_FILE = os.path.join(OUT_DIR, 'cp_eli.ttl')

OLD_BASE = 'http://codigopenal.pe/'
OLD_ART_BASE = 'http://codigopenal.pe/articulo/'

if not os.path.exists(WORKING):
    print('Working TTL not found at', WORKING)
    raise SystemExit(1)

print('Loading graph...')
g = Graph()
try:
    g.parse(WORKING, format='turtle')
except Exception as e:
    print('Failed to parse TTL:', e)
    raise

# detect year from codigo_penal resource or dct:issued/lo:anio values
year = None
try:
    for s, o in g.subject_objects():
        try:
            text = str(o).lower()
            if 'código penal' in text or 'codigo penal' in text:
                # find year nearby on subject
                for p2, o2 in g.predicate_objects(subject=s):
                    m = re.search(r'(19|20)\d{2}', str(o2))
                    if m:
                        year = m.group(0)
                        break
                if year:
                    break
        except Exception:
            continue
except Exception:
    pass

# try dcterms issued global search
if not year:
    try:
        for s,p,o in g.triples((None, None, None)):
            m = re.search(r'(19|20)\d{2}', str(o))
            if m:
                # heuristic: choose first reasonable year between 1900 and 2025
                y = int(m.group(0))
                if 1900 <= y <= 2025:
                    year = str(y)
                    break
    except Exception:
        pass

if not year:
    print('Year not detected, defaulting to 1991')
    year = '1991'
else:
    print('Detected year:', year)

ELI_BASE = f'https://leyes.peru/eli/{year}/codigo-penal'
print('ELI base will be:', ELI_BASE)

newg = Graph()
# copy namespaces
for prefix, ns in g.namespaces():
    try:
        newg.bind(prefix, ns)
    except Exception:
        pass

# helper
def migrate_uri(u: str) -> URIRef:
    if not isinstance(u, str):
        return u
    if u.startswith(OLD_ART_BASE):
        num = u[len(OLD_ART_BASE):]
        return URIRef(f"{ELI_BASE}/articulo/{num}")
    if u == OLD_BASE:
        return URIRef(ELI_BASE)
    if u.startswith(OLD_BASE):
        # other paths under old base -> map to ELI base
        suffix = u[len(OLD_BASE):]
        return URIRef(f"{ELI_BASE}/{suffix}")
    return URIRef(u)

print('Transforming triples...')
for s,p,o in g:
    s_new = migrate_uri(str(s)) if isinstance(s, URIRef) or isinstance(s, str) else s
    # object may be URIRef or Literal/BNode
    if isinstance(o, URIRef) or (isinstance(o, str) and (o.startswith(OLD_BASE) or o.startswith(OLD_ART_BASE))):
        o_new = migrate_uri(str(o))
    else:
        o_new = o
    newg.add((s_new, p, o_new))

# backup and write out
print('Backing up original TTL ->', BACKUP)
try:
    import shutil
    shutil.copy2(WORKING, BACKUP)
except Exception as e:
    print('Warning: could not backup original TTL (copy failed):', e)

os.makedirs(OUT_DIR, exist_ok=True)
print('Serializing migrated graph to', OUT_FILE)
newg.serialize(destination=OUT_FILE, format='turtle')
print('Migration complete. Migrated TTL at', OUT_FILE)
print('Note: working TTL backed up at', BACKUP)
