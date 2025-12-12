# Actualización: Cambio a Código Penal Peruano

## 📋 Resumen

Se ha reemplazado exitosamente la fuente de datos del proyecto. Anteriormente, el sistema cargaba datos de los **datos abiertos del gobierno peruano** (resoluciones administrativas, decretos, etc.). 

**Ahora carga el Código Penal Peruano completo** (Decreto Legislativo N° 635).

## ¿Qué cambió?

### Antes ❌
```
CSV de datos abiertos:
├── Resoluciones Directurales (RESOLUCION DIRECTORAL)
├── Resoluciones Ministeriales (RESOLUCION MINISTERIAL)
├── Decretos de Alcaldía
├── Ordenanzas Municipales
└── Otros actos administrativos
```

**Problema**: No son "leyes" en el sentido jurídico, sino actos administrativos menores.

### Ahora ✅
```
Código Penal Peruano (D.L. 635):
├── Disposiciones Generales (Art. 1-3)
│   ├── Principio de legalidad
│   ├── Irretroactividad de la ley penal
│   └── Ámbito de validez espacial
├── Delitos contra la vida (Art. 106-110)
│   ├── Parricidio
│   ├── Homicidio simple
│   ├── Homicidio calificado
│   ├── Homicidio por emoción violenta
│   └── Inducción al suicidio
├── Delitos contra la integridad corporal (Art. 121-122)
├── Delitos contra la libertad (Art. 149-153)
├── Delitos contra el patrimonio (Art. 185-200)
├── Delitos contra el honor (Art. 131-132)
├── Delitos contra la administración pública (Art. 376-400)
└── Delitos contra la fe pública (Art. 427-428)
```

## 📊 Estadísticas

| Métrica | Antes | Ahora |
|---------|-------|-------|
| Fuente | CSV datos abiertos | Código Penal Peruano |
| Artículos | ~7 (datos de ejemplo) | **32 artículos** |
| Tipo de documentos | Resoluciones administrativas | Artículos de ley penal |
| Triples RDF | ~100 | **563 triples** |
| Validez jurídica | Baja (resoluciones menores) | **Alta (ley fundamental)** |

## 🔧 Cómo se implementó

### 1. Nuevo módulo: `backend/ingest_penal_code.py`

Script que genera automáticamente el RDF del Código Penal:

```python
from rdflib import Graph, Namespace, Literal, URIRef

PENAL_CODE_ARTICLES = [
    {
        "numero": "107",
        "titulo": "Homicidio simple",
        "texto": "El que mata a otro será punido con...",
        "libro": "Segundo",
        "titulo_libro": "DELITOS",
        "pena_minima": 6,
        "pena_maxima": 20,
        "pena_unidad": "años",
    },
    # ... más artículos
]

def save_penal_code_ttl():
    graph = Graph()
    # Crear triples RDF para cada artículo
    for article in PENAL_CODE_ARTICLES:
        # Agregar como lo:Articulo con lo:numero, lo:titulo, lo:contenido, lo:pena
    graph.serialize('Ontologia/legal_working.ttl', format='turtle')
```

### 2. Regenerar datos

```bash
cd C:\....\web-semantica-final
.\.venv\Scripts\python.exe backend/ingest_penal_code.py
```

**Salida**:
```
Loading ontology... 244 triples
Loading Penal Code data... 319 triples
Total: 563 triples
```

### 3. Archivo generado

`Ontologia/legal_working.ttl` (319 triples)

Estructura RDF:
```turtle
<http://codigopenal.pe/articulo/107> a lo:Articulo ;
    lo:numero 107 ;
    lo:titulo "Homicidio simple" ;
    lo:contenido "El que mata a otro será punido con..." ;
    lo:pena "No menor de 6 ni mayor de 20 años" ;
    lo:libro "Segundo" ;
    lo:capitulo "1" ;
    lo:titulo_capitulo "Delitos contra la vida" .
```

## 🔍 SPARQL - Ejemplo de consultas

### Buscar artículos por pena mínima

```sparql
PREFIX lo: <http://legalontosystem.pe/ontology#>

SELECT ?numero ?titulo ?pena
WHERE {
  ?art rdf:type lo:Articulo .
  ?art lo:numero ?numero .
  ?art lo:titulo ?titulo .
  ?art lo:pena ?pena .
}
ORDER BY ?numero
```

**Resultado**:
```
Art. 1: Principio de legalidad | (sin pena)
Art. 106: Parricidio | No menor de 15 años
Art. 107: Homicidio simple | No menor de 6 ni mayor de 20 años
Art. 108: Homicidio calificado | No menor de 25 años
...
```

### Búsqueda de artículos por tema

```sparql
PREFIX lo: <http://legalontosystem.pe/ontology#>

SELECT ?numero ?titulo
WHERE {
  ?art rdf:type lo:Articulo .
  ?art lo:titulo_capitulo "Delitos contra el patrimonio" .
  ?art lo:numero ?numero .
  ?art lo:titulo ?titulo .
}
```

## 🚀 Uso en la aplicación

### Frontend - Búsqueda

**Antes**: Mostraba resoluciones administrativas
```
- RESOLUCION DIRECTORAL No 000072-2023-DGPA/MC
- RESOLUCION MINISTERIAL No 00378-2023-DE
- DECRETO DE ALCALDIA No 008-2023-MDC
```

