# Módulos Mejorados del Frontend - LegalOnto v2.0

## Resumen de Cambios

Se han implementado **5 nuevos módulos** especializados en la plataforma LegalOnto para mejorar el análisis jurídico:

### 1. **Grafo de Relaciones Mejorado** (Búsqueda)
- **Descripción**: Visualización interactiva de leyes y sus relaciones
- **Mejoras**:
  - ✅ **Zoom y Pan**: Usa la rueda del ratón para acercar/alejar (scroll)
  - ✅ **Arrastrar**: Arrastra nodos individuales para reorganizar
  - ✅ **Botón Reset**: Vuelve a la vista original con un clic
  - ✅ **Indicador de nivel**: Muestra el nivel de zoom actual (x1.00, x2.50, etc.)

**Cómo usar**:
1. Ve a la pestaña "Búsqueda"
2. Usa el campo de búsqueda o carga todas las leyes
3. Interactúa con el grafo:
   - Rueda del ratón = zoom
   - Arrastra el fondo = pan (movimiento)
   - Haz clic en un nodo = ver detalles
   - Usa "🔍 Reset" para volver al inicio

---

### 2. **Asesor de Casos Jurídicos** (Consulta Inteligente)
- **Descripción**: Analiza casos y recomienda leyes aplicables
- **Tecnología**: spaCy NLP para extracción de entidades

**Características**:
- 📋 Describe un caso en detalle
- 🔍 Extrae automáticamente:
  - Artículos mencionados (Ej: "Artículo 5")
  - Leyes referenciadas (Ej: "Ley N° 27444")
  - Conceptos jurídicos clave
  - Entidades (personas, organizaciones)
- ⚖️ Recomienda leyes aplicables con fundamentación
- 📊 Muestra palabras clave relacionadas

**Cómo usar**:
1. Ve a la pestaña "Asesor de Casos"
2. Describe el caso jurídico en el área de texto
3. Haz clic en "Analizar y Recomendar"
4. El sistema:
   - Extrae entidades automáticamente
   - Busca leyes relacionadas
   - Presenta recomendaciones ordenadas

**Ejemplo de entrada**:
```
Un cliente fue despedido sin causa justificada. 
Trabajaba para empresa XYZ desde 2019. 
Desea saber qué leyes lo protegen y si puede demandar.
```

---

### 3. **Análisis de Precedentes**
- **Descripción**: Encuentra casos relacionados a leyes específicas
- **Ranking**: Calcula relevancia automática

**Características**:
- ⚖️ Selecciona una ley o artículo
- 📑 Busca precedentes relacionados
- 🎯 Ordena por relevancia (score %)
- 📍 Muestra jurisdicción y fecha de casos
- 🔗 Enlaces entre casos y normativa

**Cómo usar**:
1. Ve a la pestaña "Precedentes"
2. Selecciona una ley de la lista desplegable
3. Haz clic en "Buscar Precedentes"
4. Visualiza casos ordenados por relevancia
5. Haz clic en cada caso para más detalles

---

### 4. **Jerarquía de Normas Legales**
- **Descripción**: Visualiza la estructura completa del ordenamiento

**Características**:
- 🌳 Árbol jerárquico de Leyes → Artículos
- 📊 Estadísticas:
  - Total de leyes cargadas
  - Cantidad de artículos
- 🎨 Visualización D3 interactiva
- 💾 Carga automática al acceder

**Cómo usar**:
1. Ve a la pestaña "Jerarquía"
2. Observa la estructura visual de leyes y artículos
3. Lee las estadísticas de la base de conocimiento
4. Interactúa con el árbol (zoom/pan igual que el grafo)

---

### 5. **Detector de Contradicciones Normativas**
- **Descripción**: Identifica conflictos y derogaciones entre normas
- **Análisis**: Automático de todo el sistema

**Características**:
- ⚠️ Detección automática de:
  - Leyes derogadas
  - Modificaciones
  - Reglamentaciones
  - Incompatibilidades
