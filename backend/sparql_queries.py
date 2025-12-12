def search_laws_by_text(q: str):
    # busca etiquetas y textos que contengan q (case-insensitive)
    # Tolerante: acepta recursos tipados como lo:Ley o lo:Articulo
    q_esc = q.replace('"','\\"')
    return f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX lo: <http://legalontosystem.pe/ontology#>
    SELECT ?law ?title WHERE {{
      ?law a ?type .
      FILTER( ?type = lo:Ley || ?type = lo:Articulo )
      OPTIONAL {{ ?law rdfs:label ?label }}
      OPTIONAL {{ ?law lo:titulo ?titulo }}
      OPTIONAL {{ ?law lo:texto ?texto }}
      BIND(COALESCE(?label, ?titulo, "") AS ?title)
      FILTER( regex(str(?title), "{q_esc}", "i") || (bound(?texto) && regex(str(?texto), "{q_esc}", "i")) )
    }} LIMIT 50
    """


def example_precedent_query():
    return """
    PREFIX lo: <http://legalontosystem.pe/ontology#>
    SELECT ?case ?precedent WHERE {
      ?case a lo:Caso ; lo.tienePrecedente ?precedent .
    } LIMIT 100
    """


def find_applicable_laws_query(case_uri: str):
    case_uri_esc = case_uri.replace('"','\\"')
    return f"""
    PREFIX lo: <http://legalontosystem.pe/ontology#>
    SELECT ?law ?article WHERE {{
      ?law lo.tieneArticulo ?article .
      ?article lo.aplicaACaso <{case_uri_esc}> .
    }}
    """
