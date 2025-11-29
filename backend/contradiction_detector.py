from rdflib import Graph, Namespace

EX = Namespace('http://example.org/legal#')


def find_contradictions(g: Graph):
    """Busca contradicciones simples en el grafo:
    - ciclos de deroga (A deroga B y B deroga A)
    - leyes que se modifican mutuamente
    - artículos con disposiciones opuestas (heurística: propiedad ex.prohibe vs ex.permite)
    Retorna una lista de issues detectadas (strings).
    """
    issues = []
    # ciclo deroga
    for s, p, o in g.triples((None, EX.deroga, None)):
        if (o, EX.deroga, s) in g:
            issues.append(f'Ciclo deroga detectado: {s} <-> {o}')
    # mutual modifica
    for s, p, o in g.triples((None, EX.modifica, None)):
        if (o, EX.modifica, s) in g:
            issues.append(f'Mutua modificación: {s} <-> {o}')
    # opuestos en artículos (prohibe vs permite)
    for art, p, obj in g.triples((None, EX.prohibe, None)):
        if (art, EX.permite, obj) in g:
            issues.append(f'Artículo con acciones contradictorias: {art} prohíbe y permite {obj}')
    return issues
