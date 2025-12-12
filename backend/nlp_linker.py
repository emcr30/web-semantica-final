"""
nlp_linker.py

Módulo combinado:
- Extracción de referencias jurídicas (artículos, leyes, entidades, keywords) usando spaCy + regex robustos.
- Resolución de IRIs de artículos/leyes en un grafo rdflib (busca por lo:articleNumber, lo:numero, rdfs:label).
- Integración con la función `find_cases_for_article` (heurística SPARQL) para recuperar precedentes.

Uso principal:
    from rdflib import Graph
    from nlp_linker import extract_and_link

    g = Graph()
    g.parse("legal_working.ttl", format="ttl")
    out = extract_and_link(text, g)
    # out['article_uris'] -> list de IRIs detectados
    # out['precedents'] -> dict article_uri -> [ranked cases]
"""

import re
import logging
import datetime
from typing import List, Dict, Any, Set, Iterable

import spacy
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import XSD, RDFS

# --- logging ---
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# --- spaCy model (Spanish) ---
try:
    nlp = spacy.load("es_core_news_sm")
except OSError:
    logger.warning("es_core_news_sm not found. Using blank es model. Install with: python -m spacy download es_core_news_sm")
    nlp = spacy.blank("es")

# --- Ontology namespace (local) ---
LO = Namespace("http://legalontosystem.pe/ontology#")

# --- Regexes (mejorados) ---
# Detects: "Artículo 189", "Art. 189-A", "art 108°", "art. 108 inciso 1", "ARTÍCULO 189-A"
ARTICLE_RE = re.compile(
    r'\b(?:art(?:ículo)?\.?)\s*([0-9]{1,4}(?:[A-Za-z°º\-]{0,6}))',
    re.IGNORECASE
)

# Detects: "Ley 30364", "Ley N° 30364", "Decreto Supremo 008-2020-MIMP", "D.L. 295"
LAW_NUMBER_RE = re.compile(
    r'\b(?:ley|decreto(?:\s+supremo)?|d\.?l\.?|d\.?s\.?)\s*(?:n(?:º|°|o)?\.?\s*)?([0-9]{1,5}(?:-[0-9]{2,4}(?:-[A-Za-z\-]+)?)?)\b',
    re.IGNORECASE
)

# Keyword patterns (sencillos; amplía según tu dominio)
KEYWORD_PATTERNS = [
    r'\b(?:delito|crimen|fraude|robo|homicidio|violencia|asesin(?:o|ar|ado)?|muerte|matar|apuñalad[oa]?)\b',
    r'\b(?:contrato|acuerdo|obligación|responsabilidad)\b',
    r'\b(?:derecho|deber|libertad|propiedad)\b',
    r'\b(?:pena|sanción|multa|prisión|reclusión)\b',
]

# --- Extractors (limpios) ---


def _process_chunk(chunk_text_content: str) -> List[Dict[str, str]]:
    """Procesa un chunk con spaCy y devuelve entidades seleccionadas."""
    try:
        doc = nlp(chunk_text_content)
    except Exception:
        return []
    ents = []
    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG", "GPE", "MISC"}:
            ents.append({'text': ent.text.strip(), 'label': ent.label_})
    return ents


