"""
Migration helper: replace old `http://codigopenal.pe/` and `http://codigopenal.pe/articulo/` URIs
with ELI URIs `https://leyes.peru/eli/{year}/codigo-penal` and article URIs.

Usage: run from project root venv: `python backend/migrate_cp_to_eli.py`
It will backup `Ontologia/legal_working.ttl` to `.bak` and write the migrated TTL.
"""
import os
from rdflib import Graph, URIRef, Literal
import re

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
WORKING_TTL = os.path.join(BASE_DIR, 'Ontologia', 'legal_working.ttl')
BACKUP = WORKING_TTL + '.bak'

if not os.path.exists(WORKING_TTL):
    print('No working TTL found at', WORKING_TTL)
    exit(1)

print('Loading graph...')
g = Graph()
try:
    g.parse(WORKING_TTL, format='turtle')
except Exception as e:
    print('Failed to parse TTL:', e)
    exit(2)

# try detect year from existing codigo_penal resource
year = '1991'
for s,l in g.subject_objects():
    try:
        if 'código penal' in str(l).lower() or 'codigo penal' in str(l).lower():
            # try find date nearby
            y = None
            # search for dct:issued or lo:anio
            for p,o in g.predicate_objects(subject=s):
                if isinstance(o, Literal) and re.search(r"(19|20)\d{2}", str(o)):
                    y = re.search(r"(19|20)\d{2}", str(o)).group(0)
                    break
            if y:
                year = y
                break
    except Exception:
        pass

ELI_BASE = f'https://leyes.peru/eli/{year}/codigo-penal'
OLD_BASE = 'http://codigopenal.pe/'
OLD_ART_BASE = 'http://codigopenal.pe/articulo/'

print('Detected year:', year)
print('Creating migrated graph...')
newg = Graph()
# copy namespaces
for prefix, ns in g.namespaces():
    newg.bind(prefix, ns)

for s,p,o in g:
    s_str = str(s)
    o_new = o
    s_new = s
    if s_str.startswith(OLD_ART_BASE):
        art_num = s_str.split(OLD_ART_BASE)[-1]
        s_new = URIRef(f"{ELI_BASE}/articulo/{art_num}")
    elif s_str == OLD_BASE:
        s_new = URIRef(ELI_BASE)
    else:
        s_new = s

    # object
    if isinstance(o, URIRef) or (hasattr(o, 'startswith') and isinstance(o, str) and o.startswith(OLD_ART_BASE)):
        o_str = str(o)
        if o_str.startswith(OLD_ART_BASE):
            art_num = o_str.split(OLD_ART_BASE)[-1]
            o_new = URIRef(f"{ELI_BASE}/articulo/{art_num}")
        elif o_str == OLD_BASE:
            o_new = URIRef(ELI_BASE)
        else:
            o_new = o
    # add triple
    newg.add((s_new, p, o_new))

# backup and save
print('Backing up', WORKING_TTL, '->', BACKUP)
os.rename(WORKING_TTL, BACKUP)
print('Serializing migrated TTL...')
newg.serialize(destination=WORKING_TTL, format='turtle')
print('Done. Original backed up as', BACKUP)
