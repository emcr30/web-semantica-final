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
RESOURCE_BASE = 'http://legalontosystem.pe/resource/'

# Load or create graph
GRAPHS_BY_FILE = {}
GRAPH = None  # merged view across files


def load_all_ttls(ontologia_dir: str):
    """Load all .ttl files under `ontologia_dir` as separate Graphs and produce a merged Graph.
    Returns (merged_graph, graphs_by_file_dict).
    """
    from rdflib import Graph
    graphs = {}
    merged = Graph()
    try:
        if not os.path.exists(ontologia_dir):
            return merged, graphs
        for fname in sorted(os.listdir(ontologia_dir)):
            if not fname.lower().endswith('.ttl'):
                continue
            path = os.path.join(ontologia_dir, fname)
            try:
                g = Graph()
                g.parse(path, format='turtle')
                graphs[fname] = g
                # merge triples into merged graph
                for t in g.triples((None, None, None)):
                    merged.add(t)
            except Exception as e:
                print(f"Warning: failed parsing TTL {path}: {e}")
    except Exception as e:
        print('load_all_ttls error:', str(e))
    return merged, graphs


# initial load of ontology files into per-file graphs + merged view
try:
    MERGED, FILE_GRAPHS = load_all_ttls(os.path.join(BASE_DIR, 'Ontologia'))
    GRAPH = MERGED
    GRAPHS_BY_FILE = FILE_GRAPHS
except Exception as e:
    print('Warning: failed initial TTL load:', str(e))


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

def _normalize_uri(u: str) -> str:
    """Normalize URIs to canonical ELI domain and strip trailing slash."""
    if not isinstance(u, str):
        return u
    s = u.strip().rstrip('/')
    if '/eli/' in s:
        parts = s.split('/eli/', 1)
        s = 'https://leyes.peru/eli/' + parts[1]
    return s