- 🎯 Análisis por ley específica
- 📊 Grado de severidad (Alto/Medio/Bajo)
- 💡 Impacto legal explicado

**Cómo usar**:
1. Ve a la pestaña "Contradicciones"
2. **Opción A - Análisis general**:
   - Haz clic en "Cargar Todas las Contradicciones"
   - Visualiza conflictos del sistema completo
3. **Opción B - Análisis específico**:
   - Selecciona una ley
   - Haz clic en "Analizar"
   - Ve conflictos de esa ley

**Interpretación de resultados**:
- 🔴 **Alto**: Potencial conflicto grave (derogación)
- 🟡 **Medio**: Incompatibilidad parcial (modificación)
- 🟢 **Bajo**: Diferencias menores

---

## Integración Backend

### Nuevo Endpoint: `/nlp_extract`
```bash
POST /nlp_extract
Content-Type: application/json

{
  "text": "Descripción del caso aquí..."
}

Response:
{
  "articles": ["5", "10"],
  "laws": ["27444"],
  "entities": [
    {"text": "Juan Pérez", "label": "PERSON"},
    {"text": "MinTrabajo", "label": "ORG"}
  ],
  "keywords": ["despido", "contrato", "derechos"]
}
```

### Módulos Backend Existentes (Mejorados)
- `/sparql` - Consultas SPARQL (mejorado con manejo de errores)
- `/precedents_for_article` - Busca precedentes
- `/detect_contradictions` - Detecta conflictos

---

## Configuración de Dependencias

### Frontend (ya incluidas en package.json)
```json
{
  "d3": "^7.x",
  "axios": "^latest",
  "react": "^18.x"
}
```

### Backend (instalar si no existe)
```bash
pip install spacy
python -m spacy download es_core_news_sm
```

Si `es_core_news_sm` no está disponible, el sistema fallback a un modelo en blanco.

---

## Mejoras de UX

### Navegación
- Sidebar con 7 opciones principales
- Títulos dinámicos que cambian por pestaña
- Indicador visual de pestaña activa

### Estilos
- Paleta de colores consistente
- Cards con sombras y transiciones
- Responsive design (mobile-friendly)
- Iconos unicode para claridad

### Feedback
- Loading states en botones
- Mensajes de error informativos
- Confirmaciones de acciones

---

## Roadmap Futuro

- [ ] Integración con GraphDB para razonamiento OWL-DL
- [ ] Análisis de similitud entre casos (cosine similarity)
- [ ] Exportar reportes en PDF
- [ ] Sincronización en tiempo real (WebSockets)
- [ ] Dashboard de métricas legales

---

## Arquitectura

```
frontend/src/
├── App.jsx                 # Componente principal (actualizado)
├── D3Graph.jsx             # Grafo mejorado con zoom/pan
├── styles.css              # Estilos ampliados
└── modules/
    ├── CaseAdvisor.jsx     # Asesor de casos
    ├── PrecedentAnalyzer.jsx  # Análisis de precedentes
    ├── HierarchyViewer.jsx    # Visualización jerárquica
    └── ContradictionDetector.jsx  # Detector de conflictos

backend/
├── app.py                  # API Flask (mejorada)
├── nlp_extractor.py        # Nuevo módulo NLP
└── ... (otros módulos existentes)
```

---

## Notas Técnicas

1. **D3Graph con Zoom**: Implementado con `d3.zoom()` y `zoomIdentity`
2. **spaCy NLP**: Extrae entidades y patrones regex para artículos/leyes
3. **Componentes React**: Hooks (`useState`, `useEffect`) para estado local
4. **API REST**: Todos los módulos usan axios para llamadas HTTP
5. **SPARQL**: Consultas dinámicas para buscar leyes y precedentes

---

## Soporte

Para reportar problemas o sugerencias, por favor abre un issue en el repositorio.
