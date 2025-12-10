# LegalOntoSystem — Proyecto 10

Objetivo: Crear una ontología y sistema de consulta jurídica para modelar leyes, artículos, casos, precedentes y jurisdicciones, con búsqueda semántica y razonamiento.

Estructura propuesta:

- `Ontologia/` — ontologías TTL/OWL (ya contiene `legalontosystem_peru.ttl` y `legal.rdf`).
- `backend/` — API en Python (Flask), scripts de ingestión, procesamiento NLP, construcción RDF y razonamiento.
- `frontend/` — esqueleto para un cliente React que consuma la API y muestre búsquedas y visualizaciones.

Requisitos (resumen rápido):
- Python 3.10+
- spaCy (modelo español `es_core_news_sm` recomendado)
- rdflib, owlrl (para razonamiento OWL-RL en Python)
- GraphDB (opcional, para triple store + Pellet)

Pasos rápidos de instalación (backend):

1. Crear y activar un entorno virtual (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r backend/requirements.txt
python -m spacy download es_core_news_sm
```

3. Ejecutar la API (desarrollo):

```powershell
$env:FLASK_APP = 'backend.app'
$env:FLASK_ENV = 'development'
flask run
```

Para producción o integración con GraphDB/ Pellet, ver las instrucciones en `backend/`.

**LegalOntoSystem — Proyecto 10**

**Descripción:** Proyecto para modelar y consultar normativa legal (Leyes, Artículos, Casos, Precedentes y Jurisdicciones) mediante una ontología OWL, ingestión automática, análisis NLP y razonamiento. Incluye un backend en Python (Flask + rdflib/owlrl) y un frontend en React (Vite + D3) para búsqueda semántica y visualización.

**Estructura principal del repositorio**
- `Ontologia/`: archivos TTL/OWL (ej.: `legalontosystem_peru.ttl`, `legal.rdf`).
- `backend/`: API Flask, ingestores, constructor RDF, razonador, utilidades de upload a GraphDB.
- `frontend/`: Cliente React (Vite) con visualización D3 y formularios de ingestión.

**Requisitos**
- **Python** 3.10+ (recomendado 3.10–3.11)
- **Node.js** 16+ y `npm` para el frontend
- **GraphDB** (opcional) para triple-store y razonador Pellet si desea OWL-DL
- **spaCy** + modelo `es_core_news_sm` (NLP en español)
- Opcional para OCR: **Tesseract** y **poppler** (solo si necesita extraer texto de PDFs escaneados)

**Guía rápida — Clonar y ejecutar (Windows / macOS / Linux)**

Pasos comunes a ambos sistemas:

1) Clonar el repositorio:

```bash
git clone https://github.com/emcr30/web-semantica-final.git
cd web-semantica-final
```

2) Repositorio: estructura esperada (desde la raíz del repo):

- `Ontologia/`
- `backend/` — contiene `app.py`, `dataset_ingest.py`, `graphdb_upload.py`, etc.
- `frontend/` — cliente React (Vite)

---

**A. Backend (Python) — Windows (PowerShell)**

```powershell
# crear entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# instalar dependencias
pip install --upgrade pip
pip install -r backend/requirements.txt

# instalar modelo spaCy (si falla, ver nota alternativa abajo)
python -m spacy download es_core_news_sm

# ejecutar servidor Flask (desarrollo)
$env:FLASK_APP='backend.app'
$env:FLASK_ENV='development'
flask run --host=127.0.0.1 --port=5000
```

**A. Backend (macOS / Linux — bash/zsh)**

```bash
# crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# instalar dependencias
pip install --upgrade pip
pip install -r backend/requirements.txt

# instalar modelo spaCy
python -m spacy download es_core_news_sm

# ejecutar servidor Flask
export FLASK_APP=backend.app
export FLASK_ENV=development
flask run --host=127.0.0.1 --port=5000
```

Nota: si la descarga del modelo spaCy falla (problemas de red o versión), puede instalar el wheel manualmente o usar `python -m spacy download es_core_news_sm --direct` y luego `pip install` del paquete wheel local.

---

**B. Frontend (React / Vite) — Windows y macOS (bash/PowerShell)**

Requisitos: Node.js (16+). Desde la raíz del repo:

```bash
cd frontend
npm install
npm run dev
# abre http://localhost:5173 en tu navegador
```

El `vite.config.js` incluye un proxy para las llamadas al backend (por defecto `http://127.0.0.1:5000`) así que las rutas como `/sparql`, `/ingest_csv`, `/entity` funcionan sin CORS adicional cuando desarrollas con Vite.

---

**C. Configurar GraphDB (opcional)**

Si dispones de una instancia GraphDB (con o sin Pellet), crea un archivo de configuración para que el backend pueda subir TTL automáticamente:

1. Copia el ejemplo en `backend/graphdb_config.example.json` y crea `backend/graphdb_config.json` con tus valores:

```json
{
	"url": "http://localhost:7200",
	"repository": "mi_repositorio",
	"username": "", 
	"password": ""
}
```

2. Reinicia el backend Flask y luego, al usar el endpoint de ingestión (`/ingest` o `/ingest_csv`), el backend intentará subir `Ontologia/legal_working.ttl` al repo configurado.

Verificación: abre la Workbench de GraphDB y revisa las triples en el repositorio indicado.

Nota sobre razonamiento: para activar razonamiento más potente (OWL2-RL, OWL-Horst) o usar Pellet (OWL-DL) consulta `docs/graphdb_reasoning.md`.

---

**D. Endpoints importantes (desarrollo)**

-- `POST /sparql` — ejecutar consulta SPARQL en el grafo cargado (JSON body: `{ "query": "..." }`).
-- `POST /ingest` — ingestión manual de texto: `{ "text": "...", "title": "...", "id": "..." }`.
-- `POST /ingest_csv` — ingestión desde CSV. Ahora soporta **subida de archivo (multipart/form-data, campo `file`)** o JSON `{ "url": "..." }` para compatibilidad. Cuando se sube un archivo, el backend lo guarda en `Datos/` con un sufijo de timestamp para evitar sobrescrituras y responde con `saved_as` y `result`.
		 - Ejemplo (curl):
			 ```bash
			 curl -v -F "file=@/ruta/a/DatosAbiertos_Periodo_20230401_20230430.CSV" http://127.0.0.1:5000/ingest_csv
			 ```
		 - Ejemplo (desde frontend): use la pestaña "Ingestión" → "Ingestar desde CSV" y seleccione el archivo.
-- `GET /entity?uri=<URI>` — devuelve propiedades del sujeto solicitado.
-- `POST /fetch_url_debug` — debug fetch para diagnosticar 404/403 desde el backend: `{ "url": "..." }`.

Ejemplos usando PowerShell (desde la raíz del repo):

```powershell
# probar entity
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:5000/entity?uri=http://example.org/legal/2173422-1"

# ejecutar SPARQL vía proxy (frontend dev)
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5173/sparql -Body (@{query="SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }"} | ConvertTo-Json) -ContentType "application/json"
```

---

**E. Extra: OCR para PDFs escaneados (opcional)**

Si deseas extraer texto de PDFs escaneados agrega OCR:

- Windows: instala `poppler` (binarios) y `Tesseract OCR` (instalador), luego en Python instala `pytesseract` y `pdf2image`.
- macOS: `brew install poppler tesseract` y luego `pip install pytesseract pdf2image`.

El código del ingestador puede ampliarse para convertir páginas a imágenes y aplicar OCR cuando `pdfminer.six` no extraiga texto legible.

---

**F. Problemas comunes y soluciones**
- Si el frontend muestra errores de CORS: asegúrate de ejecutar Vite (`npm run dev`) y el backend en `127.0.0.1:5000` para que el proxy funcione.
- Si `pip install -r backend/requirements.txt` falla por versión de `rdflib`, usa la versión que figura en el `requirements.txt` del repo.
- Si el fetch a URLs gubernamentales devuelve 403/404: prueba el endpoint `POST /fetch_url_debug` (desde el backend) para inspeccionar headers y contenido preview.

- Nota sobre Vite/IPv6: en algunos entornos Vite puede enlazar en IPv6 (`[::1]:5173`). Si `http://127.0.0.1:5173` falla, usa `http://localhost:5173` o `http://[::1]:5173` (o fuerza IPv6 con `curl -6`).

---

**H. Git / .gitignore y limpieza de archivos trackeados**
Se añadió un `.gitignore` en la raíz para evitar subir entornos virtuales, `node_modules`, archivos `Datos/`, `Ontologia/legal_working.ttl` y `backend/graphdb_config.json` (config sensible). Si ya tienes estos archivos versionados, quítalos del índice de Git sin borrarlos localmente:

PowerShell:
```powershell
git rm --cached Ontologia/legal_working.ttl
git rm --cached backend/graphdb_config.json
git rm --cached -r Datos
git commit -m "Stop tracking generated files and sensitive configs; add .gitignore"
```

Bash:
```bash
git rm --cached Ontologia/legal_working.ttl
git rm --cached backend/graphdb_config.json
git rm --cached -r Datos
git commit -m "Stop tracking generated files and sensitive configs; add .gitignore"
```

Si quieres, puedo crear scripts `scripts/cleanup_gitignored.ps1` y `scripts/cleanup_gitignored.sh` que ejecuten estos comandos de forma segura.

---

**G. Desarrollo y siguientes pasos recomendados**
- Crear/editar la ontología en `Ontologia/legalontosystem_peru.ttl` usando Protégé para mantener consistencia OWL2.
- Añadir tests automatizados para ingestion y SPARQL (pytest).
- Integrar GraphDB + Pellet para razonamiento OWL-DL si necesitas inferencias más potentes.

---

Si necesitas que automatice la creación de `backend/graphdb_config.json`, añadir el flujo CKAN para resolver resource IDs en `datosabiertos.gob.pe` o incluir OCR automático, dime cuál y lo implemento.

Licencia: este repositorio es un proyecto de investigación; añade licencia si corresponde.