@APP.route('/ingest', methods=['POST'])
def ingest():
    data = request.json or {}
    # If `text` provided we create a law individual from raw text
    if 'text' in data:
        law_id = data.get('id', 'LEY_' + str(abs(hash(data.get('text'))) % 100000))
        title = data.get('title', 'Ley importada')
        jurisdiction = data.get('jurisdiccion', 'Peru')
        # Create the law in a fresh graph and serialize to its own TTL file
        try:
            from rdflib import Graph
            newg = Graph()
            rdf_builder.create_law(newg, law_id, title, data['text'], jurisdiction)
            # annotate source filename on the resource if possible (best-effort)
            try:
                # use resource base pattern to find subject
                subj = None
                for s in newg.subjects(None, None):
                    if str(s).startswith(RESOURCE_BASE):
                        subj = s
                        break
                if subj is not None:
                    newg.add((subj, rdflib.URIRef('http://legalontosystem.pe/ontology#sourceFile'), rdflib.Literal(f"{secure_filename(title)}.pdf")))
            except Exception:
                pass
            ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            safe = secure_filename(title) or law_id
            outname = f"{safe}_{ts}.ttl"
            outpath = os.path.join(os.path.dirname(__file__), '..', 'Ontologia', outname)
            newg.serialize(destination=outpath, format='turtle')
            # reload all TTLs so the new file is included in memory
            merged, graphs = load_all_ttls(os.path.join(BASE_DIR, 'Ontologia'))
            global GRAPH, GRAPHS_BY_FILE
            GRAPH = merged
            GRAPHS_BY_FILE = graphs
            return jsonify({'status':'ok','id':law_id,'saved_ttl': outname}), 201
        except Exception as e:
            return jsonify({'error':'create_law_failed','message': str(e)}), 500
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
    scope = request.args.get('scope','')
    if not q:
        return jsonify({'error':'q parameter required'}), 400
    # Try SPARQL-based search first; if parser fails (rdflib/pyparsing issues),
    # fall back to a graph-scan text search to keep the UI working.
    try:
        # allow searching by scope: 'content' (full text), 'keywords' (search by crime keywords and related cases), or default
        q_esc = q.replace('"','\\"')
        if scope == 'keywords':
            query = f'''
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX lo: <http://legalontosystem.pe/ontology#>
    SELECT DISTINCT ?law ?title WHERE {{
      ?law a ?type .
      FILTER( ?type = lo:Ley || ?type = lo:Articulo )
      OPTIONAL {{ ?law rdfs:label ?label }}
      OPTIONAL {{ ?law lo:titulo ?titulo }}
      OPTIONAL {{ ?law lo:texto ?texto }}
      BIND(COALESCE(?label, ?titulo, "") AS ?title)
      FILTER( regex(str(?title), "{q_esc}", "i") || (bound(?texto) && regex(str(?texto), "{q_esc}", "i")) || EXISTS {{ ?law lo:tieneArticulo ?art . ?case lo:mencionaArticulo ?art . ?case lo:delitoLiteral ?dl . FILTER(regex(str(?dl), "{q_esc}", "i")) }} )
    }} LIMIT 200
            '''
        elif scope == 'content':
            query = f'''
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX lo: <http://legalontosystem.pe/ontology#>
    SELECT ?law ?title WHERE {{
      ?law a ?type .
      FILTER( ?type = lo:Ley || ?type = lo:Articulo )
      OPTIONAL {{ ?law rdfs:label ?label }}
      OPTIONAL {{ ?law lo:titulo ?titulo }}
      OPTIONAL {{ ?law lo:texto ?texto }}
      BIND(COALESCE(?label, ?titulo, "") AS ?title)
      FILTER( bound(?texto) && regex(str(?texto), "{q_esc}", "i") )
    }} LIMIT 200
            '''
        else:
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

    # Auto-inject common prefixes if used but not declared
    def _ensure_prefixes(q: str) -> str:
        try:
            import re
            prefix_map = {
                'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'lo': 'http://legalontosystem.pe/ontology#',
                'dct': 'http://purl.org/dc/terms/',
                'xsd': 'http://www.w3.org/2001/XMLSchema#',
            }
            # prefixes already declared
            declared = set(m.group(1).lower() for m in re.finditer(r'(?im)^\s*PREFIX\s+([A-Za-z][A-Za-z0-9_-]*):', q))
            needed = []
            for p, uri in prefix_map.items():
                # detect token usage like 'pfx:' that isn't part of a PREFIX line
                if re.search(rf'(^|[^A-Za-z0-9_]){p}:[A-Za-z_]', q) and p not in declared:
                    needed.append(f"PREFIX {p}: <{uri}>")
            if needed:
                q = "\n".join(needed) + "\n" + q
            return q
        except Exception:
            return q

    query = _ensure_prefixes(query)
    # Basic validation: detect malformed UNION usage before rdflib parses
    try:
        qchk = query if isinstance(query, str) else str(query)
        # Auto-correct common typo 'UNIO' -> 'UNION' between groups
        import re
        qchk = re.sub(r"\}\s*UNIO\s*\{", "} UNION {", qchk, flags=re.IGNORECASE)
        # Rewrite specific UNION pattern for article children into a path operator to avoid parser fragility
        # { <SUBJ> lo:tieneArticulo ?art } UNION { <SUBJ> lo:hasArticle ?art } -> { <SUBJ> (lo:tieneArticulo|lo:hasArticle) ?art }
        qchk = re.sub(
            r"\{\s*<([^>]+)>\s+lo:tieneArticulo\s+\?art\s*\}\s*UNION\s*\{\s*<\\1>\s+lo:hasArticle\s+\?art\s*\}",
            r"{ <\\1> (lo:tieneArticulo|lo:hasArticle) ?art }",
            qchk,
            flags=re.IGNORECASE
        )
        query = qchk
        if 'UNION' in qchk:
            # A valid UNION requires two complete groups {...} UNION {...}
            # quick check for presence of two braces groups
            groups = re.findall(r"\{[^}]*\}", qchk)
            if len(groups) < 2 or 'UNIO' in qchk:
                raise ValueError('Invalid SPARQL UNION detected')
    except Exception as _:
        # do not block; allow fallback to handle query
        pass

    try:
        res = GRAPH.query(query)
    except Exception as e:
        # Concise logging without full traceback to avoid noisy console spam
        msg = str(e)
        print('SPARQL execution error;', 'query preview:', repr(query)[:300], 'error:', msg)

        # Attempt a targeted fallback for a common query template used by the UI:
        # SELECT ?art ?label ?titulo ?anio ?jurisd WHERE {
        #   OPTIONAL {
        #     { <SUBJ> lo:tieneArticulo ?art } UNION { <SUBJ> lo:hasArticle ?art } .
        #     OPTIONAL { ?art rdfs:label ?label }
        #   }
        #   OPTIONAL { <SUBJ> lo:titulo ?titulo }
        #   OPTIONAL { <SUBJ> lo:anio ?anio }
        #   OPTIONAL { <SUBJ> lo:aplicaEn ?jurisd }
        # }
        try:
            import re
            qstr = query if isinstance(query, str) else str(query)
            # Extract the fixed subject URI inside angle brackets that appears before tieneArticulo/hasArticle
            m = re.search(r"\{\s*<([^>]+)>\s+lo:(?:tieneArticulo|hasArticle)\s+\?art", qstr)
            if not m:
                # try within OPTIONAL { { <...> ... } UNION { <...> ... } }
                m = re.search(r"\{\s*\{\s*<([^>]+)>\s+lo:(?:tieneArticulo|hasArticle)\s+\?art", qstr)
            if m:
                subj_uri = m.group(1)
                LO = rdflib.URIRef('http://legalontosystem.pe/ontology#')
                tiene = rdflib.URIRef(str(LO) + 'tieneArticulo')
                has = rdflib.URIRef(str(LO) + 'hasArticle')
                # gather articles
                arts = []
                sref = rdflib.URIRef(subj_uri)
                try:
                    for a in GRAPH.objects(sref, tiene):
                        arts.append(a)
                except Exception:
                    pass
                try:
                    for a in GRAPH.objects(sref, has):
                        arts.append(a)
                except Exception:
                    pass
                # dedupe while preserving order
                seen_u = set()
                arts_u = []
                for a in arts:
                    su = str(a)
                    if su not in seen_u:
                        seen_u.add(su)
                        arts_u.append(a)

                titulo = GRAPH.value(sref, rdflib.URIRef(str(LO) + 'titulo'))
                anio = GRAPH.value(sref, rdflib.URIRef(str(LO) + 'anio'))
                jurisd = GRAPH.value(sref, rdflib.URIRef(str(LO) + 'aplicaEn'))

                rows = []
                for a in arts_u:
                    label = GRAPH.value(a, RDFS.label)
                    rows.append({
                        'art': str(a),
                        'label': str(label) if label else None,
                        'titulo': str(titulo) if titulo else None,
                        'anio': str(anio) if anio else None,
                        'jurisd': str(jurisd) if jurisd else None,
                    })
                return jsonify({'head': ['art','label','titulo','anio','jurisd'], 'results': rows, 'fallback': True})
        except Exception:
            # ignore and fall through to soft error
            pass

        # Fallback 2: list all articles with optional number and title
        # Matches queries of the form:
        #   SELECT ?art ?num ?title WHERE {
        #     ?art a lo:Articulo .
        #     OPTIONAL { ?art lo:articleNumber ?num }
        #     OPTIONAL { ?art rdfs:label ?l }
        #     OPTIONAL { ?art lo:titulo ?t }
        #     BIND(COALESCE(?l, ?t, "") AS ?title)
        #   } ORDER BY ?num LIMIT N
        try:
            import re
            qstr = query if isinstance(query, str) else str(query)
            if re.search(r"\?art\s+a\s+lo:Articulo", qstr):
                # derive limit if present
                lim = 100
                mlim = re.search(r"LIMIT\s+(\d+)", qstr, re.IGNORECASE)
                if mlim:
                    try:
                        lim = int(mlim.group(1))
                    except Exception:
                        lim = 100
                # detect if ordering by ?num requested
                order_by_num = bool(re.search(r"ORDER\s+BY\s+\?num", qstr, re.IGNORECASE))

                LO = rdflib.URIRef('http://legalontosystem.pe/ontology#')
                art_t = rdflib.URIRef(str(LO) + 'Articulo')
                num_p = rdflib.URIRef(str(LO) + 'articleNumber')
                titulo_p = rdflib.URIRef(str(LO) + 'titulo')

                rows_raw = []
                for s in GRAPH.subjects(RDF.type, art_t):
                    num = GRAPH.value(s, num_p)
                    l = GRAPH.value(s, RDFS.label)
                    t = GRAPH.value(s, titulo_p)
                    title = l or t
                    rows_raw.append({
                        'art': str(s),
                        'num_raw': str(num) if num is not None else None,
                        'title': str(title) if title is not None else ''
                    })

                def num_key(v):
                    try:
                        # extract integer even if stored as string
                        import re
                        m = re.search(r"\d+", v.get('num_raw') or '')
                        return int(m.group(0)) if m else 10**9
                    except Exception:
                        return 10**9

                if order_by_num:
                    rows_raw.sort(key=num_key)

                # apply limit and map to expected keys
                out = []
                for r in rows_raw[:lim]:
                    out.append({ 'art': r['art'], 'num': r['num_raw'], 'title': r['title'] })

                return jsonify({'head': ['art','num','title'], 'results': out, 'fallback': True})
        except Exception:
            pass

        # Fallback 3: generic typed-list with OPTIONAL props and simple CONTAINS filters
        # Supports queries containing a basic pattern: ?var a lo:Class . OPTIONAL { ?var prop ?v }
        # Recognized props: rdfs:label, lo:titulo, lo:texto, lo:articleNumber. Supports ORDER BY ?varname and LIMIT N.
        try:
            import re
            qstr = query if isinstance(query, str) else str(query)
            # Identify SELECT variables
            msel = re.search(r"(?is)select\s+(.*?)\s+where", qstr)
            if not msel:
                raise ValueError('no select clause')
            sel_part = msel.group(1)
            sel_vars = [v.strip()[1:] for v in re.findall(r"\?[A-Za-z_][A-Za-z0-9_]*", sel_part)]

            # Detect type pattern ?res a lo:Something
            mtype = re.search(r"\?(?P<res>[A-Za-z_][A-Za-z0-9_]*)\s+a\s+lo:(?P<class>[A-Za-z_][A-Za-z0-9_]*)", qstr)
            if not mtype:
                raise ValueError('no type pattern')
            res_var = mtype.group('res')
            class_name = mtype.group('class')

            # Detect OPTIONAL bindings for common props to variable names
            def opt_var(pattern: str) -> str | None:
                m = re.search(pattern, qstr)
                return m.group(1) if m else None
            l_var = opt_var(r"OPTIONAL\s*\{\s*\?%s\s+rdfs:label\s+\?(\w+)\s*\}" % res_var)
            t_var = opt_var(r"OPTIONAL\s*\{\s*\?%s\s+lo:titulo\s+\?(\w+)\s*\}" % res_var)
            x_var = opt_var(r"OPTIONAL\s*\{\s*\?%s\s+lo:texto\s+\?(\w+)\s*\}" % res_var)
            n_var = opt_var(r"OPTIONAL\s*\{\s*\?%s\s+lo:articleNumber\s+\?(\w+)\s*\}" % res_var)

            # Extract simple CONTAINS filters of form CONTAINS(LCASE(STR(?var)), "term")
            contains_filters = []
            for m in re.finditer(r"CONTAINS\(\s*LCASE\(STR\(\?(\w+)\)\)\s*,\s*\"([^\"]*)\"\s*\)", qstr, re.IGNORECASE):
                contains_filters.append((m.group(1), m.group(2).lower()))

            # ORDER BY and LIMIT
            order_m = re.search(r"ORDER\s+BY\s+\?(\w+)", qstr, re.IGNORECASE)
            order_var = order_m.group(1) if order_m else None
            lim = 200
            mlim = re.search(r"LIMIT\s+(\d+)", qstr, re.IGNORECASE)
            if mlim:
                try:
                    lim = int(mlim.group(1))
                except Exception:
                    lim = 200

            # Resolve class URI
            LO = rdflib.URIRef('http://legalontosystem.pe/ontology#')
            class_uri = rdflib.URIRef(str(LO) + class_name)
            # Collect resources of this type
            resources = list(GRAPH.subjects(RDF.type, class_uri))

            # Build row objects with available fields
            out_rows = []
            for s in resources:
                lab = GRAPH.value(s, RDFS.label)
                tit = GRAPH.value(s, rdflib.URIRef(str(LO) + 'titulo'))
                txt = GRAPH.value(s, rdflib.URIRef(str(LO) + 'texto'))
                num = GRAPH.value(s, rdflib.URIRef(str(LO) + 'articleNumber'))

                # Apply contains filters when they reference known vars
                ok = True
                for vname, term in contains_filters:
                    val = None
                    if vname == (l_var or ''):
                        val = lab
                    elif vname == (t_var or ''):
                        val = tit
                    elif vname == (x_var or ''):
                        val = txt
                    elif vname == (n_var or ''):
                        val = num
                    elif vname == res_var:
                        val = s
                    if val is not None and term:
                        sval = str(val).lower()
                        if term not in sval:
                            ok = False; break
                if not ok:
                    continue

                row = {}
                # Populate selected variables
                for v in sel_vars:
                    if v == res_var:
                        row[v] = str(s)
                    elif v == (l_var or ''):
                        row[v] = str(lab) if lab is not None else None
                    elif v == (t_var or ''):
                        row[v] = str(tit) if tit is not None else None
                    elif v == (x_var or ''):
                        row[v] = str(txt) if txt is not None else None
                    elif v == (n_var or ''):
                        row[v] = str(num) if num is not None else None
                    elif v.lower() == 'title':
                        row[v] = str(lab or tit or '')
                    else:
                        row[v] = None
                out_rows.append(row)

            # Sorting
            if order_var:
                def order_key(r):
                    val = r.get(order_var)
                    if val is None:
                        return ''
                    # try numeric
                    try:
                        import re
                        m = re.search(r"\d+", str(val))
                        return int(m.group(0)) if m else str(val)
                    except Exception:
                        return str(val)
                out_rows.sort(key=order_key)

            # Trim to limit and return with head equal to SELECT projection order
            head = ['?' + v for v in sel_vars]
            # Convert to rdflib-like result format: keys without '?'
            mapped = []
            for r in out_rows[:lim]:
                mapped.append({ k: ('' if r[k[1:]] is None else r[k[1:]]) for k in head })

            return jsonify({'head': [v[1:] for v in head], 'results': mapped, 'fallback': True})
        except Exception:
            pass

        # Fallback 4: typed-list for any prefix (including default ':') e.g. `?x a :Delito` with OPTIONAL rdfs:label
        try:
            import re
            qstr = query if isinstance(query, str) else str(query)

            # Collect declared prefixes, including default ':'
            prefix_map = {}
            for m in re.finditer(r"(?im)^\s*PREFIX\s+([A-Za-z][A-Za-z0-9_-]*)?:\s*<([^>]+)>", qstr):
                pfx = m.group(1) or ''
                uri = m.group(2)
                prefix_map[pfx] = uri

            # Detect pattern `?var a <pfx>:<Class>` where pfx may be empty (default ':')
            mtype = re.search(r"\?(?P<res>[A-Za-z_][A-Za-z0-9_]*)\s+a\s+(?P<pfx>[A-Za-z][A-Za-z0-9_-]*)?:\s*(?P<class>[A-Za-z_][A-Za-z0-9_]*)", qstr)
            if not mtype:
                raise ValueError('no typed pattern with arbitrary prefix')
            res_var = mtype.group('res')
            pfx = mtype.group('pfx') or ''
            cls = mtype.group('class')
            base = prefix_map.get(pfx)
            if not base:
                raise ValueError('prefix base not found')
            class_uri = rdflib.URIRef(base + cls)

            # Optional label var name
            mlabel = re.search(r"OPTIONAL\s*\{\s*\?%s\s+rdfs:label\s+\?(\w+)\s*\}" % res_var, qstr)
            label_var = mlabel.group(1) if mlabel else None

            # Extract SELECT var names
            msel = re.search(r"(?is)select\s+(.*?)\s+where", qstr)
            if not msel:
                raise ValueError('no select clause')
            sel_vars = [v.strip()[1:] for v in re.findall(r"\?[A-Za-z_][A-Za-z0-9_]*", msel.group(1))]

            # ORDER BY and LIMIT
            order_m = re.search(r"ORDER\s+BY\s+\?(\w+)", qstr, re.IGNORECASE)
            order_var = order_m.group(1) if order_m else None
            lim = 200
            mlim = re.search(r"LIMIT\s+(\d+)", qstr, re.IGNORECASE)
            if mlim:
                try:
                    lim = int(mlim.group(1))
                except Exception:
                    lim = 200

            # Collect resources and build rows
            rows = []
            for s in GRAPH.subjects(RDF.type, class_uri):
                lab = GRAPH.value(s, RDFS.label)
                row = {}
                for v in sel_vars:
                    if v == res_var:
                        row[v] = str(s)
                    elif v == (label_var or '') or v.lower() == 'label':
                        row[v] = str(lab) if lab is not None else ''
                    else:
                        row[v] = ''
                rows.append(row)

            # sort and limit
            if order_var:
                rows.sort(key=lambda r: (r.get(order_var) or '').lower())
            rows = rows[:lim]

            return jsonify({'head': sel_vars, 'results': [{k: v for k, v in r.items()} for r in rows], 'fallback': True})
        except Exception:
            pass

        # Return a soft error with empty results to avoid noisy 500s in the UI
        return jsonify({'head': [], 'results': [], 'error': 'query_error', 'message': msg, 'query_preview': repr(query)[:1000]}), 200

    # convert to JSON-friendly (stringify variable names)
    vars = [str(v) for v in res.vars]
    rows = []
    for r in res:
        rows.append({ vars[i]: str(r[i]) for i in range(len(vars)) })
    return jsonify({'head':vars,'results':rows})

