# Integración con GraphDB y Pellet

Este documento explica cómo integrar Localmente la ontología/TTL con GraphDB y usar Pellet para razonamiento OWL-DL.

1) Opciones de instalación
- Descargar GraphDB SE o usar Docker. Versión Community soporta razonamiento básico; para Pellet necesitas GraphDB Enterprise o usar Pellet standalone.
- Docker (ejemplo): visita https://graphdb.ontotext.com/documentation/ to obtener la imagen oficial. La imagen de Ontotext puede requerir licencia para funcionalidades empresariales.

2) Crear un repositorio (Workbench)
- Abrir `http://localhost:7200` (GraphDB Workbench), crear un nuevo repositorio (por ejemplo `legal_repo`), y activar indexes si es necesario.

3) Habilitar Pellet
- Para razonamiento OWL-DL con Pellet en GraphDB, sigue la guía de Ontotext: normalmente se configura en el repositorio settings o se instala como plugin.
- Alternativa libre: ejecutar Pellet standalone y usarla fuera de GraphDB, o usar `owlrl` en Python (incluido en este proyecto) para OWL-RL.

4) Subir datos (ejemplo usando el script incluido)
- Copia `backend/graphdb_config.example.json` a `backend/graphdb_config.json` y ajusta `graphdb_url` y `repository`.
- Ejecutar:
```powershell
.\.venv\Scripts\Activate.ps1
python backend/graphdb_upload.py --config backend/graphdb_config.json --file Ontologia/legal_working.ttl
```
- El script POSTea el TTL a `http://<graphdb>/repositories/<repo>/statements`.

5) Consultas SPARQL desde GraphDB
- Una vez cargada la data, prueba consultas SPARQL desde el Workbench o usando la API REST (`/repositories/<repo>?query=...`).

6) Notas
- Para producción, protege el endpoint y usa autenticación.
- Si necesitas ayuda con la configuración de Docker Compose para GraphDB, puedo añadir un `docker-compose.yml` específico según tu licencia/versión.
