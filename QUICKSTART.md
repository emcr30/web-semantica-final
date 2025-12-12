# Guía de Ejecución - LegalOnto v2.0 

## Sistema de Base de Datos Legal

**Base de datos**: Código Penal Peruano (Decreto Legislativo N° 635)
- 32 artículos representativos
- 563 triples RDF (ontología + datos)
- Cobertura: Delitos contra vida, patrimonio, libertad, honor, administración pública

**Ver**: `PENAL_CODE_UPDATE.md` para detalles de la migración

---

## 🚀 Inicio Rápido

### 1. Terminal 1 - Backend (Flask API)
```powershell
cd 'web-semantica-final\backend'
# Asegúrate de tener activado el venv
.\.venv\Scripts\Activate.ps1
# Inicia Flask
python -m flask --app app:APP run --host=127.0.0.1 --port=5000 --reload
```

**Esperado**:
```
 * Running on http://127.0.0.1:5000
```

### 2. Terminal 2 - Frontend (Vite Dev Server)
```powershell
cd 'web-semantica-final\frontend'
npm run dev
```

**Esperado**:
```
VITE v5.x.x  ready in xxx ms

➜ Local:   http://localhost:5173
➜ press h + enter to show help
```

Si puerto 5173 está ocupado, Vite intentará 5174, 5175, etc.

### 3. Abre el navegador
```
http://localhost:5173  (o el puerto que indique Vite)
```

---

## 📦 Estructura de Módulos Implementados

### ✅ Módulos Completados

1. **Grafo de Relaciones Mejorado**
   - Archivo: `frontend/src/D3Graph.jsx`
   - Características: Zoom (scroll), Pan (arrastrar), Reset
   - Estado: Integrado en la pestaña "Búsqueda"

2. **Asesor de Casos Jurídicos**
   - Archivo: `frontend/src/modules/CaseAdvisor.jsx`
   - Backend: `/nlp_extract` (spaCy)
   - Características: Análisis NLP, recomendación de leyes
   - Estado: Pestaña "Asesor de Casos"

3. **Análisis de Precedentes**
   - Archivo: `frontend/src/modules/PrecedentAnalyzer.jsx`
   - Backend: `/precedents_for_article`
   - Características: Búsqueda de casos, ranking por relevancia
   - Estado: Pestaña "Precedentes"

4. **Visualización de Jerarquía**
   - Archivo: `frontend/src/modules/HierarchyViewer.jsx`
   - Backend: SPARQL query personalizada
   - Características: Árbol jerárquico, estadísticas
   - Estado: Pestaña "Jerarquía"

5. **Detector de Contradicciones**
   - Archivo: `frontend/src/modules/ContradictionDetector.jsx`
   - Backend: `/detect_contradictions`
   - Características: Detección de conflictos, severidad
   - Estado: Pestaña "Contradicciones"

---

## 🔧 Configuración de Dependencias

### Backend - Dependencias Necesarias
```bash
cd backend
pip install spacy
python -m spacy download es_core_news_sm
```

Si `es_core_news_sm` falla, el sistema usa un modelo blank automáticamente.

### Frontend - Ya Incluidas
- React 18+
- Axios
- D3 v7+
- Vite

---

## 📋 Navegación del Sistema

### Barra Lateral (Sidebar)
```
LegalOnto v1.0
├── 🏠 Búsqueda          → Búsqueda y grafo mejorado
├── 📋 Asesor de Casos   → Análisis jurídico inteligente
├── ⚖️ Precedentes        → Busca casos relacionados
├── 🌳 Jerarquía         → Estructura de normas
├── ⚠️ Contradicciones    → Detecta conflictos
├── 📥 Datos             → Ingesta de CSV/texto
└── ⚡ SPARQL            → Editor de consultas
```

---

## 🎯 Casos de Uso

### Caso 1: Buscar una Ley y Ver Sus Relaciones
1. Pestaña "Búsqueda"
2. Escribe término (ej: "trabajo")
3. Haz clic en "Buscar"
4. Zoom con rueda del ratón
5. Arrastra para ver mejor
6. Haz clic en un nodo para detalles

### Caso 2: Analizar un Caso Jurídico
1. Pestaña "Asesor de Casos"
2. Describe el caso (incluye hechos, artículos si sabes)
3. Haz clic en "Analizar y Recomendar"
4. Ve entidades extraídas y leyes aplicables

