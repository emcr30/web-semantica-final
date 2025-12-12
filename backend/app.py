from flask import Flask, request, jsonify
from flask import send_from_directory
from flask_cors import CORS
import rdflib
from rdflib import Graph
from rdflib import URIRef
from rdflib.namespace import RDFS, RDF
import os
import requests
from werkzeug.utils import secure_filename
import datetime
from backend import rdf_builder, reasoner, ingest_peru_api, sparql_queries, contradiction_detector
from backend import dataset_ingest
from backend import precedent_processor
from backend import nlp_extractor
from backend import pdf_processor
from backend.nlp_chunker import chunk_text
import hashlib

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


def _find_codigo_penal_year(g: Graph, default_year: int = 1991) -> int:
    """Attempt to find the year of the loaded Código Penal in the graph.
    Strategy: look for resources with label/title containing 'código penal' and try
    to extract a 4-digit year from rdfs:label, lo:anio, dct:issued or the URI.
    Falls back to `default_year` if none found.
    """
    import re
    candidates = []
    try:
        # search labels
        for s, l in g.subject_objects(RDFS.label):
            if l and 'código penal' in str(l).lower():
                candidates.append((s, str(l)))
    except Exception:
        pass

    # also try lo:titulo
    LO = URIRef('http://legalontosystem.pe/ontology#')
    try:
        for s, t in g.subject_objects(URIRef(str(LO) + 'titulo')):
            if t and 'código penal' in str(t).lower():
                candidates.append((s, str(t)))
    except Exception:
        pass

    # try to extract year from candidate labels or URIs
    for subj, text in candidates:
        # look for 4-digit year
        m = re.search(r"(19|20)\d{2}", text)
        if m:
            try:
                return int(m.group(0))
            except Exception:
                pass
        # try to inspect known properties like lo:anio or dct:issued
        try:
            y = g.value(subj, URIRef(str(LO) + 'anio')) or g.value(subj, URIRef('http://purl.org/dc/terms/issued'))
            if y:
                ym = re.search(r"(19|20)\d{2}", str(y))
                if ym:
                    return int(ym.group(0))
        except Exception:
            pass
        # try year in URI
        try:
            u = str(subj)
            m2 = re.search(r"(19|20)\d{2}", u)
            if m2:
                return int(m2.group(0))
        except Exception:
            pass

    return default_year


def _eli_article_uri(article_num: str, g: Graph) -> str:
    """Return an ELI-style URI for a Código Penal article using the detected year.
    Example: https://leyes.peru/eli/1991/codigo-penal/articulo/124
    """
    art_num = ''.join(ch for ch in str(article_num) if ch.isdigit())
    if not art_num:
        raise ValueError('article number not found')
    year = _find_codigo_penal_year(g)
    return f"https://leyes.peru/eli/{year}/codigo-penal/articulo/{art_num}"

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
    # Try SPARQL-based search first; if parser fails (rdflib/pyparsing issues),
    # fall back to a graph-scan text search to keep the UI working.
    try:
        query = sparql_queries.search_laws_by_text(q)
        res = GRAPH.query(query)
        results = []
        # detect parts (objects of lo:tieneParte)
        LO = URIRef('http://legalontosystem.pe/ontology#')
        tiene_parte = URIRef(str(LO) + 'tieneParte')
        part_objs = set(o for s,p,o in GRAPH.triples((None, tiene_parte, None)))
        for row in res:
            subj = getattr(row, 'law', None) or (row[0] if len(row)>0 else None)
            title = getattr(row, 'title', None) or (row[1] if len(row)>1 else None)
            subj_uri = str(subj) if subj is not None else None
            is_part = False
            try:
                is_part = (URIRef(subj_uri) in part_objs)
            except Exception:
                is_part = False
            results.append({ 'law': subj_uri, 'title': str(title) if title is not None else subj_uri, 'is_part': bool(is_part) })
        return jsonify(results)
    except Exception as e:
        # Fallback: scan graph literals for the query term (case-insensitive)
        term = q.lower()
        LO = URIRef('http://legalontosystem.pe/ontology#')
        candidates = set()
        # properties to search in
        props = [RDFS.label, URIRef(str(LO) + 'titulo'), URIRef(str(LO) + 'texto'), URIRef(str(LO) + 'contenido')]
        for s,p,o in GRAPH.triples((None, None, None)):
            if isinstance(o, rdflib.Literal) and term in str(o).lower():
                candidates.add(s)

        results = []
        # detect parts
        tiene_parte = URIRef(str(LO) + 'tieneParte')
        part_objs = set(o for s,p,o in GRAPH.triples((None, tiene_parte, None)))
        for subj in list(candidates)[:200]:
            # determine a display title
            title = GRAPH.value(subj, RDFS.label) or GRAPH.value(subj, URIRef(str(LO) + 'titulo')) or GRAPH.value(subj, URIRef(str(LO) + 'texto'))
            is_part = subj in part_objs
            results.append({ 'law': str(subj), 'title': str(title) if title else str(subj), 'is_part': bool(is_part) })
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
    try:
        issues = contradiction_detector.find_contradictions(GRAPH)
        return jsonify({'contradictions': issues})
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print('Contradiction detection error:', tb)
        return jsonify({'error': 'contradiction_detection_failed', 'message': str(e)}), 500


