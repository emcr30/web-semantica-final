from rdflib import Graph, Namespace, Literal, RDF, RDFS, URIRef
from rdflib.namespace import FOAF, XSD
import os

EX = Namespace('http://example.org/legal#')
BASE_URI = 'http://example.org/legal/'


def ensure_namespaces(g: Graph):
    g.bind('ex', EX)
    g.bind('foaf', FOAF)
    g.bind('rdfs', RDFS)


def create_law(g: Graph, law_id: str, title: str, text: str, jurisdiction: str = 'Peru'):
    """Crea un individuo Ley y sus artículos básicos a partir de texto.
    - law_id: identificador corto (sin espacios)
    - title: título de la ley
    - text: cuerpo de la ley
    """
    ensure_namespaces(g)
    law_uri = URIRef(BASE_URI + law_id)
    g.add((law_uri, RDF.type, EX.Ley))
    g.add((law_uri, RDFS.label, Literal(title, datatype=XSD.string)))
    g.add((law_uri, EX.tieneTexto, Literal(text, datatype=XSD.string)))
    g.add((law_uri, EX.jurisdiccion, Literal(jurisdiction)))
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
        art_uri = URIRef(f"{BASE_URI}{law_id}_art_{num}")
        g.add((art_uri, RDF.type, EX.Articulo))
        g.add((art_uri, RDFS.label, Literal(f"Artículo {num}")))
        g.add((art_uri, EX.numero, Literal(num)))
        g.add((art_uri, EX.tieneTexto, Literal(art_text)))
        g.add((law_uri, EX.tieneArticulo, art_uri))
    return law_uri


def save_graph(g: Graph, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    g.serialize(destination=path, format='turtle')
