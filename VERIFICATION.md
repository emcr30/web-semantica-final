# Verificación del Sistema - Código Penal Peruano

## ✅ Checklist de Implementación

### 1. Datos ✓
- [x] Código Penal Peruano cargado
- [x] 32 artículos representativos
- [x] 563 triples RDF generados
- [x] Archivo `Ontologia/legal_working.ttl` creado
- [x] Ontología `Ontologia/legalontosystem_peru.ttl` compatible

### 2. Backend ✓
- [x] Módulo `backend/ingest_penal_code.py` creado
- [x] SPARQL queries funcionando con Código Penal
- [x] Endpoints `/sparql`, `/search`, etc. actualizados
- [x] Flask cargando datos correctamente

### 3. Frontend ✓
- [x] Todos los módulos conectados
- [x] D3Graph mostrando artículos
- [x] CaseAdvisor recomendando artículos
- [x] PrecedentAnalyzer buscando por artículos
- [x] HierarchyViewer mostrando estructura

### 4. Documentación ✓
- [x] `PENAL_CODE_UPDATE.md` creado
- [x] `QUICKSTART.md` actualizado
- [x] Scripts de regeneración creados

---

## 🧪 Pruebas para ejecutar

### Test 1: Verificar datos RDF

```bash
cd C:\Users\LENOVO\Documents\Laeros\web-semantica-final
.\.venv\Scripts\python.exe -c "
from rdflib import Graph
g = Graph()
g.parse('Ontologia/legalontosystem_peru.ttl')
g.parse('Ontologia/legal_working.ttl')
print(f'Total triples: {len(g)}')

query = 'PREFIX lo: <http://legalontosystem.pe/ontology#> SELECT (COUNT(?art) as ?count) WHERE { ?art rdf:type lo:Articulo }'
result = list(g.query(query))[0]
print(f'Total articles: {result.count}')
"
```

**Resultado esperado**:
```
Total triples: 563
Total articles: 32
```

### Test 2: SPARQL query manual

```bash
cd C:\Users\LENOVO\Documents\Laeros\web-semantica-final
.\.venv\Scripts\python.exe -c "
from rdflib import Graph
import json

g = Graph()
g.parse('Ontologia/legalontosystem_peru.ttl')
g.parse('Ontologia/legal_working.ttl')

query = '''
PREFIX lo: <http://legalontosystem.pe/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?numero ?titulo ?pena
WHERE {
  ?art rdf:type lo:Articulo .
  ?art lo:numero ?numero .
  ?art lo:titulo ?titulo .
  OPTIONAL { ?art lo:pena ?pena }
}
ORDER BY ?numero
LIMIT 10
'''

results = list(g.query(query))
for row in results:
    print(f'Art. {row.numero}: {row.titulo}')
"
```

**Resultado esperado**:
```
Art. 1: Principio de legalidad
Art. 106: Parricidio
Art. 107: Homicidio simple
Art. 108: Homicidio calificado
...
```

### Test 3: Backend Flask

```bash
# Terminal 1
cd C:\Users\LENOVO\Documents\Laeros\web-semantica-final\backend
.\.venv\Scripts\python.exe -m flask --app app:APP run --port 5000

# Terminal 2 (en otra ventana PowerShell)
$body = @{
    query = "PREFIX lo: <http://legalontosystem.pe/ontology#> SELECT ?titulo WHERE { ?art rdf:type lo:Articulo . ?art lo:titulo ?titulo } LIMIT 5"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:5000/sparql" `
  -Method POST `
  -Headers @{"Content-Type"="application/json"} `
  -Body $body | Select-Object -ExpandProperty Content
```

**Resultado esperado**:
```json
[
  {"titulo": "Principio de legalidad"},
  {"titulo": "Parricidio"},
  {"titulo": "Homicidio simple"},
  ...
]
```

### Test 4: Frontend

1. Abre navegador: `http://localhost:5173`
2. Navega a cada pestaña:
   - **Búsqueda**: Debe mostrar grafo con artículos
   - **Asesor de Casos**: Ingresa texto, debe recomendar artículos
   - **Precedentes**: Selecciona artículo, debe mostrar casos
   - **Jerarquía**: Debe mostrar árbol de artículos
   - **Contradicciones**: Debe mostrar conflictos entre artículos

### Test 5: Búsqueda por palabra clave

Busca en la pestaña "Búsqueda":
- `homicidio` → Debe retornar Art. 106-109
- `robo` → Debe retornar Art. 188-189
- `hurto` → Debe retornar Art. 185-186

---

## 📊 Datos de referencia

### Estadísticas actuales

