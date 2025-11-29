Frontend — guía rápida

El frontend recomendado es un app React que consuma la API Flask en `backend/app.py`.

Sugerencias de implementación:
- Crear proyecto con `npx create-react-app frontend`.
- Endpoints a usar:
  - `POST /ingest` para cargar leyes (útil para admin/import)
  - `GET /search?q=...` para búsqueda rápida
  - `POST /sparql` para consultas avanzadas
  - `GET /detect_contradictions` para mostrar conflictos
  - `POST /reason` para disparar razonamiento y actualizar visualizaciones

Visualización:
- Usar D3.js para grafo (jerarquía y relaciones). Representar nodos Ley/Articulo/Caso.
- Añadir panel lateral con resultados SPARQL y detalle de individuos.

Autenticación y despliegue:
- Añadir CORS y autenticación (JWT) si expone datos sensibles.
- Para producción, desplegar backend con Gunicorn/uWSGI y servir frontend separado.
