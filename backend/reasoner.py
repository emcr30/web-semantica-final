from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import Graph


def apply_owlrl(g: Graph):
    """Aplica razonamiento OWL-RL sobre el grafo `g` in-place.
    Para razonadores más completos (Pellet), cargar la ontología en GraphDB y correr Pellet allí.
    """
    DeductiveClosure(OWLRL_Semantics).expand(g)
    return g


def save_inferred(g: Graph, path: str):
    g.serialize(destination=path, format='turtle')
    return path