### Caso 3: Encontrar Precedentes
1. Pestaña "Precedentes"
2. Selecciona ley/artículo de dropdown
3. Haz clic en "Buscar Precedentes"
4. Ve casos ordenados por relevancia

### Caso 4: Ver Estructura Completa
1. Pestaña "Jerarquía"
2. Observa árbol de leyes → artículos
3. Lee estadísticas (leyes cargadas, artículos totales)

### Caso 5: Detectar Conflictos
1. Pestaña "Contradicciones"
2. Opción A: "Cargar Todas las Contradicciones"
3. Opción B: Selecciona ley + "Analizar"
4. Lee conflictos detectados

---

## 🐛 Troubleshooting

### Error: "Request failed with status code 500"
**Causa**: Backend no cargó las leyes de `legal_working.ttl`
**Solución**:
1. Verifica que `Ontologia/legal_working.ttl` existe
2. Reinicia Flask con `--reload`
3. Verifica logs en terminal de Flask

### Error: "es_core_news_sm not found"
**Causa**: Modelo spaCy no instalado
**Solución**:
```bash
pip install spacy
python -m spacy download es_core_news_sm
```

### Frontend muestra pantalla en blanco
**Causa**: Backend no responde o CORS bloqueado
**Solución**:
1. Verifica que Flask está en http://127.0.0.1:5000
2. Abre consola del navegador (F12 → Console)
3. Busca errores de red
4. Verifica que `CORS(APP)` está en `backend/app.py`

### Pestaña "Asesor de Casos" muestra error
**Causa**: Endpoint `/nlp_extract` no disponible
**Solución**:
1. Reinicia Flask
2. Verifica que `nlp_extractor.py` existe
3. Comprueba que spaCy está instalado

---

## 📊 Endpoints API

### Búsqueda y Grafo
- `POST /sparql` → Ejecuta consulta SPARQL

### Asesor de Casos
- `POST /nlp_extract` → Extrae entidades (nuevo)
- `POST /sparql` → Busca leyes aplicables

### Precedentes
- `GET /precedents_for_article?uri=...&limit=50` → Casos relacionados

### Jerarquía
- `POST /sparql` → Estructura de leyes (query personalizada)

### Contradicciones
- `GET /detect_contradictions` → Todos los conflictos
- `POST /sparql` → Conflictos específicos de una ley

---

## 💾 Datos de Prueba

Para probar sin datos reales:
1. Pestaña "Datos" → Ingesta Manual de Texto
2. Ingesta una ley de ejemplo:
```
ID: LEY-PRUEBA-001
Título: Ley de Protección de Datos
Contenido: 
Artículo 1. Se protegen los derechos fundamentales...
Artículo 2. Las obligaciones del responsable son...
```

3. Haz clic en "Procesar e Ingestar"
4. Vuelve a "Búsqueda" y carga todas las leyes

---

## 🎨 Personalizaciones Posibles

### Cambiar colores
Edita `frontend/src/styles.css`:
```css
.nav-item.active {
  background: rgba(255,255,255,0.15);  /* Cambiar aquí */
}
```

### Agregar más módulos
1. Crea `frontend/src/modules/MiModulo.jsx`
2. Importa en `App.jsx`
3. Añade botón en sidebar
4. Añade caso en switch de tabs

### Mejorar NLP
Edita `backend/nlp_extractor.py`:
```python
# Agregar nuevos patrones
KEYWORD_PATTERNS = [
    r'\b(tu patrón aquí)\b',
]
```

---

## 📝 Notas Importantes

1. **Ontología**: Los datos vienen de `Ontologia/legalontosystem_peru.ttl` y `Ontologia/legal_working.ttl`
2. **Grafo**: Es generado dinámicamente desde SPARQL
3. **Zoom/Pan**: Implementado con D3 v7+
4. **NLP**: Requiere descarga de modelo `es_core_news_sm` (~40MB)
5. **Precedentes**: Usa endpoint `/precedents_for_article` del backend

---

## 📞 Contacto / Soporte

Ver documentación completa en `FRONTEND_MODULES.md`

---

**Última actualización**: 9 de Diciembre de 2025
**Versión**: 2.0
**Estado**: Producción (Beta)
