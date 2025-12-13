from SPARQLWrapper import SPARQLWrapper, JSON
import spacy
import numpy as np
import re
from typing import Any, Dict, List
from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDFS

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

ENDPOINT = "http://localhost:7200/repositories/legal"
try:
    nlp = spacy.load("es_core_news_md")
except Exception:
    try:
        # fallback to small Spanish model if available
        nlp = spacy.load("es_core_news_sm")
    except Exception:
        # final fallback: blank Spanish pipeline (no vectors, limited features)
        nlp = spacy.blank("es")

def run_query(q):
    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setQuery(q)
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()


# ---------------------------------------------------------
# 0. UTILITY: EMBEDDINGS
# ---------------------------------------------------------

def embed(text):
    if text is None:
        return np.zeros(300)
    return nlp(text).vector


def cosine(a, b):
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b)))


# ---------------------------------------------------------
# 1. EXTRACCIÓN DE ARTÍCULOS CANDIDATOS POR NÚMERO MENCIONADO
# ---------------------------------------------------------

def extract_candidate_articles(text):
    numbers = re.findall(r'\b\d{1,3}\b', text)
    candidates = []

    for n in numbers:
        q = f"""
        PREFIX lo: <http://legalontosystem.pe/ontology#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT ?art ?contenido ?version
        WHERE {{
           ?art lo:articleNumber {n}^^xsd:int .
           OPTIONAL {{ ?art lo:contenido ?contenido . }}
           OPTIONAL {{ ?art lo:belongsTo ?version . }}
        }}
        """
        res = run_query(q)

        for b in res["results"]["bindings"]:
            candidates.append({
                "uri": b["art"]["value"],
                "contenido": b.get("contenido", {}).get("value", ""),
                "version": b.get("version", {}).get("value", "")
            })

    return candidates


# ---------------------------------------------------------
# 2. BUSCAR CASOS SIMILARES SEMÁNTICAMENTE (spaCy)
# ---------------------------------------------------------

def search_related_cases_semantic(text, k=20):
    query = f"""
    PREFIX lo: <http://legalontosystem.pe/ontology#>
    SELECT ?case ?resumen ?fundamentos ?sentencia
    WHERE {{
        ?case a lo:Caso .
        OPTIONAL {{ ?case lo:resumen ?resumen . }}
        OPTIONAL {{ ?case lo:fundamentos ?fundamentos . }}
        OPTIONAL {{ ?case lo:sentenciaTexto ?sentencia . }}
    }}
    """

    res = run_query(query)

    text_vec = embed(text)
    results = []

    for b in res["results"]["bindings"]:
        resumen = b.get("resumen", {}).get("value", "")
        fundamentos = b.get("fundamentos", {}).get("value", "")
        sentencia = b.get("sentencia", {}).get("value", "")
        combined = " ".join([resumen, fundamentos, sentencia])

        sim = cosine(text_vec, embed(combined))
        results.append({
            "uri": b["case"]["value"],
            "score_semantic": sim,
            "resumen": resumen,
            "fundamentos": fundamentos,
            "sentencia": sentencia
        })

    results = sorted(results, key=lambda x: x["score_semantic"], reverse=True)
    return results[:k]


# ---------------------------------------------------------
# 3. EXTRAER ARTÍCULOS MENCIONADOS EN ESOS CASOS
# ---------------------------------------------------------

def extract_articles_from_cases(case_list):
    arts = set()
    for c in case_list:
        q = f"""
        PREFIX lo: <http://legalontosystem.pe/ontology#>
        SELECT ?art
        WHERE {{
            <{c['uri']}> lo:mencionaArticulo ?art .
        }}
        """
        res = run_query(q)
        for b in res["results"]["bindings"]:
            arts.add(b["art"]["value"])
    return list(arts)


# ---------------------------------------------------------
# 4. EXTRAER ARTÍCULOS POR PRECEDENTES INVOCADOS
# ---------------------------------------------------------

def extract_articles_by_precedent(case_list):
    arts = set()

    for c in case_list:
        q = f"""
        PREFIX lo: <http://legalontosystem.pe/ontology#>
        SELECT ?art
        WHERE {{
            <{c['uri']}> lo:invocaPrecedente ?prec .
            ?art lo:tienePrecedente ?prec .
        }}
        """
        res = run_query(q)
        for b in res["results"]["bindings"]:
            arts.add(b["art"]["value"])
    return list(arts)


