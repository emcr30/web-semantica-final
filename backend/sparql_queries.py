def search_laws_by_text(q: str):
    # busca etiquetas y textos que contengan q (case-insensitive)
    q_esc = q.replace('"','\\"')
    return f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX ex: <http://example.org/legal#>
    SELECT ?law ?title WHERE {{
      ?law a ex:Ley ;
           rdfs:label ?title .
      FILTER regex(str(?title), "{q_esc}", "i")
    }} LIMIT 50
    """


def example_precedent_query():
    return """
    PREFIX ex: <http://example.org/legal#>
    SELECT ?case ?precedent WHERE {
      ?case a ex:Caso ; ex.tienePrecedente ?precedent .
    } LIMIT 100
    """


def find_applicable_laws_query(case_uri: str):
    case_uri_esc = case_uri.replace('"','\\"')
    return f"""
    PREFIX ex: <http://example.org/legal#>
    SELECT ?law ?article WHERE {{
      ?law ex.tieneArticulo ?article .
      ?article ex.aplicaA <{case_uri_esc}> .
    }}
    """