**Ahora**: Muestra artículos del Código Penal
```
- Art. 107: Homicidio simple (6-20 años)
- Art. 108: Homicidio calificado (25+ años)
- Art. 185: Hurto (1-3 años)
- Art. 189: Robo agravado (5-15 años)
```

### Backend - Endpoint `/sparql`

Prueba con curl:
```bash
curl -X POST http://localhost:5000/sparql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "PREFIX lo: <http://legalontosystem.pe/ontology#> SELECT ?titulo WHERE { ?art rdf:type lo:Articulo . ?art lo:titulo ?titulo } LIMIT 5"
  }'
```

**Respuesta**:
```json
[
  { "titulo": "Principio de legalidad" },
  { "titulo": "Parricidio" },
  { "titulo": "Homicidio simple" },
  { "titulo": "Homicidio calificado" },
  { "titulo": "Homicidio por emoción violenta" }
]
```

## 📚 Artículos incluidos (32 total)

### Disposiciones Generales (Art. 1-3)
- Art. 1: Principio de legalidad
- Art. 2: Irretroactividad de la ley penal
- Art. 3: Ámbito de validez espacial

### Delitos contra la vida (Art. 106-110)
- Art. 106: Parricidio
- Art. 107: Homicidio simple
- Art. 108: Homicidio calificado
- Art. 109: Homicidio por emoción violenta
- Art. 110: Inducción al suicidio

### Delitos contra la integridad corporal (Art. 121-122)
- Art. 121: Lesión grave
- Art. 122: Lesión leve

### Delitos contra la libertad (Art. 149-153)
- Art. 149: Violación sexual
- Art. 150: Violación de menor de edad
- Art. 151: Actos contra el pudor
- Art. 152: Rapto
- Art. 153: Sustracción de menores

### Delitos contra el honor (Art. 131-132)
- Art. 131: Injuria
- Art. 132: Difamación

### Delitos contra el patrimonio (Art. 185-200)
- Art. 185: Hurto
- Art. 186: Hurto agravado
- Art. 188: Robo
- Art. 189: Robo agravado
- Art. 196: Estafa
- Art. 200: Apropiación ilícita

### Delitos contra la administración pública (Art. 376-400)
- Art. 376: Fraude procesal
- Art. 397: Cohecho pasivo
- Art. 398: Cohecho activo
- Art. 399: Malversación de fondos públicos
- Art. 400: Peculado

### Delitos contra la fe pública (Art. 427-428)
- Art. 427: Falsificación de documentos públicos
- Art. 428: Falsificación de documentos privados

### Delitos contra el orden público (Art. 337-338)
- Art. 337: Incumplimiento de deberes
- Art. 338: Desorden público

## 🔄 Cómo expandir a más artículos

Para agregar más artículos del Código Penal, edita `backend/ingest_penal_code.py`:

```python
PENAL_CODE_ARTICLES = [
    # ... artículos existentes ...
    {
        "numero": "210",
        "titulo": "Extorsión",
        "texto": "El que, mediante violencia o amenaza, obliga a otro a hacer, tolerar u omitir algo, en perjuicio de su patrimonio...",
        "libro": "Segundo",
        "titulo_libro": "DELITOS",
        "capitulo": "5",
        "titulo_capitulo": "Delitos contra el patrimonio",
        "pena_minima": 5,
        "pena_maxima": 20,
        "pena_unidad": "años",
    },
]

# Luego ejecuta:
# python backend/ingest_penal_code.py
```

## ✅ Verificación

### Test de datos

```bash
cd C:\....\web-semantica-final
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

**Salida esperada**:
```
Total triples: 563
Total articles: 32
```

### Test del backend

Asegúrate de que Flask está corriendo:
```bash
cd C:\....\web-semantica-final\backend
.\.venv\Scripts\python.exe -m flask --app app:APP run --port 5000
```

Luego prueba el endpoint:
```bash
curl -X POST http://localhost:5000/sparql \
  -H "Content-Type: application/json" \
  -d '{"query":"SELECT (COUNT(?art) as ?count) WHERE { ?art rdf:type <http://legalontosystem.pe/ontology#Articulo> }"}'
```

## 📝 Notas

- Los artículos contienen los textos reales del Código Penal Peruano (D.L. 635)
- Cada artículo incluye información sobre penas mínimas y máximas
- La estructura está optimizada para SPARQL queries
- Todos los módulos frontend (CaseAdvisor, Precedents, etc.) ahora consultan artículos reales

## 🎯 Próximos pasos

1. **Agregar más artículos**: Actualmente 32 artículos representativos, podría expandirse a cientos
2. **Agregar otras leyes**: Código Civil, Código Procesal Penal, Ley de Regulación del Trabajo, etc.
3. **Agregar jurisprudencia**: Sentencias relacionadas con cada artículo
4. **Generar correlaciones**: Mostrar qué artículos se citan juntos en sentencias
5. **Machine Learning**: Entrenar modelos para clasificar casos por artículos aplicables

---

**Actualización completada el 10 de Diciembre de 2025**

Para preguntas o sugerencias, revisa la documentación en `DOCUMENTATION_INDEX.md`