# ---------------------------------------------------------
# 5. EMBEDDINGS ENTRE TEXTO DEL CASO Y TEXTO DEL ARTÍCULO
# ---------------------------------------------------------

def semantic_similarity_with_article(text, article_uri):
    q = f"""
    PREFIX lo: <http://legalontosystem.pe/ontology#>
    SELECT ?cont
    WHERE {{
        <{article_uri}> lo:contenido ?cont .
    }}
    """
    res = run_query(q)

    if not res["results"]["bindings"]:
        return 0.0

    art_text = res["results"]["bindings"][0]["cont"]["value"]
    return cosine(embed(text), embed(art_text))


# ---------------------------------------------------------
# 6. RANKING HÍBRIDO
# ---------------------------------------------------------

def recommend_articles(text):
    # A: Extraer candidatos por número
    by_number = extract_candidate_articles(text)

    # B: Casos similares semánticos
    related_cases = search_related_cases_semantic(text)

    # C: Artículos mencionados en esos casos
    from_cases = extract_articles_from_cases(related_cases)

    # D: Artículos conectados por precedentes
    by_precedent = extract_articles_by_precedent(related_cases)

    # E: Ranking final combinado
    score = {}

    # Pesos base
    W_NUMBER = 3
    W_CASE = 2
    W_PRECEDENT = 1
    W_EMBED = 5

    # A) Artículos mencionados explícitamente por número
    for a in by_number:
        score[a["uri"]] = score.get(a["uri"], 0) + W_NUMBER

    # B) Artículos de casos similares
    for a in from_cases:
        score[a] = score.get(a, 0) + W_CASE

    # C) Artículos por precedentes
    for a in by_precedent:
        score[a] = score.get(a, 0) + W_PRECEDENT

    # D) Similitud semántica artículo – texto del caso
    for art in list(score.keys()):
        sem = semantic_similarity_with_article(text, art)
        score[art] += sem * W_EMBED

    ranked = sorted(score.items(), key=lambda x: x[1], reverse=True)

    return {
        "ranking": ranked,
        "from_number": by_number,
        "related_cases": related_cases,
        "from_cases": from_cases,
        "from_precedents": by_precedent
    }


# ---------------------------------------------------------
# 7. FIND CASES FOR ARTICLE (Graph scan, no SPARQL)
#    Used by backend /precedents_for_article endpoint.
# ---------------------------------------------------------

LO = Namespace('http://legalontosystem.pe/ontology#')

WEIGHT_DIRECT_PRECEDENT = 3.0
WEIGHT_TEXT_MATCH = 1.5
WEIGHT_JURISDICTION = 1.2
WEIGHT_RECENCY = 1.0


