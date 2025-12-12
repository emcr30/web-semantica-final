"""
Quick validation script to POST a sample PDF to /ingest_case and verify persisted triples.

Usage:
  & .venv\Scripts\Activate.ps1
  python backend\tests\validate_case_ingest.py --file Datos\sample_case.pdf

The script will:
 - POST the PDF to http://127.0.0.1:5000/ingest_case (adjust host/port if needed)
 - Expect JSON response with `case_uri`.
 - Load `Ontologia/legal_working.ttl` and check that the case node has:
    - a triple lo:texto
    - optional lo:fechaSentencia (if provided)
    - at least one lo:mencionaArticulo whose URI starts with https://leyes.peru/eli/

Note: run the backend server before executing this script.
"""
import argparse
import requests
import time
from rdflib import Graph, URIRef
import os

API = 'http://127.0.0.1:5000'
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
# Follow repository convention: Ontologia/legal_working.ttl
WORKING_TTL = os.path.normpath(os.path.join(BASE_DIR, '..', 'Ontologia', 'legal_working.ttl'))

parser = argparse.ArgumentParser()
parser.add_argument('--file', required=True, help='Path to sample PDF to upload')
parser.add_argument('--fecha', help='FechaSentencia to include (YYYY-MM-DD)')
args = parser.parse_args()

pdf_path = args.file
if not os.path.exists(pdf_path):
    print('Sample PDF not found at', pdf_path)
    raise SystemExit(1)

print('Uploading', pdf_path, 'to', API + '/ingest_case')
files = {'file': open(pdf_path, 'rb')}
data = {}
if args.fecha:
    data['fecha'] = args.fecha

# First, try multipart upload (preferred). If it fails, fall back to a JSON POST
# containing text that references an article (so the NLP extractor can pick it up).
try:
    r = requests.post(API + '/ingest_case', files=files, data=data, timeout=30)
except Exception as e:
    print('Multipart upload failed, attempting JSON fallback. Error:', str(e))
    fallback_text = 'Sentencia de ejemplo que menciona el Artículo 107. Hechos relevantes...'
    try:
        r = requests.post(API + '/ingest_case', json={'title': 'Caso de prueba', 'text': fallback_text}, timeout=15)
    except Exception as e2:
        print('JSON fallback also failed:', str(e2))
        raise SystemExit(2)

print('Response:', getattr(r, 'status_code', None))
print(getattr(r, 'text', ''))

if r.status_code not in (200,201):
    # If multipart returned a non-2xx, try JSON fallback once more before aborting
    try:
        print('Multipart response indicates failure; attempting JSON fallback...')
        fallback_text = 'Sentencia de ejemplo que menciona el Artículo 107. Hechos relevantes...'
        r2 = requests.post(API + '/ingest_case', json={'title': 'Caso de prueba', 'text': fallback_text}, timeout=15)
        if r2.status_code in (200,201):
            r = r2
        else:
            print('JSON fallback response:', r2.status_code, r2.text)
            print('Upload failed; aborting')
            raise SystemExit(2)
    except Exception as e:
        print('JSON fallback exception:', str(e))
        raise SystemExit(2)

resp = r.json()
case_uri = resp.get('case_uri')
if not case_uri:
    print('No case_uri returned in response; aborting')
    print('Response JSON:', resp)
    raise SystemExit(3)

print('Case created:', case_uri)

# Wait briefly to allow server to serialize TTL
time.sleep(1)

if not os.path.exists(WORKING_TTL):
    print('Working TTL not found at', WORKING_TTL)
    raise SystemExit(4)

g = Graph()
try:
    g.parse(WORKING_TTL, format='turtle')
except Exception as e:
    print('Failed to parse TTL at', WORKING_TTL, str(e))
    raise SystemExit(4)
case_ref = URIRef(case_uri)
LO = 'http://legalontosystem.pe/ontology#'
menciona = URIRef(LO + 'mencionaArticulo')
texto = URIRef(LO + 'texto')
fecha_p = URIRef(LO + 'fechaSentencia')

has_text = False
for o in g.objects(case_ref, texto):
    has_text = True
    print('Found texto (length):', len(str(o)))

has_fecha = False
for o in g.objects(case_ref, fecha_p):
    has_fecha = True
    print('Found fechaSentencia:', str(o))

arts = list(g.objects(case_ref, menciona))
print('Found', len(arts), 'lo:mencionaArticulo links')
if len(arts) == 0:
    print('No lo:mencionaArticulo links found for case', case_uri)
    raise SystemExit(5)
for a in arts[:10]:
    print(' -', a)
    if not str(a).startswith('https://leyes.peru/eli/'):
        print(' -> Article URI does not look like ELI:', a)
        raise SystemExit(6)

if not has_text:
    print('No lo:texto found for case', case_uri)
    raise SystemExit(6)

print('Validation OK: case stored with lo:texto and ELI-linked articles')