def extract_entities(text: str, max_len: int = 100000, overlap: int = 2000) -> Dict[str, Any]:
    """
    Extrae artículos, leyes, entidades y keywords desde `text`.
    No realiza resolución a IRIs - solo extracción de cadenas/valores.
    """
    out = {'articles_raw': [], 'laws_raw': [], 'entities': [], 'keywords': []}
    if not text:
        return out

    # Detect article references con regex
    arts = ARTICLE_RE.findall(text)
    # Normalize: strip spaces and upper-case letters on suffix (e.g., '189-A')
    normalized_arts = []
    for a in arts:
        a_clean = a.replace("°", "").replace("º", "").replace(" ", "")
        a_clean = a_clean.upper()
        normalized_arts.append(a_clean)
    out['articles_raw'] = list(dict.fromkeys(normalized_arts))

    # Detect law refs
    laws = LAW_NUMBER_RE.findall(text)
    out['laws_raw'] = [l.strip() for l in dict.fromkeys(laws)]

    # Keywords
    kws = []
    for pat in KEYWORD_PATTERNS:
        kws += re.findall(pat, text, flags=re.IGNORECASE)
    out['keywords'] = list(dict.fromkeys(kws))

    # spaCy entities by chunking to avoid max_length
    entities = []
    seen = set()
    # simple chunker by characters (chunk_texter)
    start = 0
    L = len(text)
    while start < L:
        end = min(start + max_len, L)
        chunk = text[start:end]
        ents = _process_chunk(chunk)
        for e in ents:
            key = (e['text'].lower(), e['label'])
            if key not in seen:
                seen.add(key)
                entities.append(e)
        if end == L:
            break
        start = end - overlap if end - overlap > start else end
    out['entities'] = entities
    return out


# --- Resolving helpers: buscan en el grafo IRIs de artículos/leyes ---


def resolve_article_uris_from_number(g: Graph, number_raw: str) -> List[str]:
    """
    Intenta resolver número de artículo (e.g., "189", "189-A") a URIs en el grafo.
    Busca primero por lo:articleNumber (xsd:int) y luego por otras propiedades (lo:numero, rdfs:label).
    Devuelve lista de URIs (strings).
    """
    out = []
    # extraer solo dígitos iniciales para buscar articleNumber int
    m = re.match(r'(\d+)', number_raw)
    try:
        if m:
            num = int(m.group(1))
            for s in g.subjects(LO.articleNumber, Literal(num, datatype=XSD.integer)):
                out.append(str(s))
            if out:
                return list(dict.fromkeys(out))
    except Exception:
        logger.exception("error resolving articleNumber as integer")

    # fallback 1: búsqueda por lo:numero literal (cadena o int)
    try:
        for s in g.subjects(LO.numero, None):
            # si existe la propiedad, evaluar su literal
            val = g.value(s, LO.numero)
            if val and re.search(r'\b' + re.escape(str(number_raw)) + r'\b', str(val), flags=re.IGNORECASE):
                out.append(str(s))
    except Exception:
        pass
    if out:
        return list(dict.fromkeys(out))

    # fallback 2: buscar en rdfs:label o lo:contenido donde aparezca "Artículo 189"
    try:
        pattern = re.compile(r'Artículo\s+' + re.escape(number_raw), re.IGNORECASE)
        for s, p, o in g.triples((None, RDFS.label, None)):
            if o and pattern.search(str(o)):
                out.append(str(s))
    except Exception:
        pass

    return list(dict.fromkeys(out))


def resolve_law_uris_from_raw(g: Graph, law_raw: str) -> List[str]:
    """
    Resolver una referencia de ley detectada (e.g., '30364', '008-2020-MIMP') a URIs de ley en el grafo.
    Busca por varias propiedades conocidas (ej. lo:numeroNorma, lo:numero, rdfs:label).
    """
    out = []
    lr = law_raw.strip()
    # intentar extraer dígitos iniciales
    m = re.search(r'(\d{2,6})', lr)
    try:
        if m:
            num = m.group(1)
            # buscar en lo:numeroNorma, lo:numero o lo:numeroNorma como literal conteniendo num
            for subj, pred, obj in g.triples((None, LO.numeroNorma, None)):
                if obj and num in str(obj):
                    out.append(str(subj))
            for subj, pred, obj in g.triples((None, LO.numero, None)):
                if obj and num in str(obj):
                    out.append(str(subj))
            for subj, pred, obj in g.triples((None, LO.numeroNorma, None)):
                if obj and num in str(obj):
                    out.append(str(subj))
            if out:
                return list(dict.fromkeys(out))
    except Exception:
        logger.exception("error resolving law by numeric fragment")

    # fallback: buscar labels que contengan "Ley" + número
    try:
        pat = re.compile(r'Ley\s*\.?\s*' + re.escape(lr), re.IGNORECASE)
        for s, p, o in g.triples((None, RDFS.label, None)):
            if o and pat.search(str(o)):
                out.append(str(s))
    except Exception:
        pass

    return list(dict.fromkeys(out))


