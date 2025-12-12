"""
Utility: ingest a local PDF file path into the RDF graph using the same logic
as `/ingest_pdf` but without requiring multipart upload. Useful when file
permissions prevent the Flask process from saving uploads.

Usage:
    .venv\Scripts\python.exe ingest_from_path.py "C:\...\CODIGOPENAL.pdf" CP_635_SCRIPT

This will parse ontology + working TTL, process the PDF (extract text, chunk,
run NLP), persist a parent Documento with full text and parts, link mencionaArticulo,
serialize `Ontologia/legal_working.ttl`.
"""
import sys
import os
import hashlib
from rdflib import Graph, URIRef, Literal, RDF, RDFS

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ONTO_PATH = os.path.join(BASE_DIR, 'Ontologia', 'legalontosystem_peru.ttl')
WORKING_TTL = os.path.join(BASE_DIR, 'Ontologia', 'legal_working.ttl')

if len(sys.argv) < 2:
    print('Usage: python ingest_from_path.py <pdf_path> [doc_id]')
    sys.exit(1)

pdf_path = sys.argv[1]
doc_id = sys.argv[2] if len(sys.argv) > 2 else ('DOC_' + __import__('datetime').datetime.now().strftime('%Y%m%d%H%M%S'))

# make sure workspace root is on sys.path so `import backend` works when running
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend import pdf_processor, nlp_extractor
from backend.nlp_chunker import chunk_text

if not os.path.exists(pdf_path):
    print('PDF not found:', pdf_path)
    sys.exit(2)

# Load graph
G = Graph()
try:
    G.parse(ONTO_PATH, format='turtle')
except Exception:
    G = Graph()
if os.path.exists(WORKING_TTL):
    try:
        G.parse(WORKING_TTL, format='turtle')
    except Exception as e:
        print('Warning: failed to parse working ttl:', e)

# Extract text
print('Extracting text...')
text = pdf_processor.extract_text_from_pdf(pdf_path)
print('Text length:', len(text))

# Chunk and run NLP
chunks = list(chunk_text(text, max_len=100000, overlap=2000))
print('Chunks:', len(chunks))
aggregated = {'articles': [], 'laws': [], 'entities': [], 'keywords': []}
seen_articles = set(); seen_laws=set(); seen_entities=set(); seen_keywords=set()
for start, chunk in chunks:
    sub = nlp_extractor.extract_entities(chunk)
    for a in (sub.get('articles') or []):
        if a not in seen_articles:
            seen_articles.add(a); aggregated['articles'].append(a)
    for l in (sub.get('laws') or []):
        if l not in seen_laws:
            seen_laws.add(l); aggregated['laws'].append(l)
    for k in (sub.get('keywords') or []):
        if k not in seen_keywords:
            seen_keywords.add(k); aggregated['keywords'].append(k)
    for e in (sub.get('entities') or []):
        key = (e.get('text','').strip().lower(), e.get('label'))
        if key not in seen_entities:
            seen_entities.add(key); aggregated['entities'].append(e)

print('Aggregated articles:', aggregated['articles'][:10])

# Persist
from backend.rdf_builder import ensure_namespaces
ensure_namespaces(G)
RESOURCE_BASE = 'http://legalontosystem.pe/resource/'
checksum_prop = URIRef('http://legalontosystem.pe/ontology#checksum')
full_checksum_prop = URIRef('http://legalontosystem.pe/ontology#fullChecksum')

created = []
skipped = []
part_subjects = {}

# Create parent with full text if not existing by full checksum
full_sha = hashlib.sha256(text.encode('utf8')).hexdigest()
parent_uri = URIRef(RESOURCE_BASE + doc_id)
existing_parent = None
for s in G.subjects(full_checksum_prop, Literal(full_sha)):
    existing_parent = s
    break

if existing_parent is not None:
    print('Existing parent found:', existing_parent)
    created.append(str(existing_parent))
else:
    G.add((parent_uri, RDF.type, URIRef('http://legalontosystem.pe/ontology#Documento')))
    G.add((parent_uri, RDFS.label, Literal(os.path.basename(pdf_path))))
    G.add((parent_uri, URIRef('http://legalontosystem.pe/ontology#texto'), Literal(text)))
    G.add((parent_uri, full_checksum_prop, Literal(full_sha)))
    created.append(str(parent_uri))

# Parts
for idx, (start, chunk) in enumerate(chunks, start=1):
    sha = hashlib.sha256(chunk.encode('utf8')).hexdigest()
    existing = None
    for s in G.subjects(checksum_prop, Literal(sha)):
        existing = s
        skipped.append(str(s))
        break
    if existing is not None:
        # ensure parent link
        G.add((parent_uri, URIRef('http://legalontosystem.pe/ontology#tieneParte'), existing))
        part_subjects[sha] = existing
    else:
        part_id = f"{doc_id}_part{idx}"
        doc_uri = URIRef(RESOURCE_BASE + part_id)
        G.add((doc_uri, RDF.type, URIRef('http://legalontosystem.pe/ontology#Documento')))
        G.add((doc_uri, RDFS.label, Literal(f"{os.path.basename(pdf_path)} (parte {idx})")))
        G.add((doc_uri, URIRef('http://legalontosystem.pe/ontology#texto'), Literal(chunk)))
        G.add((doc_uri, checksum_prop, Literal(sha)))
        G.add((parent_uri, URIRef('http://legalontosystem.pe/ontology#tieneParte'), doc_uri))
        created.append(str(doc_uri))
        part_subjects[sha] = doc_uri

# Link mentions
menciona_prop = URIRef('http://legalontosystem.pe/ontology#mencionaArticulo')
for art in aggregated.get('articles', []):
    art_num = ''.join(ch for ch in str(art) if ch.isdigit())
    if not art_num:
        continue
    try:
        # import helper from app if available (best-effort)
        try:
            from backend.app import _eli_article_uri
            art_uri = URIRef(_eli_article_uri(art_num, G))
        except Exception:
            art_uri = URIRef(f'https://leyes.peru/eli/1991/codigo-penal/articulo/{art_num}')
        # assert LKIF type for articles
        try:
            LKIF = 'http://www.estrellaproject.org/lkif-core/legal-rule.owl#'
            G.add((art_uri, RDF.type, URIRef(LKIF + 'LegalRule')))
        except Exception:
            pass
        G.add((parent_uri, menciona_prop, art_uri))
        for sha, subj in part_subjects.items():
            sref = subj if hasattr(subj, 'n3') else URIRef(str(subj))
            G.add((sref, menciona_prop, art_uri))
    except Exception:
        continue

# Serialize
G.serialize(destination=WORKING_TTL, format='turtle')
print('Done. Created:', len(created), 'Skipped:', len(skipped))
print('Parent:', parent_uri)
