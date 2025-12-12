import sys
import os
from rdflib import Graph
# add repo root to path
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
# import module
from backend import precedent_processor

# load TTL
g = Graph()
working = os.path.join(ROOT, 'Ontologia', 'legal_working.ttl')
print('loading', working)
g.parse(working, format='turtle')

article_uri = 'https://leyes.peru/eli/1991/codigo-penal/articulo/189'
res = precedent_processor.find_cases_for_article(g, article_uri, limit=50)
print('found', len(res), 'results')
for r in res:
    print(r)
