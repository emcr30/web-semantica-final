"""
Heuristics and SPARQL helpers to find and rank precedent cases for a given Article URI.
This is a pragmatic implementation using SPARQL queries + simple scoring based on:
 - direct precedent linkage (if precedents are modelled in the graph)
 - text similarity via simple substring/regex matching (rdflib SPARQL FILTER regex)
 - jurisdiction match and recency

Endpoints in `backend/app.py` call these functions to return ranked results.
"""
from rdflib import Graph
from typing import List, Dict, Any
import datetime
import logging

# module logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.DEBUG)

# scoring weights (tunable)
WEIGHT_DIRECT_PRECEDENT = 3.0
WEIGHT_TEXT_MATCH = 1.5
WEIGHT_JURISDICTION = 1.2
WEIGHT_RECENCY = 1.0


def find_cases_for_article(g: Graph, article_uri: str, jurisdiction: str = None, year: int = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Search graph for cases relevant to an article and return ranked list of cases.
    Strategy:
      1. Find cases that refer to precedents linked to the law/article (if such links exist)
      2. Find cases whose textual description contains substrings from the article text (simple heuristic)
      3. Combine and score by heuristics: direct precedent > textual match > jurisdiction > recency
    Returns list of dicts: {case: uri, score:float, reasons:[], properties...}
    """
    logger.debug(f"find_cases_for_article called: article_uri={article_uri} jurisdiction={jurisdiction} year={year} limit={limit}")
    results = {}
    # Determine candidate article URIs: include same article number across versions
    candidate_articles = [article_uri]
    try:
        import re
        from rdflib import URIRef, Literal
        from rdflib.namespace import XSD
        m = re.search(r"(\d+)(?!.*\d)", str(article_uri))
        if m:
            art_num_val = int(m.group(1))
            for s in g.subjects(URIRef('http://legalontosystem.pe/ontology#articleNumber'), Literal(art_num_val, datatype=XSD.integer)):
                su = str(s)
                if su not in candidate_articles:
                    candidate_articles.append(su)
    except Exception:
        logger.exception('error building candidate_articles')
    logger.debug(f"candidate_articles: {candidate_articles}")
    # 1) direct linkage: cases that explicitly mention the article (lo:mencionaArticulo)
    try:
        # query for each candidate article URI (covers other versioned URIs)
        for art_u in candidate_articles:
            # sanitize candidate URI to avoid accidental newlines or CRs breaking SPARQL
            safe_art_u = str(art_u).replace('\n', '').replace('\r', '')
            logger.debug(f"querying mentions for article candidate: {safe_art_u}")
            q_cases = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX lo: <http://legalontosystem.pe/ontology#>
            SELECT ?case ?caseLabel ?date WHERE {{
                ?case a lo:Caso .
                OPTIONAL {{ ?case rdfs:label ?caseLabel }}
                OPTIONAL {{ ?case lo.fechaSentencia ?date }}
                ?case lo:mencionaArticulo <{safe_art_u}> .
            }} LIMIT {limit}
            """
            logger.debug('q_cases: >>START>>\n' + q_cases + '\n<<END>>')
            for row in g.query(q_cases):
                case = str(row.case)
                logger.debug(f"matched case {case} for article {art_u}")
                score = results.get(case, {}).get('score', 0)
                score += WEIGHT_DIRECT_PRECEDENT
                ent = results.get(case, {})
                ent.update({
                    'case': case,
                    'label': ent.get('label') or (str(row.caseLabel) if row.caseLabel else None),
                    'score': score,
                    'date': ent.get('date') or (str(row.date) if row.date else None),
                })
                ent['reasons'] = ent.get('reasons', []) + [f'mentions_article_{art_u}']
                results[case] = ent
    except Exception:
        logger.exception('error querying direct mentions')

    # 1b) legacy pattern: if a law explicitly has lo.tienePrecedente linking to precedent nodes
    q_direct = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX lo: <http://legalontosystem.pe/ontology#>
    SELECT ?case ?caseLabel ?prec ?precLabel ?date WHERE {{
      ?case a lo:Caso .
      OPTIONAL {{ ?case rdfs:label ?caseLabel }}
      OPTIONAL {{ ?case lo.refierePrecedente ?prec . ?prec rdfs:label ?precLabel }}
      OPTIONAL {{ ?case lo.fechaSentencia ?date }}
      ?law lo.tieneArticulo <{article_uri}> .
      ?law lo.tienePrecedente ?prec .
    }} LIMIT {limit}
    """
    try:
        for row in g.query(q_direct):
            case = str(row.case)
            logger.debug(f"legacy pattern matched case {case} via prec {row.prec}")
            score = results.get(case, {}).get('score', 0)
            score += WEIGHT_DIRECT_PRECEDENT
            ent = results.get(case, {})
            ent.update({
                'case': case,
                'label': ent.get('label') or (str(row.caseLabel) if row.caseLabel else None),
                'score': score,
                'matched_prec': str(row.prec) if row.prec else None,
                'date': ent.get('date') or (str(row.date) if row.date else None),
            })
            ent['reasons'] = ent.get('reasons', []) + ['direct_precedent']
            results[case] = ent
    except Exception:
        pass

    # 2) text-match heuristic: compare article text to case texto (substring / regex)
    # fetch article text first: try lo:texto, then fallback to lo:contenido or rdfs:label
    article_text = None
    try:
        q_article = f"""
        PREFIX lo: <http://legalontosystem.pe/ontology#>
        SELECT ?texto ?contenido ?label WHERE {{
          OPTIONAL {{ <{article_uri}> lo.texto ?texto }}
          OPTIONAL {{ <{article_uri}> lo.contenido ?contenido }}
          OPTIONAL {{ <{article_uri}> rdfs:label ?label }}
        }} LIMIT 1
        """
        for r in g.query(q_article):
            if getattr(r, 'texto', None):
                article_text = str(r.texto)
            elif getattr(r, 'contenido', None):
                article_text = str(r.contenido)
            elif getattr(r, 'label', None):
                article_text = str(r.label)
            break
    except Exception:
        article_text = None

    if article_text:
        # take short representative phrases to match (first 200 chars)
        snippet = article_text[:200].replace('"','\\"')
        q_text = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX lo: <http://legalontosystem.pe/ontology#>
        SELECT ?case ?caseLabel ?date WHERE {{
          ?case a lo:Caso .
          OPTIONAL {{ ?case rdfs:label ?caseLabel }}
          OPTIONAL {{ ?case lo.texto ?ctext }}
          FILTER regex(str(?ctext), "{snippet}", "i")
          OPTIONAL {{ ?case lo.fechaSentencia ?date }}
        }} LIMIT {limit}
        """
        try:
            for row in g.query(q_text):
                case = str(row.case)
                score = results.get(case, { 'score': 0 })['score'] if case in results else 0
                score += WEIGHT_TEXT_MATCH
                ent = results.get(case, {})
                ent.update({
                    'case': case,
                    'label': ent.get('label') or (str(row.caseLabel) if row.caseLabel else None),
                    'score': score,
                    'date': ent.get('date') or (str(row.date) if row.date else None),
                })
                ent['reasons'] = ent.get('reasons', []) + ['text_match']
                results[case] = ent
        except Exception:
            pass

    # 3) jurisdiction & recency boosting and filter by year/jurisdiction if requested
    final = []
    for case_uri, meta in results.items():
        score = meta.get('score', 0.0)
        # jurisdiction
        if jurisdiction:
            # try to query the case jurisdiction and compare (best-effort)
            try:
                q_j = f"""
                PREFIX lo: <http://legalontosystem.pe/ontology#>
                SELECT ?jur WHERE {{ <{case_uri}> lo.jurisdiccionCaso ?jur }} LIMIT 1
                """
                jur = None
                for r in g.query(q_j):
                    jur = str(r.jur) if r.jur else None
                if jur and jurisdiction.lower() in jur.lower():
                    score *= WEIGHT_JURISDICTION
                    meta['reasons'].append('jurisdiction_match')
                elif jurisdiction and jur and jurisdiction.lower() not in jur.lower():
                    # if jurisdiction filter requested but doesn't match, skip
                    continue
            except Exception:
                pass
        # recency
        if meta.get('date'):
            try:
                y = int(str(meta.get('date'))[:4])
                age = max(0, datetime.datetime.now().year - y)
                # boost more recent cases
                score *= (1.0 + WEIGHT_RECENCY / (1.0 + age))
            except Exception:
                pass
        # filter by year if requested
        if year:
            if meta.get('date'):
                try:
                    y = int(str(meta.get('date'))[:4])
                    if y != int(year):
                        continue
                except Exception:
                    pass
        meta['score'] = score
        final.append(meta)

    # sort by score desc
    final_sorted = sorted(final, key=lambda x: x.get('score', 0), reverse=True)
    return final_sorted[:limit]
