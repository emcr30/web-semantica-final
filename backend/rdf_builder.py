from rdflib import Graph, Namespace, Literal, RDF, RDFS, URIRef
from rdflib.namespace import FOAF, XSD
import os

# Use the project's ontology namespace for consistency with Ontologia/legalontosystem_peru.ttl
ONT = Namespace('http://legalontosystem.pe/ontology#')
RESOURCE_BASE = 'http://legalontosystem.pe/resource/'


def ensure_namespaces(g: Graph):
    g.bind('', ONT)
    g.bind('lo', ONT)
    g.bind('foaf', FOAF)
    g.bind('rdfs', RDFS)


def create_law(g: Graph, law_id: str, title: str, text: str, jurisdiction: str = 'Peru', numero: str = None):
    """Crea un individuo Ley y sus artículos básicos a partir de texto.
    - law_id: identificador corto (sin espacios)
    - title: título de la ley
    - text: cuerpo de la ley
    """
    ensure_namespaces(g)
    law_uri = URIRef(RESOURCE_BASE + law_id)
    g.add((law_uri, RDF.type, ONT.Ley))
    # store both rdfs:label and ontology's :titulo for compatibility
    g.add((law_uri, RDFS.label, Literal(title, datatype=XSD.string)))
    g.add((law_uri, ONT.titulo, Literal(title, datatype=XSD.string)))
    g.add((law_uri, ONT.texto, Literal(text, datatype=XSD.string)))
    # use ontology property :aplicaEn to indicate jurisdiction/applicability
    g.add((law_uri, ONT.aplicaEn, Literal(jurisdiction)))
    if numero:
        g.add((law_uri, ONT.numeroNorma, Literal(numero)))
    # heurística simple: dividir por 'Artículo' para crear artículos
    sections = text.split('\n')
    # create a simple Article if 'Artículo' found
    from backend.nlp_processor import ARTICLE_RE
    import re
    article_matches = list(ARTICLE_RE.finditer(text))
    for i, m in enumerate(article_matches):
        num = m.group(1)
        start = m.end()
        end = article_matches[i+1].start() if i+1 < len(article_matches) else len(text)
        art_text = text[start:end].strip()
        art_uri = URIRef(f"{RESOURCE_BASE}{law_id}_art_{num}")
        g.add((art_uri, RDF.type, ONT.Articulo))
        g.add((art_uri, RDFS.label, Literal(f"Artículo {num}")))
        g.add((art_uri, ONT.titulo, Literal(f"Artículo {num}")))
        g.add((art_uri, ONT.texto, Literal(art_text)))
        # link article -> law using esParteDe (ontology defines esParteDe as inverseOf tieneArticulo)
        g.add((art_uri, ONT.esParteDe, law_uri))
        # also add inverse relation for compatibility
        g.add((law_uri, ONT.tieneArticulo, art_uri))
    return law_uri


def save_graph(g: Graph, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    g.serialize(destination=path, format='turtle')
