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
    results = {}
    # 1) direct precedent linkage: if Ontology has :tienePrecedente (law -> precedent) and cases refer to precedents
    q_direct = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX lo: <http://legalontosystem.pe/ontology#>
    SELECT ?case ?caseLabel ?prec ?precLabel ?date WHERE {{
      ?case a lo:Caso .
      OPTIONAL {{ ?case rdfs:label ?caseLabel }}
      OPTIONAL {{ ?case lo.refierePrecedente ?prec . ?prec rdfs:label ?precLabel }}
      OPTIONAL {{ ?case lo.fechaSentencia ?date }}
      # try to find precedents that are connected to article's law
      ?law lo.tieneArticulo <{article_uri}> .
      ?law lo.tienePrecedente ?prec .
    }} LIMIT {limit}
    """
    try:
        for row in g.query(q_direct):
            case = str(row.case)
            score = results.get(case, { 'score': 0 })['score'] if case in results else 0
            score += WEIGHT_DIRECT_PRECEDENT
            results[case] = {
                'case': case,
                'label': str(row.caseLabel) if row.caseLabel else None,
                'score': score,
                'matched_prec': str(row.prec) if row.prec else None,
                'date': str(row.date) if row.date else None,
                'reasons': results.get(case, {}).get('reasons', []) + ['direct_precedent']
            }
    except Exception:
        # query may fail if patterns not present; ignore and continue
        pass

    # 2) text-match heuristic: compare article text to case texto (substring / regex)
    # fetch article text first
    article_text = None
    try:
        q_article = f"""
        PREFIX lo: <http://legalontosystem.pe/ontology#>
        SELECT ?texto WHERE {{ <{article_uri}> lo.texto ?texto }} LIMIT 1
        """
        for r in g.query(q_article):
            article_text = str(r.texto)
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