@APP.route('/list_resources', methods=['GET'])
def list_resources():
    """Return a list of resources of types lo:Ley, lo:Articulo, lo:Documento with labels."""
    LO = URIRef('http://legalontosystem.pe/ontology#')
    # By default, only return Ley and Articulo. If client requests include_docs=1, include Documento.
    types = [URIRef(str(LO) + 'Ley'), URIRef(str(LO) + 'Articulo')]
    if request.args.get('include_docs') == '1':
        types.append(URIRef(str(LO) + 'Documento'))
    items = []
    # detect parts: objects of lo:tieneParte
    tiene_parte = URIRef(str(LO) + 'tieneParte')
    part_objs = set(o for s,p,o in GRAPH.triples((None, tiene_parte, None)))

    for t in types:
        for s in GRAPH.subjects(RDF.type, t):
            # skip any subject that is a Documento unless client explicitly asked for documents
            if (s, RDF.type, URIRef(str(LO) + 'Documento')) in GRAPH and request.args.get('include_docs') != '1':
                continue
            # skip internal 'resource' namespace (documents and parts) unless explicitly requested
            if request.args.get('include_docs') != '1' and str(s).startswith('http://legalontosystem.pe/resource/'):
                continue
            label = GRAPH.value(s, RDFS.label) or GRAPH.value(s, URIRef(str(LO) + 'titulo'))
            is_part = s in part_objs
            items.append({'uri': str(s), 'title': str(label) if label else str(s), 'is_part': bool(is_part)})
    # As an extra safety, filter out any resource namespace entries unless explicitly requested
    if request.args.get('include_docs') != '1':
        items = [i for i in items if not i['uri'].startswith('http://legalontosystem.pe/resource/')]
    return jsonify({'count': len(items), 'results': items})