def find_cases_for_article(g: Graph, article_uri: str, jurisdiction: str = None, year: int = None, limit: int = 50) -> List[Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    art_ref = URIRef(article_uri)

    def _norm(u: str) -> str:
        if not u:
            return ''
        s = str(u).strip().replace('\n','').replace('\r','')
        s = s.replace('http://', 'https://')
        if s.endswith('/'):
            s = s[:-1]
        return s.lower()

    target_norm = _norm(article_uri)
    target_num = None
    m = re.search(r"/articulo/(\d+)$", target_norm)
    if m:
        target_num = m.group(1)

    # 1) Casos que mencionan directamente el artículo
    try:
        for case in g.subjects(LO.mencionaArticulo, art_ref):
            case_uri = str(case)
            label = g.value(case, RDFS.label)
            date = g.value(case, LO.fechaSentencia)
            ent = results.get(case_uri, {})
            ent['case'] = case_uri
            if label and not ent.get('label'):
                ent['label'] = str(label)
            if date and not ent.get('date'):
                ent['date'] = str(date)
            ent['score'] = ent.get('score', 0.0) + WEIGHT_DIRECT_PRECEDENT
            ent['reasons'] = list(dict.fromkeys(ent.get('reasons', []) + [f'mentions_article_{article_uri}']))
            results[case_uri] = ent
    except Exception:
        pass

    # 1a) Fallback tolerante: comparar por URI normalizada o por número del artículo
    try:
        for case, _, art in g.triples((None, LO.mencionaArticulo, None)):
            a_norm = _norm(art)
            matched = False
            if a_norm == target_norm:
                matched = True
            elif target_num:
                m2 = re.search(r"/articulo/(\d+)$", a_norm)
                if m2 and m2.group(1) == target_num:
                    matched = True
            if not matched:
                continue
            case_uri = str(case)
            label = g.value(case, RDFS.label)
            date = g.value(case, LO.fechaSentencia)
            ent = results.get(case_uri, {})
            ent['case'] = case_uri
            if label and not ent.get('label'):
                ent['label'] = str(label)
            if date and not ent.get('date'):
                ent['date'] = str(date)
            ent['score'] = ent.get('score', 0.0) + WEIGHT_DIRECT_PRECEDENT
            ent['reasons'] = list(dict.fromkeys(ent.get('reasons', []) + ['mentions_article_fuzzy']))
            results[case_uri] = ent
    except Exception:
        pass

    # 1b) Patrón legado: ley -> tieneArticulo/hasArticle -> artículo; ley -> tienePrecedente -> prec; caso -> refierePrecedente -> prec
    try:
        for prop_name in ('tieneArticulo', 'hasArticle'):
            prop = URIRef(str(LO) + prop_name)
            for law in g.subjects(prop, art_ref):
                for prec in g.objects(law, LO.tienePrecedente):
                    for case in g.subjects(LO.refierePrecedente, prec):
                        case_uri = str(case)
                        label = g.value(case, RDFS.label)
                        date = g.value(case, LO.fechaSentencia)
                        ent = results.get(case_uri, {})
                        ent['case'] = case_uri
                        if label and not ent.get('label'):
                            ent['label'] = str(label)
                        if date and not ent.get('date'):
                            ent['date'] = str(date)
                        ent['score'] = ent.get('score', 0.0) + WEIGHT_DIRECT_PRECEDENT
                        ent['matched_prec'] = str(prec)
                        ent['reasons'] = list(dict.fromkeys(ent.get('reasons', []) + ['direct_precedent_via_law']))
                        results[case_uri] = ent
    except Exception:
        pass

    # 2) Heurística simple: si el caso contiene texto con parte del contenido del artículo
    #    (evitamos consultas costosas; usamos un snippet del artículo)
    article_text = None
    try:
        txt = g.value(art_ref, LO.texto) or g.value(art_ref, LO.contenido) or g.value(art_ref, RDFS.label)
        if txt:
            article_text = str(txt)
    except Exception:
        article_text = None

    if article_text:
        snippet = article_text[:200].lower()
        try:
            for case in set(g.subjects(LO.texto, None)):
                ctext = g.value(case, LO.texto)
                if ctext and snippet in str(ctext).lower():
                    case_uri = str(case)
                    label = g.value(case, RDFS.label)
                    date = g.value(case, LO.fechaSentencia)
                    ent = results.get(case_uri, {})
                    ent['case'] = case_uri
                    if label and not ent.get('label'):
                        ent['label'] = str(label)
                    if date and not ent.get('date'):
                        ent['date'] = str(date)
                    ent['score'] = ent.get('score', 0.0) + WEIGHT_TEXT_MATCH
                    ent['reasons'] = list(dict.fromkeys(ent.get('reasons', []) + ['text_match']))
                    results[case_uri] = ent
        except Exception:
            pass

    # 3) Filtros/boost por jurisdicción y año (si se proporcionan)
    final: List[Dict[str, Any]] = []
    for case_uri, meta in results.items():
        score = meta.get('score', 0.0)
        if jurisdiction:
            jur = g.value(URIRef(case_uri), LO.jurisdiccionCaso)
            if jur and jurisdiction.lower() in str(jur).lower():
                score *= WEIGHT_JURISDICTION
                meta['reasons'] = list(dict.fromkeys(meta.get('reasons', []) + ['jurisdiction_match']))
            else:
                # si la jurisdicción solicitada no coincide, descartamos
                continue
        # filtro por año exacto si está disponible
        if year:
            try:
                d = meta.get('date') or g.value(URIRef(case_uri), LO.fechaSentencia)
                if d and str(d)[:4] != str(year):
                    continue
            except Exception:
                pass
        meta['score'] = score
        final.append(meta)

    final_sorted = sorted(final, key=lambda x: x.get('score', 0.0), reverse=True)
    return final_sorted[:limit]