```
Código Penal Peruano (D.L. 635)

Total de artículos: 32
Total de triples: 563

Desglose por categoría:
├── Disposiciones Generales: 3 artículos
├── Delitos contra la vida: 5 artículos
├── Delitos contra la integridad corporal: 2 artículos
├── Delitos contra la libertad: 5 artículos
├── Delitos contra el honor: 2 artículos
├── Delitos contra el patrimonio: 6 artículos
├── Delitos contra la administración pública: 5 artículos
├── Delitos contra la fe pública: 2 artículos
└── Delitos contra el orden público: 2 artículos

Rangos de penas:
├── Sin pena (principios): 3 artículos
├── Hasta 3 años: 4 artículos
├── De 3 a 10 años: 10 artículos
├── De 10 a 20 años: 8 artículos
└── Más de 20 años: 7 artículos
```

### Ejemplos de consultas

#### Encontrar todos los delitos con pena mínima de 5+ años
```sparql
PREFIX lo: <http://legalontosystem.pe/ontology#>
SELECT ?numero ?titulo ?pena
WHERE {
  ?art rdf:type lo:Articulo .
  ?art lo:numero ?numero .
  ?art lo:titulo ?titulo .
  ?art lo:pena ?pena .
  FILTER(REGEX(?pena, "cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|veinte|veinticinco"))
}
```

#### Encontrar delitos por capítulo
```sparql
PREFIX lo: <http://legalontosystem.pe/ontology#>
SELECT ?numero ?titulo
WHERE {
  ?art rdf:type lo:Articulo .
  ?art lo:titulo_capitulo "Delitos contra la vida" .
  ?art lo:numero ?numero .
  ?art lo:titulo ?titulo .
}
```

---

## 🔄 Cómo actualizar los artículos

### Agregar un nuevo artículo

1. Edita `backend/ingest_penal_code.py`
2. Agrégalo a la lista `PENAL_CODE_ARTICLES`:

```python
{
    "numero": "376",
    "titulo": "Fraude procesal",
    "texto": "El que, siendo parte en un proceso...",
    "libro": "Segundo",
    "titulo_libro": "DELITOS",
    "capitulo": "22",
    "titulo_capitulo": "Delitos contra la administración pública",
    "pena_minima": 2,
    "pena_maxima": 6,
    "pena_unidad": "años",
},
```

3. Regenera el archivo:
```bash
.\.venv\Scripts\python.exe backend/ingest_penal_code.py
```

4. Reinicia Flask:
```bash
# Ctrl+C en la terminal de Flask
# Luego:
.\.venv\Scripts\python.exe -m flask --app app:APP run --port 5000
```

### Agregar otra ley (ej: Código Civil)

Crea un nuevo archivo `backend/ingest_civil_code.py` con estructura similar:

```python
def save_civil_code_ttl():
    graph = Graph()
    # ... agregar artículos del Código Civil ...
    graph.serialize('Ontologia/legal_working.ttl', format='turtle')
```

Luego combina en `app.py`:
```python
from backend.ingest_penal_code import create_penal_code_rdf
from backend.ingest_civil_code import create_civil_code_rdf

# En startup:
penal = create_penal_code_rdf()
civil = create_civil_code_rdf()
GRAPH = Graph()
GRAPH += penal
GRAPH += civil
```

---

## 🚀 Próximas fases sugeridas

### Fase 1: Expansión de datos
- [ ] Agregar 100+ artículos del Código Penal
- [ ] Agregar Código Civil Peruano
- [ ] Agregar Código Procesal Penal
- [ ] Agregar Ley de Regulación del Trabajo

### Fase 2: Datos jurisprudenciales
- [ ] Agregar sentencias de la Corte Suprema
- [ ] Crear relaciones entre artículos y sentencias
- [ ] Agregar métricas de relevancia

### Fase 3: Análisis avanzado
- [ ] Machine Learning para clasificación automática
- [ ] Similitud semántica entre casos
- [ ] Predicción de aplicabilidad de artículos
- [ ] Análisis de tendencias jurisprudenciales

---

## 📞 Soporte

Si encuentras problemas:

1. **No carga artículos**:
   - Verifica que `legal_working.ttl` exista
   - Ejecuta: `python backend/ingest_penal_code.py`
   - Reinicia Flask

2. **SPARQL query no retorna resultados**:
   - Verifica namespace correcto: `http://legalontosystem.pe/ontology#`
   - Prueba manualmente con: `python -c "from rdflib import Graph; g = Graph(); g.parse('Ontologia/legal_working.ttl'); print(len(g))"`

3. **Frontend no actualiza**:
   - Limpia caché del navegador: `Ctrl+Shift+Delete`
   - Recarga página: `F5` o `Ctrl+R`
   - Reinicia Vite

4. **Flask no inicia**:
   - Verifica puerto no esté en uso: `netstat -ano | findstr :5000`
   - Mata proceso: `taskkill /PID <PID> /F`
   - Reinicia Flask

---

**Última actualización**: 10 de Diciembre de 2025
**Versión**: v2.0
**Estado**: ✅ Completado