@APP.route('/reload_working', methods=['POST'])
def reload_working():
    """Reload the ONTO + working TTL into the in-memory GRAPH. Useful for tests.
    """
    global GRAPH
    try:
        newg = Graph()
        try:
            newg.parse(ONTO_PATH, format='turtle')
        except Exception:
            newg = Graph()
        if os.path.exists(WORKING_TTL):
            newg.parse(WORKING_TTL, format='turtle')
        GRAPH = newg
        return jsonify({'status':'reloaded'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@APP.route('/ingest_case', methods=['POST'])
def ingest_case():
    """Create a `lo:Caso` resource from JSON {title, text, fecha, jurisdiccion}.
    Runs the NLP extractor to detect mentioned articles and links them to the case.
    """
    # support either multipart form with a PDF file OR JSON body
    print('== Incoming request: /ingest_case ==')
    try:
        print('Content-Type:', request.content_type)
        print('Headers:', dict(request.headers))
        print('Form:', request.form.to_dict())
        print('Files:', list(request.files.keys()))
    except Exception as _e:
        print('ingest_case: failed to log request metadata:', str(_e))

    title = None
    text = None
    fecha = None
    jurisd = None

    # Prefer multipart file upload when present
    if 'file' in request.files:
        f = request.files['file']
        print('ingest_case: received file upload:', getattr(f, 'filename', None))
        if f and f.filename:
            filename = secure_filename(f.filename)
            base = os.path.dirname(os.path.dirname(__file__))
            save_dir = os.path.join(base, 'Datos')
            os.makedirs(save_dir, exist_ok=True)
            out_path = os.path.join(save_dir, filename)
            f.save(out_path)
            # remember saved filename to persist on case node later
            saved_filename = filename
            try:
                text = pdf_processor.extract_text_from_pdf(out_path)
                # Extract case metadata (title, department, chamber, crime labels)
                try:
                    meta = nlp_extractor.extract_case_metadata(text)
                    # override title if metadata title found
                    if meta.get('title'):
                        title = meta.get('title')
                    # set jurisdiction if department detected
                    if meta.get('department') and not jurisd:
                        jurisd = meta.get('department')
                    # store metadata in local variables to be persisted later
                    extracted_meta_for_case = meta
                except Exception:
                    extracted_meta_for_case = {}

                # if title provided in form, use it; otherwise use filename or detected title
                title = request.form.get('title') or title or filename
                fecha = request.form.get('fecha')
                jurisd = request.form.get('jurisdiccion')
            except Exception as e:
                print('ingest_case: pdf extraction failed:', str(e))
                return jsonify({'error':'pdf_extraction_failed','message': str(e)}), 500
    else:
        # Fallback: accept JSON body only (do not call get_json unless necessary)
        if request.is_json:
            data = request.get_json(silent=True) or {}
            title = data.get('title')
            text = data.get('text')
            fecha = data.get('fecha')
            jurisd = data.get('jurisdiccion')
        else:
            # no file and not JSON -> bad request
            print('ingest_case: neither multipart file nor JSON body received')
            return jsonify({'error':'multipart_or_json_required','message':'Send multipart/form-data with `file` or JSON body with `text` and `title`.'}), 415
    try:
        from rdflib import URIRef, Literal
        RESOURCE_BASE = 'http://legalontosystem.pe/resource/'
        try:
            from backend.rdf_builder import ensure_namespaces
            ensure_namespaces(GRAPH)
        except Exception:
            pass

        ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        case_id = f'CASE_{ts}'
        case_uri = URIRef(RESOURCE_BASE + case_id)
        GRAPH.add((case_uri, rdflib.RDF.type, rdflib.URIRef('http://legalontosystem.pe/ontology#Caso')))
        GRAPH.add((case_uri, rdflib.RDFS.label, Literal(title)))
        # persist original uploaded filename if present
        try:
            if 'saved_filename' in locals() and locals().get('saved_filename'):
                GRAPH.add((case_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#archivoFilename'), Literal(locals().get('saved_filename'))))
        except Exception:
            pass
        # persist extracted metadata if available
        try:
            meta = locals().get('extracted_meta_for_case') or {}
            if meta.get('department'):
                GRAPH.add((case_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#jurisdiccionCaso'), Literal(meta.get('department'))))
            if meta.get('chamber'):
                GRAPH.add((case_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#sala'), Literal(meta.get('chamber'))))
            if meta.get('chamber_number'):
                GRAPH.add((case_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#salaNumero'), Literal(int(meta.get('chamber_number')))))
            # persist crime descriptions
            for crime in (meta.get('crime_labels') or []):
                GRAPH.add((case_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#delitoLiteral'), Literal(crime)))
        except Exception:
            pass
        # add LKIF-Core type for cases
        try:
            LKIF = 'http://www.estrellaproject.org/lkif-core/legal-rule.owl#'
            GRAPH.add((case_uri, rdflib.RDF.type, rdflib.URIRef(LKIF + 'LegalCase')))
        except Exception:
            pass
        GRAPH.add((case_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#texto'), Literal(text)))
        if fecha:
            GRAPH.add((case_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#fechaSentencia'), Literal(fecha)))
        if jurisd:
            GRAPH.add((case_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#jurisdiccionCaso'), Literal(jurisd)))

        # Run NLP extractor to detect referenced articles/laws and link them
        try:
            extracted = nlp_extractor.extract_entities(text)
            menciona_prop = rdflib.URIRef('http://legalontosystem.pe/ontology#mencionaArticulo')
            LO = rdflib.URIRef('http://legalontosystem.pe/ontology#')
            LKIF = 'http://www.estrellaproject.org/lkif-core/legal-rule.owl#'

            # determine current Código Penal version year from graph
            year = _find_codigo_penal_year(GRAPH)
            version_uri = rdflib.URIRef(f"https://leyes.peru/eli/{year}/codigo-penal/version/{year}")
            # ensure version node exists (create minimal triples if missing)
            if (version_uri, None, None) not in GRAPH:
                GRAPH.add((version_uri, rdflib.RDF.type, rdflib.URIRef(str(LO) + 'Version')))
                GRAPH.add((version_uri, rdflib.URIRef(str(LO) + 'versionYear'), Literal(str(year))))

            for art in (extracted.get('articles') or []):
                art_str = str(art)
                if art_str.startswith('http'):
                    art_uri = rdflib.URIRef(art_str)
                else:
                    art_num = ''.join(ch for ch in art_str if ch.isdigit())
                    if not art_num:
                        continue
                    art_uri = rdflib.URIRef(_eli_article_uri(art_num, GRAPH))

                # assert article type and ELI-version relationships
                try:
                    GRAPH.add((art_uri, rdflib.RDF.type, rdflib.URIRef(str(LO) + 'Articulo')))
                    GRAPH.add((art_uri, rdflib.RDF.type, rdflib.URIRef(LKIF + 'LegalRule')))
                except Exception:
                    pass
                # add article number typed literal
                try:
                    from rdflib.namespace import XSD
                    art_num_val = int(''.join(ch for ch in str(art) if ch.isdigit())) if not art_str.startswith('http') else None
                    if art_num_val is not None:
                        GRAPH.add((art_uri, rdflib.URIRef(str(LO) + 'articleNumber'), Literal(art_num_val, datatype=XSD.integer)))
                except Exception:
                    pass

                # link article <-> version
                GRAPH.add((version_uri, rdflib.URIRef(str(LO) + 'hasArticle'), art_uri))
                GRAPH.add((art_uri, rdflib.URIRef(str(LO) + 'belongsTo'), version_uri))

                # finally add mention from case to article
                GRAPH.add((case_uri, menciona_prop, art_uri))
                # mark this case also as a Precedente (useful for law->precedent links)
                try:
                    GRAPH.add((case_uri, rdflib.RDF.type, rdflib.URIRef(str(LO) + 'Precedente')))
                except Exception:
                    pass

                # Link the containing law(s) to this case as a precedent (lo:tienePrecedente).
                # If no law found for the article, fallback to linking the article itself.
                try:
                    ART_PROP = rdflib.URIRef(str(LO) + 'tieneArticulo')
                    PRE_PROP = rdflib.URIRef(str(LO) + 'tienePrecedente')
                    found_law = False
                    for law in GRAPH.subjects(ART_PROP, art_uri):
                        GRAPH.add((law, PRE_PROP, case_uri))
                        found_law = True
                    if not found_law:
                        # fallback: link article directly to precedent list
                        GRAPH.add((art_uri, PRE_PROP, case_uri))
                except Exception:
                    pass
        except Exception as e:
            print('ingest_case: NLP extractor failed:', str(e))
            # don't fail the whole request if NLP linking fails
            pass

        GRAPH.serialize(destination=WORKING_TTL, format='turtle')
        return jsonify({'status':'ok','case_uri': str(case_uri)}), 201
    except Exception as e:
        print('ingest_case: unexpected error:', str(e))
        return jsonify({'error': str(e)}), 500


@APP.route('/precedents_for_article', methods=['GET'])
def precedents_for_article():
    uri = request.args.get('uri')
    if not uri:
        return jsonify({'error':'uri param required (article URI)'}), 400
    jurisdiction = request.args.get('jurisdiccion')
    year = request.args.get('year')
    limit = int(request.args.get('limit') or 50)
    try:
        # Accept either an Article URI or a Law URI. If a Law is provided, gather its articles.
        from rdflib import URIRef
        LO = URIRef('http://legalontosystem.pe/ontology#')
        ART_PROP = URIRef(str(LO) + 'tieneArticulo')
        target_uris = []
        uref = URIRef(uri)
        # if the provided URI is a law with articles, iterate its articles
        try:
            for art in GRAPH.objects(uref, ART_PROP):
                target_uris.append(str(art))
        except Exception:
            pass
        # if no articles found, assume the uri is itself an article
        if not target_uris:
            target_uris = [uri]

        print('precedents_for_article: target_uris=', target_uris)
        # aggregate results for all target articles (dedupe by case URI)
        aggregated = {}
        for t in target_uris:
            res = precedent_processor.find_cases_for_article(GRAPH, t, jurisdiction=jurisdiction, year=year, limit=limit)
            for item in (res or []):
                case = item.get('case')
                if not case:
                    continue
                existing = aggregated.get(case)
                if not existing:
                    aggregated[case] = item
                else:
                    # merge scores and reasons
                    existing['score'] = max(existing.get('score',0), item.get('score',0))
                    existing['reasons'] = list(dict.fromkeys(existing.get('reasons', []) + item.get('reasons', [])))
        results = list(aggregated.values())
        print('precedents_for_article: aggregated_count=', len(results))
        # Use NLP-derived crime labels from article text to include matching cases by lo:delitoLiteral.
        try:
            LO = URIRef('http://legalontosystem.pe/ontology#')
            detected_crimes = set()
            for art_uri in target_uris:
                try:
                    txt = None
                    try:
                        txt = GRAPH.value(URIRef(art_uri), URIRef(str(LO) + 'texto'))
                    except Exception:
                        txt = None
                    if not txt:
                        try:
                            txt = GRAPH.value(URIRef(art_uri), RDFS.label)
                        except Exception:
                            txt = None
                    if txt:
                        # use nlp_extractor to find crime labels from article text
                        try:
                            meta = nlp_extractor.extract_case_metadata(str(txt))
                            for c in (meta.get('crime_labels') or []):
                                if c and str(c).strip():
                                    detected_crimes.add(str(c).strip().lower())
                        except Exception:
                            # fallback to naive keyword scanning if NLP fails
                            s = str(txt).lower()
                            for k in ('robo','homicidio','fraude','violencia','apropiacion','estafa','lesion','delito'):
                                if k in s:
                                    detected_crimes.add(k)
                except Exception:
                    continue

            for crime in detected_crimes:
                q_del = f"""
                PREFIX lo: <http://legalontosystem.pe/ontology#>
                SELECT ?case ?del WHERE {{
                  ?case a lo:Caso .
                  ?case lo:delitoLiteral ?del .
                  FILTER regex(str(?del), "{crime}", "i")
                }} LIMIT {limit}
                """
                try:
                    for r in GRAPH.query(q_del):
                        case = str(r.case)
                        if case in aggregated:
                            ent = aggregated[case]
                            ent['reasons'] = list(dict.fromkeys(ent.get('reasons', []) + [f'delito_match_{crime}']))
                        else:
                            aggregated[case] = {'case': case, 'label': None, 'score': 0.8, 'reasons': [f'delito_match_{crime}'], 'date': None}
                except Exception:
                    pass
        except Exception:
            pass

        results = list(aggregated.values())
        results = sorted(results, key=lambda x: x.get('score',0), reverse=True)[:limit]
        return jsonify({'uri': uri, 'target_articles': target_uris, 'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@APP.route('/files/<path:filename>', methods=['GET'])
def serve_uploaded_file(filename):
    # Serve files from the Datos directory (uploaded PDFs)
    try:
        base = os.path.dirname(os.path.dirname(__file__))
        data_dir = os.path.join(base, 'Datos')
        # prevent directory traversal
        safe_name = secure_filename(filename)
        full = os.path.join(data_dir, safe_name)
        print('serve_uploaded_file: data_dir=', data_dir, 'safe_name=', safe_name, 'full=', full)
        print('exists:', os.path.exists(full))
        if not os.path.exists(full):
            # list files for debugging
            try:
                files = os.listdir(data_dir)
            except Exception:
                files = []
            return jsonify({'error':'file_not_found','requested': safe_name, 'data_dir': data_dir, 'files': files}), 404
        return send_from_directory(data_dir, safe_name, as_attachment=False)
    except Exception as e:
        return jsonify({'error': 'file_not_found', 'message': str(e)}), 404


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


@APP.route('/nlp_extract', methods=['POST'])
def nlp_extract():
    data = request.json or {}
    text = data.get('text')
    if not text:
        return jsonify({'error':'text parameter required'}), 400
    try:
        result = nlp_extractor.extract_entities(text)
        return jsonify(result), 200
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


@APP.route('/ingest_pdf', methods=['POST'])
def ingest_pdf():
    """Accept a multipart file upload with field 'file' (PDF). Extracts text and runs NLP extraction.
    Returns extracted entities and optionally saves the raw text and TTL if requested.
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error':'file field required (PDF)'}), 400
        f = request.files['file']
        if f.filename == '':
            return jsonify({'error':'empty filename'}), 400
        filename = secure_filename(f.filename)
        base = os.path.dirname(os.path.dirname(__file__))
        save_dir = os.path.join(base, 'Datos')
        os.makedirs(save_dir, exist_ok=True)
        out_path = os.path.join(save_dir, filename)
        f.save(out_path)

        # Extract text from PDF
        try:
            text = pdf_processor.extract_text_from_pdf(out_path)
        except Exception as e:
            return jsonify({'error':'pdf_extraction_failed','message': str(e)}), 500

        # Run NLP extraction in chunks to support very large PDFs and collect merged results
        try:
            # Determine chunking parameters; allow client to override via form
            max_len = int(request.form.get('chunk_max_len') or 100000)
            overlap = int(request.form.get('chunk_overlap') or 2000)

            aggregated = {'articles': [], 'laws': [], 'entities': [], 'keywords': []}
            seen_entities = set()
            seen_articles = set()
            seen_laws = set()
            seen_keywords = set()

            # Split text into chunks (character-based) using the shared chunker
            chunks = list(chunk_text(text, max_len=max_len, overlap=overlap))
            # chunk_text yields (start_idx, chunk_text)
            for idx, (start, chunk) in enumerate(chunks, start=1):
                subres = nlp_extractor.extract_entities(chunk)
                for a in (subres.get('articles') or []):
                    if a not in seen_articles:
                        seen_articles.add(a); aggregated['articles'].append(a)
                for l in (subres.get('laws') or []):
                    if l not in seen_laws:
                        seen_laws.add(l); aggregated['laws'].append(l)
                for k in (subres.get('keywords') or []):
                    if k not in seen_keywords:
                        seen_keywords.add(k); aggregated['keywords'].append(k)
                for e in (subres.get('entities') or []):
                    key = (e.get('text','').strip().lower(), e.get('label'))
                    if key not in seen_entities:
                        seen_entities.add(key); aggregated['entities'].append(e)
        except Exception as e:
            return jsonify({'error':'nlp_failed','message': str(e)}), 500

        # Optionally convert to RDF: create document node(s) in graph if requested
        if request.form.get('persist') == '1':
            doc_id_base = request.form.get('doc_id') or ('DOC_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
            from backend.rdf_builder import ensure_namespaces
            ensure_namespaces(GRAPH)
            from rdflib import URIRef, Literal
            RESOURCE_BASE = 'http://legalontosystem.pe/resource/'
            checksum_prop = rdflib.URIRef('http://legalontosystem.pe/ontology#checksum')
            full_checksum_prop = rdflib.URIRef('http://legalontosystem.pe/ontology#fullChecksum')

            created = []
            skipped = []
            # map part checksum -> subject URI (existing or newly created)
            part_subjects = {}
            # Compute full-text checksum and create parent Documento with full text
            full_sha = hashlib.sha256(text.encode('utf8')).hexdigest()
            parent_uri = URIRef(RESOURCE_BASE + doc_id_base)
            # If a parent with same full checksum already exists, skip creating duplicates
            existing_parent = None
            for s in GRAPH.subjects(full_checksum_prop, rdflib.Literal(full_sha)):
                existing_parent = s
                break

            if existing_parent is not None:
                # Parent already exists; return it and skip creating parts
                created.append(str(existing_parent))
            else:
                # Create parent and attach full text + full checksum
                GRAPH.add((parent_uri, rdflib.RDF.type, rdflib.URIRef('http://legalontosystem.pe/ontology#Documento')))
                GRAPH.add((parent_uri, rdflib.RDFS.label, Literal(filename)))
                GRAPH.add((parent_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#texto'), Literal(text)))
                GRAPH.add((parent_uri, full_checksum_prop, Literal(full_sha)))
                created.append(str(parent_uri))

            # Persist each chunk as a part; detect duplicates by per-chunk checksum
            for part_index, (start, chunk) in enumerate(chunks, start=1):
                sha = hashlib.sha256(chunk.encode('utf8')).hexdigest()
                # Check if graph already has a document part with same checksum
                existing_subject = None
                for s in GRAPH.subjects(checksum_prop, rdflib.Literal(sha)):
                    existing_subject = s
                    skipped.append(str(s))
                    break
                if existing_subject is not None:
                    # ensure parent->tieneParte link exists
                    GRAPH.add((parent_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#tieneParte'), existing_subject))
                    part_subjects[sha] = existing_subject
                    # don't recreate the part node, but continue to next step
                else:
                    part_id = f"{doc_id_base}_part{part_index}"
                    doc_uri = URIRef(RESOURCE_BASE + part_id)
                    GRAPH.add((doc_uri, rdflib.RDF.type, rdflib.URIRef('http://legalontosystem.pe/ontology#Documento')))
                    GRAPH.add((doc_uri, rdflib.RDFS.label, Literal(f"{filename} (parte {part_index})")))
                    GRAPH.add((doc_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#texto'), Literal(chunk)))
                    GRAPH.add((doc_uri, checksum_prop, Literal(sha)))
                    # always link part to parent doc
                    GRAPH.add((parent_uri, rdflib.URIRef('http://legalontosystem.pe/ontology#tieneParte'), doc_uri))

                    created.append(str(doc_uri))
                    part_subjects[sha] = doc_uri

            # Link the created document(s) to any articles detected by the NLP extractor
            try:
                menciona_prop = rdflib.URIRef('http://legalontosystem.pe/ontology#mencionaArticulo')
                # For each detected article, attach mencionaArticulo to parent and to all part subjects (new or existing)
                parent_uri = rdflib.URIRef(RESOURCE_BASE + doc_id_base)
                for art in aggregated.get('articles', []):
                    # art may be a number string; build ELI article URI using detected CP year
                    art_num = ''.join(ch for ch in str(art) if ch.isdigit())
                    if not art_num:
                        continue
                    try:
                        art_uri = rdflib.URIRef(_eli_article_uri(art_num, GRAPH))
                        # assert LKIF type for articles
                        try:
                            LKIF = 'http://www.estrellaproject.org/lkif-core/legal-rule.owl#'
                            GRAPH.add((art_uri, rdflib.RDF.type, rdflib.URIRef(LKIF + 'LegalRule')))
                        except Exception:
                            pass
                        # attach to parent doc
                        GRAPH.add((parent_uri, menciona_prop, art_uri))
                        # attach to each part (use part_subjects map to include existing ones)
                        for sha, subj in part_subjects.items():
                            sref = subj if isinstance(subj, rdflib.term.Node) else rdflib.URIRef(str(subj))
                            GRAPH.add((sref, menciona_prop, art_uri))
                    except Exception:
                        # skip if ELI generation fails for any reason
                        continue

                # Persist detected 'laws' (external law identifiers) as mencionaLey
                try:
                    menciona_ley = rdflib.URIRef('http://legalontosystem.pe/ontology#mencionaLey')
                    for law in aggregated.get('laws', []):
                        law_id = ''.join(ch for ch in str(law) if ch.isalnum())
                        if not law_id:
                            continue
                        law_uri = rdflib.URIRef(f'http://legalontosystem.pe/law/{law_id}')
                        GRAPH.add((parent_uri, menciona_ley, law_uri))
                        for sha, subj in part_subjects.items():
                            sref = subj if isinstance(subj, rdflib.term.Node) else rdflib.URIRef(str(subj))
                            GRAPH.add((sref, menciona_ley, law_uri))
                except Exception:
                    pass

                # Persist keywords as literal triples lo:keyword
                try:
                    kw_prop = rdflib.URIRef('http://legalontosystem.pe/ontology#keyword')
                    for kw in aggregated.get('keywords', []):
                        GRAPH.add((parent_uri, kw_prop, rdflib.Literal(str(kw))))
                        for sha, subj in part_subjects.items():
                            sref = subj if isinstance(subj, rdflib.term.Node) else rdflib.URIRef(str(subj))
                            GRAPH.add((sref, kw_prop, rdflib.Literal(str(kw))))
                except Exception:
                    pass

                # Persist entities as blank nodes with label and type, link via lo:mencionaEntidad
                try:
                    ent_prop = rdflib.URIRef('http://legalontosystem.pe/ontology#mencionaEntidad')
                    ent_type_prop = rdflib.URIRef('http://legalontosystem.pe/ontology#entidadTipo')
                    for i, ent in enumerate(aggregated.get('entities', []), start=1):
                        text_val = ent.get('text') or ent.get('label') or str(ent)
                        ent_bnode = rdflib.BNode()
                        GRAPH.add((ent_bnode, rdflib.RDFS.label, rdflib.Literal(text_val)))
                        if ent.get('label'):
                            GRAPH.add((ent_bnode, ent_type_prop, rdflib.Literal(ent.get('label'))))
                        # link to parent and parts
                        GRAPH.add((parent_uri, ent_prop, ent_bnode))
                        for sha, subj in part_subjects.items():
                            sref = subj if isinstance(subj, rdflib.term.Node) else rdflib.URIRef(str(subj))
                            GRAPH.add((sref, ent_prop, ent_bnode))
                except Exception:
                    pass

                GRAPH.serialize(destination=WORKING_TTL, format='turtle')
            except Exception as e:
                return jsonify({'error':'persist_failed','message': str(e)}), 500

        return jsonify({'status':'ok','saved_as': os.path.basename(out_path), 'entities': aggregated, 'created': created if request.form.get('persist') == '1' else [], 'skipped': skipped if request.form.get('persist') == '1' else []}), 200
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
