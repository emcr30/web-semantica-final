from flask import Flask, request, jsonify
from flask_cors import CORS
import rdflib
from rdflib import Graph
import os
import requests
from werkzeug.utils import secure_filename
import datetime
from backend import rdf_builder, reasoner, ingest_peru_api, sparql_queries, contradiction_detector
from backend import dataset_ingest
from backend import precedent_processor

APP = Flask(__name__)
CORS(APP)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ONTO_PATH = os.path.join(BASE_DIR, 'Ontologia', 'legalontosystem_peru.ttl')
WORKING_TTL = os.path.join(BASE_DIR, 'Ontologia', 'legal_working.ttl')

# Load or create graph
GRAPH = Graph()
try:
    GRAPH.parse(ONTO_PATH, format='turtle')
except Exception:
    GRAPH = Graph()
# Also load working data (generated triples) if present so endpoints see existing laws
try:
    if os.path.exists(WORKING_TTL):
        GRAPH.parse(WORKING_TTL, format='turtle')
except Exception as e:
    # don't crash the app on startup; log for debugging
    print(f"Warning: failed loading working TTL '{WORKING_TTL}': {e}")

@APP.route('/ingest', methods=['POST'])
def ingest():
    data = request.json or {}
    # If `text` provided we create a law individual from raw text
    if 'text' in data:
        law_id = data.get('id', 'LEY_' + str(abs(hash(data.get('text'))) % 100000))
        title = data.get('title', 'Ley importada')
        jurisdiction = data.get('jurisdiccion', 'Peru')
        rdf_builder.create_law(GRAPH, law_id, title, data['text'], jurisdiction)
        GRAPH.serialize(destination=WORKING_TTL, format='turtle')
        # attempt GraphDB upload if configured
        upload_result = None
        try:
            base = os.path.dirname(os.path.dirname(__file__))
            cfg_path = os.path.join(base, 'backend', 'graphdb_config.json')
            if os.path.exists(cfg_path):
                import json
                with open(cfg_path,'r',encoding='utf8') as fh:
                    cfg = json.load(fh)
                from backend.graphdb_upload import upload_ttl
                out = WORKING_TTL
                upload_result = upload_ttl(cfg, out)
        except Exception as e:
            upload_result = { 'ok': False, 'error': str(e) }
        return jsonify({'status':'ok','id':law_id,'upload': upload_result}), 201

    # Otherwise, attempt to fetch from Peruvian API (placeholder)
    if 'fetch' in data:
        api_key = data.get('api_key')
        query = data.get('query', '')
        laws = ingest_peru_api.fetch_laws_from_api(api_key, query)
        created = []
        for law in laws:
            law_id = law.get('id') or ('LEY_' + str(abs(hash(law.get('title','')))%100000))
            rdf_builder.create_law(GRAPH, law_id, law.get('title',''), law.get('text',''), law.get('jurisdiccion','Peru'))
            created.append(law_id)
        GRAPH.serialize(destination=WORKING_TTL, format='turtle')
        # no automatic upload here; dataset_ingest will handle upload if config exists
        return jsonify({'status':'ok','created':created}), 201

    return jsonify({'error':'payload must contain `text` or `fetch` flag'}), 400

@APP.route('/search', methods=['GET'])
def search():
    q = request.args.get('q','')
    if not q:
        return jsonify({'error':'q parameter required'}), 400
    query = sparql_queries.search_laws_by_text(q)
    res = GRAPH.query(query)
    results = []
    for row in res:
        results.append({ 'law': str(row.law), 'title': str(row.title) })
    return jsonify(results)

@APP.route('/reason', methods=['POST'])
def run_reasoner():
    # Apply OWL-RL reasoning (in-memory) and persist
    reasoner.apply_owlrl(GRAPH)
    GRAPH.serialize(destination=WORKING_TTL, format='turtle')
    return jsonify({'status':'inferred_saved','path':WORKING_TTL})

@APP.route('/sparql', methods=['POST'])
def sparql_endpoint():
    data = request.json or {}
    query = data.get('query')
    if not query:
        return jsonify({'error':'query required'}), 400
    # tolerate JSON-escaped newlines (e.g. "\\n") coming from some clients/tests
    if isinstance(query, str) and '\\n' in query:
        query = query.replace('\\n', '\n')

    # basic validation and defensive logging to catch parse issues
    if not isinstance(query, str):
        return jsonify({'error': 'query must be a string', 'type': str(type(query)), 'repr': repr(query)[:1000]}), 400

    try:
        res = GRAPH.query(query)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # print to stderr so logs capture the full context
        print('SPARQL execution error; query preview:', repr(query)[:1000])
        print(tb)
        # return a helpful error to the client (preview limited)
        return jsonify({'error': 'query_error', 'message': str(e), 'query_preview': repr(query)[:1000]}), 500

    # convert to JSON-friendly (stringify variable names)
    vars = [str(v) for v in res.vars]
    rows = []
    for r in res:
        rows.append({ vars[i]: str(r[i]) for i in range(len(vars)) })
    return jsonify({'head':vars,'results':rows})

@APP.route('/detect_contradictions', methods=['GET'])
def detect_contradictions():
    issues = contradiction_detector.find_contradictions(GRAPH)
    return jsonify({'contradictions': issues})


