"""Migración de namespace para legal_working.ttl
Convierte sujetos con base `http://example.org/legal/` a `http://legalontosystem.pe/resource/`
Y convierte predicados/objetos con namespace `http://example.org/legal#` a `http://legalontosystem.pe/ontology#`.
Hace backup del archivo original a `legal_working.ttl.bak`.
"""
from rdflib import Graph, URIRef, Namespace, Literal
import os

BASE = os.path.dirname(os.path.dirname(__file__))
WORKING = os.path.join(BASE, 'Ontologia', 'legal_working.ttl')
BACKUP = WORKING + '.bak'
OLD_SUBJ_BASE = 'http://example.org/legal/'
OLD_PRED_BASE = 'http://example.org/legal#'
NEW_RESOURCE_BASE = 'http://legalontosystem.pe/resource/'
NEW_ONT_BASE = 'http://legalontosystem.pe/ontology#'

print('Loading', WORKING)
g = Graph()
try:
    g.parse(WORKING, format='turtle')
except Exception as e:
    print('Failed to parse TTL:', e)
    raise

newg = Graph()
# bind ontology prefix
newg.bind('', Namespace(NEW_ONT_BASE))
newg.bind('rdfs', Namespace('http://www.w3.org/2000/01/rdf-schema#'))

count = 0
for s,p,o in g:
    s_new = s
    p_new = p
    o_new = o
    # subject conversion
    try:
        if isinstance(s, URIRef) and str(s).startswith(OLD_SUBJ_BASE):
            s_new = URIRef(str(s).replace(OLD_SUBJ_BASE, NEW_RESOURCE_BASE, 1))
    except Exception:
        pass
    # predicate conversion
    try:
        if isinstance(p, URIRef) and str(p).startswith(OLD_PRED_BASE):
            local = str(p)[len(OLD_PRED_BASE):]
            p_new = URIRef(NEW_ONT_BASE + local)
    except Exception:
        pass
    # object conversion if URI
    try:
        if isinstance(o, URIRef) and str(o).startswith(OLD_SUBJ_BASE):
            o_new = URIRef(str(o).replace(OLD_SUBJ_BASE, NEW_RESOURCE_BASE, 1))
        elif isinstance(o, URIRef) and str(o).startswith(OLD_PRED_BASE):
            local = str(o)[len(OLD_PRED_BASE):]
            o_new = URIRef(NEW_ONT_BASE + local)
    except Exception:
        pass
    newg.add((s_new, p_new, o_new))
    count += 1

# backup original
if os.path.exists(BACKUP):
    print('Backup already exists at', BACKUP)
else:
    os.rename(WORKING, BACKUP)
    print('Original backed up to', BACKUP)

newg.serialize(destination=WORKING, format='turtle')
print('Migrated', count, 'triples; updated file:', WORKING)
print('If you are running a local server, restart it to pick up changes.')