@APP.route('/search_text', methods=['POST'])
def search_text():
    """Search resources by simple text match across common properties without SPARQL.
    Body: { "keywords": ["homicidio", "arma blanca"], "limit": 100 }
    Returns: { results: [ { res: uri, title: str } ] }
    """
    try:
        data = request.get_json(force=True) or {}
        kws = [str(k).strip().lower() for k in data.get('keywords', []) if isinstance(k, str)]
        limit = int(data.get('limit', 100))
        if not kws:
            return jsonify({ 'results': [] })

        RDFS_LABEL = RDFS.label
        LO = URIRef('http://legalontosystem.pe/ontology#')
        props = [RDFS_LABEL, URIRef(str(LO) + 'titulo'), URIRef(str(LO) + 'texto'), URIRef('http://www.w3.org/2000/01/rdf-schema#comment'), URIRef(str(LO) + 'delitoLiteral')]

        seen = set()
        results = []
        # Iterate all subjects and check literals of target properties
        for s in set(GRAPH.subjects(None, None)):
            # type filter: law or article if types present
            types = set(GRAPH.objects(s, RDF.type))
            if types and URIRef(str(LO) + 'Ley') not in types and URIRef(str(LO) + 'Articulo') not in types:
                continue
            title = None
            matched = False
            for p in props:
                for o in GRAPH.objects(s, p):
                    if isinstance(o, rdflib.term.Literal):
                        val = str(o).lower()
                        for kw in kws:
                            if kw and kw in val:
                                matched = True
                                if p == RDFS_LABEL or p == URIRef(str(LO) + 'titulo'):
                                    title = str(o)
                                break
                    if matched:
                        break
                if matched:
                    break
            if matched:
                uri = str(s).rstrip('/')
                # normalize canonical ELI domain
                if '/eli/' in uri:
                    parts = uri.split('/eli/', 1)
                    uri = 'https://leyes.peru/eli/' + parts[1]
                if uri in seen:
                    continue
                seen.add(uri)
                results.append({ 'res': uri, 'title': title })
                if len(results) >= limit:
                    break
        return jsonify({ 'results': results })
    except Exception as e:
        import traceback
        print('search_text error:', traceback.format_exc())
        return jsonify({ 'error': str(e) }), 500

