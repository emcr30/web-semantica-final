# Ontología legal (Perú) — notas

Este archivo complementa `legalontosystem_peru.ttl` y `legal.rdf` del repo.

Explica las clases y propiedades esperadas para el proyecto LegalOntoSystem.

Clases esperadas:
- :Ley
- :Articulo
- :Caso
- :Precedente
- :JurisdiccionTerritorial

Propiedades objetivas:
- :deroga
- :modifica
- :complementa
- :aplicaA (relaciona Ley/Artículo con Caso)
- :tieneArticulo (Ley -> Artículo)
- :tienePrecedente (Caso -> Precedente)
- :jurisdiccion (Ley/Caso -> JurisdiccionTerritorial)

Notas:
- El TTL existente (`legalontosystem_peru.ttl`) se puede ampliar con individuos creados por `backend/rdf_builder.py`.
- Para razonamiento OWL-complete se recomienda usar Pellet (instalable como plugin o vía GraphDB). Para una solución reproducible en Python, incluimos `owlrl` (OWL RL) para razonamiento básico.