@APP.route('/precedents_for_article', methods=['GET'])
def precedents_for_article():
    uri = request.args.get('uri')
    if not uri:
        return jsonify({'error':'uri param required (article URI)'}), 400
    jurisdiction = request.args.get('jurisdiccion')
    year = request.args.get('year')
    limit = int(request.args.get('limit') or 50)
    try:
        res = precedent_processor.find_cases_for_article(GRAPH, uri, jurisdiction=jurisdiction, year=year, limit=limit)
        return jsonify({'uri': uri, 'results': res})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@APP.route('/semantic_search', methods=['GET'])
def semantic_search():
    q = request.args.get('q')
    if not q:
        return jsonify({'error':'q parameter required'}), 400
    # optional filters
    year = request.args.get('year')
    jurisd = request.args.get('jurisdiccion')
    tipo = request.args.get('tipo')
    limit = int(request.args.get('limit') or 50)
    # Basic strategy: combine SPARQL matches on rdfs:label and lo:texto, then score by heuristics
    # Use sparql_queries.search_laws_by_text for base results (it now targets lo: namespace)
    try:
        base_q = sparql_queries.search_laws_by_text(q)
        res = GRAPH.query(base_q)
        results = []
        for row in res:
            law = str(row.law)
            title = str(row.title)
            score = 1.0
            # boost if jurisdiction matches
            try:
                qj = f"PREFIX lo: <http://legalontosystem.pe/ontology#> SELECT ?j WHERE {{ <{law}> lo.aplicaEn ?j }} LIMIT 1"
                jur = None
                for r in GRAPH.query(qj):
                    jur = str(r.j) if hasattr(r, 'j') else (str(r[0]) if len(r)>0 else None)
                if jurisd and jur and jurisd.lower() in jur.lower():
                    score *= 1.5
            except Exception:
                pass
            # penalize if law deroga many others? (simple heuristic)
            try:
                qd = f"PREFIX lo: <http://legalontosystem.pe/ontology#> SELECT (COUNT(?x) as ?c) WHERE {{ <{law}> lo.deroga ?x }}"
                for r in GRAPH.query(qd):
                    c = int(str(r.c)) if r.c else 0
                    if c>0:
                        score *= 1.0  # neutral for now, keep placeholder
            except Exception:
                pass
            results.append({ 'law': law, 'title': title, 'score': score })
        # sort
        results = sorted(results, key=lambda x: x['score'], reverse=True)[:limit]
        return jsonify({'query': q, 'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@APP.route('/link_article_mentions', methods=['POST'])
def link_article_mentions_endpoint():
    data = request.json or {}
    case_uri = data.get('case_uri') or data.get('uri')
    text = data.get('text')
    if not case_uri:
        return jsonify({'error':'case_uri required'}), 400
    try:
        res = precedent_processor.link_article_mentions(GRAPH, case_uri, case_text=text, persist=True)
        # persist graph
        GRAPH.serialize(destination=WORKING_TTL, format='turtle')
        return jsonify({'status':'ok','result': res}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@APP.route('/ingest_csv', methods=['POST'])
def ingest_csv():
    # Accept either a multipart file upload (field name 'file') or JSON {"url": "..."}
    try:
        # File upload handling
        if 'file' in request.files:
            f = request.files['file']
            if f.filename == '':
                return jsonify({'error':'empty filename'}), 400
            filename = secure_filename(f.filename)
            # add timestamp to filename to avoid overwriting existing files
            name, ext = os.path.splitext(filename)
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename_ts = f"{name}_{ts}{ext}"
            base = os.path.dirname(os.path.dirname(__file__))
            save_dir = os.path.join(base, 'Datos')
            os.makedirs(save_dir, exist_ok=True)
            out_path = os.path.join(save_dir, filename_ts)
            f.save(out_path)
            result = dataset_ingest.ingest_csv_url_into_graph(GRAPH, out_path, limit=200)
            return jsonify({'status':'ok','saved_as': filename_ts, 'result': result}), 201

        # Fallback to JSON body with a `url` key
        data = request.json or {}
        url = data.get('url')
        if not url:
            return jsonify({'error':'url or file required'}), 400
        result = dataset_ingest.ingest_csv_url_into_graph(GRAPH, url, limit=200)
        return jsonify({'status':'ok','result': result}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@APP.route('/entity', methods=['GET'])
def entity():
    uri = request.args.get('uri')
    if not uri:
        return jsonify({'error':'uri param required'}), 400
    # build SPARQL to get all properties for subject
    q = f"SELECT ?p ?o WHERE {{ <{uri}> ?p ?o }} LIMIT 1000"
    try:
        res = GRAPH.query(q)
        rows = []
        for r in res:
            rows.append({ 'p': str(r[0]), 'o': str(r[1]) })
        return jsonify({'uri':uri,'properties':rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@APP.route('/fetch_url_debug', methods=['POST'])
def fetch_url_debug():
    """Debug endpoint: POST {url: '...'}
    Returns status code, headers and a small content preview to help diagnose 404/403 issues.
    """
    data = request.json or {}
    url = data.get('url')
    if not url:
        return jsonify({'error':'url required'}), 400
    try:
        headers = {'User-Agent': 'LegalOntoSystem/1.0 (+https://example.org)'}
        r = requests.get(url, timeout=30, headers=headers, allow_redirects=True)
        out = {
            'status_code': r.status_code,
            'headers': {k:v for k,v in r.headers.items()},
            'content_preview': (r.text[:2000] if isinstance(r.text, str) else str(r.content[:2000]))
        }
        return jsonify(out)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    APP.run(debug=True)