@APP.route('/advise_case', methods=['POST'])
def advise_case():
    """Semantic advisor: extract crime labels and return linked articles/laws without SPARQL.
    Body: { text: "..." }
    Returns: { applicable: [ { uri, title } ] }
    """
    try:
        data = request.get_json(force=True) or {}
        text = str(data.get('text', '') or '')
        if not text:
            return jsonify({ 'applicable': [] })

        # Extract metadata and keywords
        meta = nlp_extractor.extract_case_metadata(text)
        extracted = nlp_extractor.extract_entities(text)
        crime_labels = set([c.lower() for c in meta.get('crime_labels', [])])
        # Also include keywords as crime cues
        for k in extracted.get('keywords', []):
            if isinstance(k, str):
                kl = k.lower()
                if kl in ('homicidio','asesinato','lesiones','robo','violencia') or 'homicid' in kl or 'robo' in kl:
                    crime_labels.add('homicidio' if 'homicid' in kl or 'muerte' in kl else kl)

        LO = URIRef('http://legalontosystem.pe/ontology#')
        # Collect articles linked by cases/documents via mencionaArticulo or delitoLiteral
        seen = {}
        scored = []
        # Helper to normalize ELI URI
        def norm(uri: str) -> str:
            if not uri:
                return uri
            u = uri.rstrip('/')
            if '/eli/' in u:
                parts = u.split('/eli/', 1)
                u = 'https://leyes.peru/eli/' + parts[1]
            return u

        # Check all subjects typed as Caso or Documento and pivot to Articulo
        tipos = [URIRef(str(LO) + 'Caso'), URIRef(str(LO) + 'Documento')]
        for t in tipos:
            for subj in GRAPH.subjects(RDF.type, t):
                # crime match via delitoLiteral
                match = False
                for dlit in GRAPH.objects(subj, URIRef(str(LO) + 'delitoLiteral')):
                    if isinstance(dlit, rdflib.Literal):
                        val = str(dlit).lower()
                        for cl in crime_labels:
                            if cl and cl in val:
                                match = True
                                break
                    if match:
                        break
                # If no explicit delitoLiteral match, do a weak text match against texto/comment
                if not match:
                    for p in [URIRef(str(LO) + 'texto'), RDFS.label, URIRef('http://www.w3.org/2000/01/rdf-schema#comment')]:
                        for o in GRAPH.objects(subj, p):
                            if isinstance(o, rdflib.Literal):
                                val = str(o).lower()
                                for cl in crime_labels:
                                    if cl and cl in val:
                                        match = True
                                        break
                        if match:
                            break
                if not match:
                    continue
                # gather mentioned articles
                for art in GRAPH.objects(subj, URIRef(str(LO) + 'mencionaArticulo')):
                    uri = norm(str(art))
                    if not uri:
                        continue
                    # compute a relevance score
                    score = 0
                    score += 5 if match else 0
                    # boost homicide articles by number
                    art_num = GRAPH.value(art, URIRef(str(LO) + 'articleNumber'))
                    if art_num and str(art_num).strip() in ('106','108','107'):
                        score += 3
                    # boost if article/title contains crime labels
                    atitle = GRAPH.value(art, URIRef(str(LO) + 'titulo')) or GRAPH.value(art, RDFS.label)
                    atitle_s = str(atitle) if atitle else ''
                    for cl in crime_labels:
                        if cl and cl in atitle_s.lower():
                            score += 2
                    # construct display title with parent law title if available
                    ley_title = None
                    for ley in GRAPH.objects(art, URIRef(str(LO) + 'perteneceALey')):
                        lt = GRAPH.value(ley, URIRef(str(LO) + 'titulo')) or GRAPH.value(ley, RDFS.label)
                        if lt:
                            ley_title = str(lt)
                            break
                    display = None
                    if atitle:
                        display = str(atitle)
                    else:
                        # fallback: "Artículo {num} – {ley_title}" or ELI code
                        num = str(art_num) if art_num else None
                        if num and ley_title:
                            display = f"Artículo {num} – {ley_title}"
                        elif num:
                            # try to infer year from URI
                            yr = None
                            try:
                                import re
                                m = re.search(r"/(19|20)\d{2}/", uri)
                                if m:
                                    yr = m.group(0).strip('/').strip()
                            except Exception:
                                pass
                            display = f"Artículo {num} – Código Penal {yr}" if yr else f"Artículo {num}"
                        else:
                            display = uri
                    prev = seen.get(uri)
                    if not prev or score > prev['score']:
                        seen[uri] = { 'uri': uri, 'title': display, 'score': score }
                        scored.append(seen[uri])

        # If still empty and homicide cues present, add Article 106
        if not scored and ('homicidio' in crime_labels or 'muerte' in extracted.get('keywords', [])):
            try:
                uri = norm(_eli_article_uri('106', GRAPH))
                title = None
                # Try to find the article resource to fetch title
                for s in GRAPH.subjects(None, None):
                    if str(s).rstrip('/') == uri:
                        title = GRAPH.value(s, URIRef(str(LO) + 'titulo')) or GRAPH.value(s, RDFS.label)
                        break
                scored.append({ 'uri': uri, 'title': str(title) if title else 'Homicidio simple', 'score': 4 })
            except Exception:
                pass

        # Sort by score desc and return top 12
        scored.sort(key=lambda x: x.get('score', 0), reverse=True)
        return jsonify({ 'applicable': scored[:12] })
    except Exception as e:
        import traceback
        print('advise_case error:', traceback.format_exc())
        return jsonify({ 'error': str(e) }), 500

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
        merged, graphs = load_all_ttls(os.path.join(BASE_DIR, 'Ontologia'))
        GRAPH = merged
        global GRAPHS_BY_FILE
        GRAPHS_BY_FILE = graphs
        return jsonify({'status':'reloaded','files_loaded': list(graphs.keys())}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@APP.route('/clear_uploaded_data', methods=['POST'])
def clear_uploaded_data():
    """Remove RDF resources created under the `resource` namespace (cases/documents/parts)
    and delete files under the Datos directory. Requires confirm=true in form or JSON.
    Use with caution.
    """
    data = request.json or request.form.to_dict() or {}
    if str(data.get('confirm')).lower() not in ('1','true','yes'):
        return jsonify({'error':'confirm_required','message':'Send JSON {"confirm": true} to perform deletion.'}), 400
    try:
        # remove triples whose subject is in RESOURCE_BASE
        subj_to_remove = [s for s in GRAPH.subjects(None, None) if str(s).startswith(RESOURCE_BASE)]
        removed = 0
        for s in subj_to_remove:
            # remove all triples with subject s
            for t in list(GRAPH.triples((s, None, None))):
                GRAPH.remove(t)
                removed += 1
            # also remove any triples where s is object
            for t in list(GRAPH.triples((None, None, s))):
                GRAPH.remove(t)
                removed += 1

        # delete files under Datos
        base = os.path.dirname(os.path.dirname(__file__))
        data_dir = os.path.join(base, 'Datos')
        deleted_files = []
        if os.path.exists(data_dir):
            for fname in os.listdir(data_dir):
                # only remove typical uploaded files (pdf, txt)
                if fname.lower().endswith(('.pdf','.txt')):
                    try:
                        full = os.path.join(data_dir, fname)
                        os.remove(full)
                        deleted_files.append(fname)
                    except Exception:
                        pass

        GRAPH.serialize(destination=WORKING_TTL, format='turtle')
        return jsonify({'status':'cleared','triples_removed': removed, 'files_deleted': deleted_files}), 200
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
    art_num = request.args.get('articleNumber')
    if not uri and not art_num:
        return jsonify({'error':'uri or articleNumber required'}), 400
    jurisdiction = request.args.get('jurisdiccion')
    year = request.args.get('year')
    limit = int(request.args.get('limit') or 50)
    try:
        # Accept articleNumber, Article URI, or Law URI. Prefer articleNumber for version-agnostic behavior.
        from rdflib import URIRef
        LO = URIRef('http://legalontosystem.pe/ontology#')
        # support both vocabulary variants used in the dataset: 'tieneArticulo' and 'hasArticle'
        ART_PROP_NAMES = ['tieneArticulo', 'hasArticle']
        target_uris = []
        # Prefer articleNumber: find all matching articles across versions
        if art_num:
            num_p = URIRef(str(LO) + 'articleNumber')
            try:
                for s in GRAPH.subjects(num_p, rdflib.Literal(int(art_num))):
                    target_uris.append(str(s))
            except Exception:
                # fallback: match as string
                for s,p,o in GRAPH.triples((None, num_p, None)):
                    if str(o).strip() == str(art_num).strip():
                        target_uris.append(str(s))
        else:
            uref = URIRef(uri)
            # if the provided URI is a law/version with articles, iterate its articles
            try:
                for prop_name in ART_PROP_NAMES:
                    prop = URIRef(str(LO) + prop_name)
                    for art in GRAPH.objects(uref, prop):
                        target_uris.append(str(art))
            except Exception:
                pass
            # if no articles found, assume the uri is itself an article
            if not target_uris and uri:
                # extract article number if ELI
                import re
                m = re.search(r"/articulo/(\d+)", uri)
                if m:
                    art_num = m.group(1)
                    num_p = URIRef(str(LO) + 'articleNumber')
                    for s,p,o in GRAPH.triples((None, num_p, None)):
                        if str(o).strip() == str(art_num).strip():
                            target_uris.append(str(s))
                else:
                    target_uris = [uri]

        print('precedents_for_article: target_uris=', target_uris)
        # aggregate results for all target articles (dedupe by case URI)
        aggregated = {}
        # If we have per-file graphs loaded, run searches in parallel across them for better performance
        # Always include the live merged GRAPH so newly ingested data is searched,
        # plus any per-file graphs if available.
        if isinstance(GRAPHS_BY_FILE, dict) and len(GRAPHS_BY_FILE) > 0:
            graphs_to_search = list(GRAPHS_BY_FILE.values()) + [GRAPH]
        else:
            graphs_to_search = [GRAPH]
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            futures = []
            with ThreadPoolExecutor(max_workers=min(8, max(1, len(graphs_to_search)))) as ex:
                for g in graphs_to_search:
                    for t in target_uris:
                        futures.append(ex.submit(precedent_processor.find_cases_for_article, g, t, jurisdiction, year, limit))
                for fut in as_completed(futures):
                    try:
                        res = fut.result()
                    except Exception:
                        continue
                    for item in (res or []):
                        case = item.get('case')
                        if not case:
                            continue
                        existing = aggregated.get(case)
                        if not existing:
                            aggregated[case] = item
                        else:
                            existing['score'] = max(existing.get('score', 0), item.get('score', 0))
                            existing['reasons'] = list(dict.fromkeys(existing.get('reasons', []) + item.get('reasons', [])))
        except Exception:
            # fallback to single-graph synchronous search
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


@APP.route('/cases_overview', methods=['GET'])
def cases_overview():
    """Return a flat list of cases/precedents and the articles/laws they are linked to.
    Useful for debugging data connections.
    """
    try:
        limit = int(request.args.get('limit') or 2000)
        LO = rdflib.Namespace('http://legalontosystem.pe/ontology#')
        menciona = rdflib.URIRef(str(LO) + 'mencionaArticulo')
        caso_t = rdflib.URIRef(str(LO) + 'Caso')
        prec_t = rdflib.URIRef(str(LO) + 'Precedente')
        art_num_p = rdflib.URIRef(str(LO) + 'articleNumber')
        titulo_p = rdflib.URIRef(str(LO) + 'titulo')
        fecha_p = rdflib.URIRef(str(LO) + 'fechaSentencia')
        jur_p = rdflib.URIRef(str(LO) + 'jurisdiccionCaso')
        crime_p = rdflib.URIRef(str(LO) + 'delitoLiteral')
        file_p = rdflib.URIRef(str(LO) + 'archivoFilename')
        tiene_art = rdflib.URIRef(str(LO) + 'tieneArticulo')
        has_art = rdflib.URIRef(str(LO) + 'hasArticle')

        subjects = set()
        for s in GRAPH.subjects(menciona, None):
            subjects.add(s)
        for s in GRAPH.subjects(rdflib.RDF.type, caso_t):
            subjects.add(s)
        for s in GRAPH.subjects(rdflib.RDF.type, prec_t):
            subjects.add(s)

        out = []
        for s in list(subjects)[:limit]:
            try:
                label = GRAPH.value(s, RDFS.label) or GRAPH.value(s, titulo_p)
                date = GRAPH.value(s, fecha_p)
                jur = GRAPH.value(s, jur_p)
                crime = GRAPH.value(s, crime_p)
                fname = GRAPH.value(s, file_p)
                arts = []
                for a in GRAPH.objects(s, menciona):
                    a_label = GRAPH.value(a, RDFS.label) or GRAPH.value(a, titulo_p)
                    a_num = GRAPH.value(a, art_num_p)
                    laws = []
                    for law in GRAPH.subjects(tiene_art, a):
                        laws.append({
                            'uri': str(law),
                            'label': str(GRAPH.value(law, RDFS.label) or GRAPH.value(law, titulo_p) or '')
                        })
                    for law in GRAPH.subjects(has_art, a):
                        laws.append({
                            'uri': str(law),
                            'label': str(GRAPH.value(law, RDFS.label) or GRAPH.value(law, titulo_p) or '')
                        })
                    arts.append({
                        'uri': str(a),
                        'label': str(a_label) if a_label else None,
                        'number': str(a_num) if a_num else None,
                        'laws': laws
                    })
                out.append({
                    'case': str(s),
                    'label': str(label) if label else None,
                    'date': str(date) if date else None,
                    'jurisdiction': str(jur) if jur else None,
                    'crime': str(crime) if crime else None,
                    'pdf': str(fname) if fname else None,
                    'articles': arts
                })
            except Exception:
                continue
        return jsonify({'count': len(out), 'results': out[:limit]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@APP.route('/graph_integrity', methods=['GET'])
def graph_integrity():
    """Quick integrity report: detect dangling references, missing labels/titles, and inconsistent article-law links.
    Returns counts and samples to help diagnose "Error al obtener entidad" issues from the frontend.
    """
    try:
        LO = rdflib.Namespace('http://legalontosystem.pe/ontology#')
        report = {
            'subjects': 0,
            'missing_titles': 0,
            'missing_titles_samples': [],
            'dangling_objects': 0,
            'dangling_samples': [],
            'article_without_law': 0,
            'article_without_law_samples': [],
            'law_without_articles': 0,
            'law_without_articles_samples': [],
        }
        # Count subjects
        subs = set(GRAPH.subjects(None, None))
        report['subjects'] = len(subs)
        # Missing label/titulo
        for s in list(subs)[:5000]:
            label = GRAPH.value(s, RDFS.label) or GRAPH.value(s, rdflib.URIRef(str(LO) + 'titulo'))
            if not label:
                report['missing_titles'] += 1
                if len(report['missing_titles_samples']) < 20:
                    report['missing_titles_samples'].append(str(s))
        # Dangling objects: objects that never appear as a subject (URIRefs only)
        objs = set(o for _,_,o in GRAPH.triples((None, None, None)) if isinstance(o, rdflib.term.Identifier))
        dangling = [o for o in objs if (o, None, None) not in GRAPH]
        report['dangling_objects'] = len(dangling)
        report['dangling_samples'] = [str(o) for o in dangling[:20]]
        # Articles without parent law
        art_t = rdflib.URIRef(str(LO) + 'Articulo')
        pertenece = rdflib.URIRef(str(LO) + 'perteneceALey')
        tiene = rdflib.URIRef(str(LO) + 'tieneArticulo')
        has = rdflib.URIRef(str(LO) + 'hasArticle')
        for a in GRAPH.subjects(RDF.type, art_t):
            parent = GRAPH.value(a, pertenece)
            if not parent:
                report['article_without_law'] += 1
                if len(report['article_without_law_samples']) < 20:
                    report['article_without_law_samples'].append(str(a))
        # Laws without any articles
        ley_t = rdflib.URIRef(str(LO) + 'Ley')
        for law in GRAPH.subjects(RDF.type, ley_t):
            has_any = False
            for _a in GRAPH.objects(law, tiene):
                has_any = True; break
            if not has_any:
                for _a in GRAPH.objects(law, has):
                    has_any = True; break
            if not has_any:
                report['law_without_articles'] += 1
                if len(report['law_without_articles_samples']) < 20:
                    report['law_without_articles_samples'].append(str(law))
        return jsonify(report)
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

            # Link the created document(s) AND any matching Caso by filename to the detected articles
            try:
                menciona_prop = rdflib.URIRef('http://legalontosystem.pe/ontology#mencionaArticulo')
                archivo_p = rdflib.URIRef('http://legalontosystem.pe/ontology#archivoFilename')
                caso_t = rdflib.URIRef('http://legalontosystem.pe/ontology#Caso')
                # For each detected article, attach mencionaArticulo to parent and to all part subjects (new or existing)
                parent_uri = rdflib.URIRef(RESOURCE_BASE + doc_id_base)
                # Try to discover existing Caso nodes that correspond to this PDF by filename
                matched_cases = set()
                try:
                    # exact match on filename
                    for s in GRAPH.subjects(archivo_p, rdflib.Literal(filename)):
                        matched_cases.add(s)
                    # secure_filename variant
                    sf = secure_filename(filename)
                    if sf != filename:
                        for s in GRAPH.subjects(archivo_p, rdflib.Literal(sf)):
                            matched_cases.add(s)
                    # some datasets store only the base name without extension
                    base_no_ext, _ext = os.path.splitext(filename)
                    for s in GRAPH.subjects(archivo_p, rdflib.Literal(base_no_ext)):
                        matched_cases.add(s)
                except Exception:
                    pass
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
                        # also attach to any matching Caso subjects (so precedent search finds real cases)
                        for csubj in matched_cases:
                            GRAPH.add((csubj, menciona_prop, art_uri))
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
    uri = _normalize_uri(uri)
    q = f"SELECT ?p ?o WHERE {{ <{uri}> ?p ?o }} LIMIT 1000"
    try:
        res = GRAPH.query(q)
        rows = []
        for r in res:
            rows.append({ 'p': str(r[0]), 'o': str(r[1]) })
        return jsonify({'uri':uri,'properties':rows})
    except Exception:
        # Fallback: scan triples directly without SPARQL
        try:
            from rdflib import URIRef
            sref = URIRef(uri)
            rows = []
            for p,o in GRAPH.predicate_objects(sref):
                rows.append({ 'p': str(p), 'o': str(o) })
            return jsonify({'uri': uri, 'properties': rows})
        except Exception as e2:
            return jsonify({'error': str(e2)}), 500

@APP.route('/resolve_entity', methods=['GET'])
def resolve_entity():
    """Resolve and return concise entity info, normalizing URIs and handling missing nodes gracefully.
    Query: ?uri=...
    Response: { uri, title, types: [...], exists: bool, properties: [...] }
    """
    uri = request.args.get('uri')
    if not uri:
        return jsonify({'error':'uri param required'}), 400
    try:
        uri = _normalize_uri(uri)
        from rdflib import URIRef
        sref = URIRef(uri)
        exists = (sref, None, None) in GRAPH
        LO = rdflib.URIRef('http://legalontosystem.pe/ontology#')
        title = GRAPH.value(sref, RDFS.label) or GRAPH.value(sref, rdflib.URIRef(str(LO) + 'titulo'))
        types = [str(t) for t in GRAPH.objects(sref, RDF.type)]
        props = []
        for p,o in GRAPH.predicate_objects(sref):
            props.append({ 'p': str(p), 'o': str(o) })
        return jsonify({ 'uri': uri, 'title': (str(title) if title else None), 'types': types, 'exists': bool(exists), 'properties': props })
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