# --- Integración con función de precedentes (find_cases_for_article) ---
# A continuación incluimos una versión adaptada de la función que nos diste,
# con pequeñas defensas y reutilizable en este módulo.

WEIGHT_DIRECT_PRECEDENT = 3.0
WEIGHT_TEXT_MATCH = 1.5
WEIGHT_JURISDICTION = 1.2
WEIGHT_RECENCY = 1.0


def find_cases_for_article(g: Graph, article_uri: str, jurisdiction: str = None, year: int = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Heurística SPARQL + ranking para encontrar precedentes relevantes para `article_uri`.
    Reutiliza la lógica base que usas en backend/app.py, pero con defensas y retornos consistentes.
    """
    logger.debug(f"find_cases_for_article: article_uri={article_uri} jurisdiction={jurisdiction} year={year} limit={limit}")
    results: Dict[str, Dict[str, Any]] = {}

    # --- 1) direct linkage: casos que mencionan directamente el artículo ---
    try:
        for case in g.subjects(LO.mencionaArticulo, URIRef(article_uri)):
            case_uri = str(case)
            # intentar obtener label y fecha
            label = g.value(case, RDFS.label)
            date = g.value(case, LO.fechaSentencia)
            ent = results.get(case_uri, {})
            ent['case'] = case_uri
            ent['label'] = ent.get('label') or (str(label) if label else None)
            ent['date'] = ent.get('date') or (str(date) if date else None)
            ent['score'] = ent.get('score', 0.0) + WEIGHT_DIRECT_PRECEDENT
            ent['reasons'] = ent.get('reasons', []) + [f'mentions_article_{article_uri}']
            results[case_uri] = ent
    except Exception:
        logger.exception("error enumerating direct mentions via triples")

    # --- 1b) legacy pattern: law -> tienePrecedente -> precedent; then find cases pointing to those precedents ---
    try:
        for law in g.subjects(LO.tieneArticulo, URIRef(article_uri)):
            # ley que contiene el artículo
            for prec in g.objects(law, LO.tienePrecedente):
                # buscar casos que refieran a ese precedente (prec puede ser recurso o literal)
                for case in g.subjects(LO.refierePrecedente, prec):
                    case_uri = str(case)
                    label = g.value(case, RDFS.label)
                    date = g.value(case, LO.fechaSentencia)
                    ent = results.get(case_uri, {})
                    ent['case'] = case_uri
                    ent['label'] = ent.get('label') or (str(label) if label else None)
                    ent['date'] = ent.get('date') or (str(date) if date else None)
                    ent['score'] = ent.get('score', 0.0) + WEIGHT_DIRECT_PRECEDENT
                    ent['matched_prec'] = str(prec)
                    ent['reasons'] = ent.get('reasons', []) + ['direct_precedent_via_law']
                    results[case_uri] = ent
    except Exception:
        logger.exception("error resolving tienePrecedente pattern")

    # --- 2) text-match heuristic using article text snippet vs case lo:texto ---
    article_text = None
    try:
        # try lo:texto, lo:contenido, rdfs:label on the article resource
        art_uri_ref = URIRef(article_uri)
        txt = g.value(art_uri_ref, LO.texto) or g.value(art_uri_ref, LO.contenido) or g.value(art_uri_ref, RDFS.label)
        if txt:
            article_text = str(txt)
    except Exception:
        article_text = None

    if article_text:
        snippet = article_text[:200].replace('"', '\\"')
        # simple substring matching: iterate cases and find lo:texto containing snippet
        try:
            for case in g.subjects(RDF := None, None):  # iterate subjects (we'll filter below)
                # ensure it's a Caso
                if (URIRef(case), None, None) is None:
                    pass
            # Instead of iterating all triples (costly), use subjects with lo:texto
            for case in g.subjects(LO.texto, None):
                ctext = g.value(case, LO.texto)
                if ctext and snippet.lower() in str(ctext).lower():
                    case_uri = str(case)
                    label = g.value(case, RDFS.label)
                    date = g.value(case, LO.fechaSentencia)
                    ent = results.get(case_uri, {})
                    ent['case'] = case_uri
                    ent['label'] = ent.get('label') or (str(label) if label else None)
                    ent['date'] = ent.get('date') or (str(date) if date else None)
                    ent['score'] = ent.get('score', 0.0) + WEIGHT_TEXT_MATCH
                    ent['reasons'] = ent.get('reasons', []) + ['text_match']
                    results[case_uri] = ent
        except Exception:
            logger.exception("error in text-match step")

    # --- 3) jurisdiction & recency boosting & filters ---
    final = []
    for case_uri, meta in results.items():
        score = meta.get('score', 0.0)
        # jurisdiction filter/boost
        if jurisdiction:
            try:
                jur = g.value(URIRef(case_uri), LO.jurisdiccionCaso)
                if jur and jurisdiction.lower() in str(jur).lower():
                    score *= WEIGHT_JURISDICTION
                    meta['reasons'].append('jurisdiction_match')
                else:
                    # if requested jurisdiction doesn't match, skip case
                    continue
            except Exception:
                pass
        # recency boost
        try:
            if meta.get('date'):
                y = int(str(meta.get('date'))[:4])
                age = max(0, datetime.datetime.now().year - y)
                score *= (1.0 + WEIGHT_RECENCY / (1.0 + age))
        except Exception:
            pass
        # year filter
        if year:
            try:
                if meta.get('date'):
                    y = int(str(meta.get('date'))[:4])
                    if y != int(year):
                        continue
            except Exception:
                pass
        meta['score'] = score
        final.append(meta)
    final_sorted = sorted(final, key=lambda x: x.get('score', 0.0), reverse=True)
    return final_sorted[:limit]


# --- Función de nivel superior que une extracción y vinculación ---


def extract_and_link(text: str, g: Graph, jurisdiction: str = None, year: int = None, max_cases_per_article: int = 20) -> Dict[str, Any]:
    """
    Flujo completo:
      1. Extrae referencias (extract_entities)
      2. Resuelve artículos y leyes en el grafo (resolve_article_uris_from_number / resolve_law_uris_from_raw)
      3. Para cada artículo IRI encontrado, llama a find_cases_for_article(...) y devuelve precedentes rankeados
    Retorna:
      {
        'extraction': { ... },
        'article_uris': [...],
        'law_uris': [...],
        'precedents': { article_uri: [cases...] }
      }
    """
    logger.info("extract_and_link: starting extraction")
    extraction = extract_entities(text)
    article_raws = extraction.get('articles_raw', [])
    law_raws = extraction.get('laws_raw', [])

    # Resolve articles
    article_uris: List[str] = []
    for a in article_raws:
        try:
            found = resolve_article_uris_from_number(g, a)
            if found:
                article_uris.extend(found)
            else:
                logger.debug(f"No URI resolved for article raw '{a}'")
        except Exception:
            logger.exception("error resolving article raw")

    # Resolve laws
    law_uris: List[str] = []
    for l in law_raws:
        try:
            found = resolve_law_uris_from_raw(g, l)
            if found:
                law_uris.extend(found)
            else:
                logger.debug(f"No URI resolved for law raw '{l}'")
        except Exception:
            logger.exception("error resolving law raw")

    # Deduplicate
    article_uris = list(dict.fromkeys(article_uris))
    law_uris = list(dict.fromkeys(law_uris))

    # For each resolved article URI, call find_cases_for_article
    precedents: Dict[str, List[Dict[str, Any]]] = {}
    for art in article_uris:
        try:
            cases = find_cases_for_article(g, art, jurisdiction=jurisdiction, year=year, limit=max_cases_per_article)
            precedents[art] = cases
        except Exception:
            logger.exception(f"error finding cases for article {art}")
            precedents[art] = []

    return {
        'extraction': extraction,
        'article_uris': article_uris,
        'law_uris': law_uris,
        'precedents': precedents
    }
