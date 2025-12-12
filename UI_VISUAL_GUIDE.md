# 🎨 Guía Visual de LegalOnto v2.0

## Estructura de la Interfaz

```
┌────────────────────────────────────────────────────────────────────┐
│  LegalOnto v1.0                                                      │
│  Sistema Jurídico                                          [Avatar]  │
├──────────────────────────────────────────────────────────────────────┤
│                           PÁGINA ACTUAL                               │
│  Búsqueda y Visualización de Leyes                                  │
├──────────────────────────────────────────────────────────────────────┤
│ SIDEBAR    │                                                          │
│            │  ┌─────────────────────────────────────────────────┐   │
│ 🏠 Búsqu.  │  │ Búsqueda                  [Buscar]  [Cargar]   │   │
│            │  ├─────────────────────────────────────────────────┤   │
│ 📋 Asesor  │  │  Grafo de Relaciones        │  Información      │   │
│            │  │  (Zoom/Pan)                 │  Detallada        │   │
│ ⚖️  Prec.  │  │  🔍 Reset (x1.00)          │  (propiedades)    │   │
│            │  │                             │                    │   │
│ 🌳 Jer.   │  │  [Nodo 1] ─── [Nodo 2]    │                    │   │
│            │  │     ↓                       │  Selecciona un    │   │
│ ⚠️ Contr.  │  │  [Nodo 3]                 │  elemento         │   │
│            │  │                             │                    │   │
│ 📥 Datos   │  └─────────────────────────────────────────────────┘   │
│            │                                                          │
│ ⚡ SPARQL  │                                                          │
│            │                                                          │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flujos de Trabajo por Módulo

### 1️⃣ BÚSQUEDA Y GRAFO (Pestaña "Búsqueda")

```
ENTRADA                 PROCESAMIENTO               SALIDA
┌──────────────┐       ┌─────────────────┐       ┌──────────────┐
│ Escribe:     │  ───> │ SPARQL Query    │  ───> │ Grafo D3     │
│ "trabajo"    │       │ → RDFlib        │       │ interactivo  │
└──────────────┘       └─────────────────┘       └──────────────┘
         │                                              │
         │                                              └─> Zoom/Pan
         │                                              └─> Reset
         └─> [Buscar]
             [Cargar todas]
             
INTERACCIÓN:
• Rueda del ratón = Acercar/Alejar
• Arrastra fondo = Mover grafo
• Clic en nodo = Ver propiedades
• [Reset] = Volver al original
```

### 2️⃣ ASESOR DE CASOS (Pestaña "Asesor de Casos")

```
ENTRADA                 PROCESAMIENTO                  SALIDA
┌──────────────────────────┐      ┌──────────────┐   ┌─────────────┐
│ "Un cliente fue          │      │ spaCy NLP    │   │ Entidades:  │
│  despedido sin causa.    │ ───> │ + Regex      │───> │ Artículos: 5,10│
│  Ley N° 27444, Art. 5"   │      │ Patterns     │   │ Leyes: 27444│
└──────────────────────────┘      └──────────────┘   │ Conceptos:  │
         │                                           │ [despido]   │
         │                                           └─────────────┘
         │                                                  │
         └─> [Analizar]                                    └─> Recomendaciones
                                                               ⚖️ Ley Aplicable
                                                               ✓ Fundamentación
                                                               
RESULTADO:
┌─────────────────────────────────┐
│ ENTIDADES EXTRAÍDAS              │
├─────────────────────────────────┤
│ Artículos: [5, 10]              │
│ Leyes: [27444]                  │
│ Conceptos: despido, contrato... │
│ Personas: ... XYZ Co.           │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ LEYES RECOMENDADAS               │
├─────────────────────────────────┤
│ 1. Ley de Trabajo (27444)       │
│    Art. 5: Protecciones        │
│ 2. Ley de Protección (...)     │
│    Art. 12: Derechos...        │
└─────────────────────────────────┘
```

### 3️⃣ PRECEDENTES (Pestaña "Precedentes")

```
SELECCIÓN               BÚSQUEDA                  RANKING
┌──────────────────┐   ┌──────────────┐   ┌──────────────────┐
│ [▼ Selecciona    │   │ /precedents_ │   │ #1 Case A        │
│  Ley N° 27444]   │─> │ for_article  │─> │ Score: 95%       │
└──────────────────┘   │ Endpoint     │   │ 📍 Lima          │
         │             │ + Ranking    │   │ 📅 2024-01-15   │
         │             └──────────────┘   └──────────────────┘
         │                                 │ #2 Case B         │
         └─> [Buscar Precedentes]         │ Score: 87%       │
                                          │ 📍 Arequipa      │
                                          │ 📅 2023-06-20   │
                                          └──────────────────┘
```

### 4️⃣ JERARQUÍA (Pestaña "Jerarquía")

```
VISUALIZACIÓN D3
┌──────────────────────────────────────┐
│  Ordenamiento Jurídico (Raíz)        │
│           │                          │
│     ┌─────┴─────┬────────┐          │
│     │           │        │          │
│   Ley A       Ley B    Ley C        │
│   /   \       |  |      |  |        │
│  Art  Art    Art Art   Art Art      │
│  1    2      1   2     1   2        │
└──────────────────────────────────────┘

ESTADÍSTICAS:
┌─────────────┬──────────────┐
│ Leyes: 100  │ Artículos: 450
└─────────────┴──────────────┘
```

### 5️⃣ CONTRADICCIONES (Pestaña "Contradicciones")

```
OPCIÓN 1: GLOBAL
┌──────────────────────────┐
│ [Cargar Todas las        │
│  Contradicciones]        │
└──────────────────────────┘
         │
         └──> Analiza TODA la ontología

OPCIÓN 2: ESPECÍFICA
┌──────────────────────────┐
│ [▼ Selecciona Ley]       │
│ [Analizar]               │
└──────────────────────────┘
         │
         └──> Busca conflictos de esa ley


RESULTADOS:
┌──────────────────────────────────┐
│ ⚠️ CONFLICTO #1                 │
├──────────────────────────────────┤
│ 🔴 ALTO: Ley A DEROGA Ley B    │
│          (Vigencia: 2020)        │
│ Impacto: Ley B ya no aplica      │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ ⚠️ CONFLICTO #2                 │
├──────────────────────────────────┤
│ 🟡 MEDIO: Ley A MODIFICA Ley C  │
│           (Art. 5)               │
│ Impacto: Incompatibilidad parcial│
└──────────────────────────────────┘
```

---

## 🎯 Flujos de Uso Común

### Flujo 1: Investigar una Ley
```
1. Ve a "Búsqueda"
2. Escribe nombre de ley
3. Observa grafo de relaciones
4. Zoom para ver conexiones
5. Clic en nodo para propiedades
6. Vuelve a "Jerarquía" para ver estructura completa
```

### Flujo 2: Asesorar un Caso
```
1. Ve a "Asesor de Casos"
2. Describe el caso (copia/pega descripción)
3. [Analizar y Recomendar]
4. Lee entidades extraídas
5. Revisa leyes recomendadas
6. Ve a "Precedentes" para casos similares
```

### Flujo 3: Buscar Precedentes
```
1. Ve a "Precedentes"
2. Selecciona una ley
3. [Buscar Precedentes]
4. Revisa ranking de casos
5. Haz clic para más detalles
6. Compara con tu caso
```

### Flujo 4: Identificar Conflictos
```
1. Ve a "Contradicciones"
2. [Cargar Todas las Contradicciones]
   O selecciona ley específica + [Analizar]
3. Lee lista de conflictos
4. Verifica grado de severidad
5. Entiende impacto de cada conflicto
```

---

## 📱 Respuesta Responsive

### Desktop (>1200px)
```
┌──────────────────────────────────────────┐
│ [SIDEBAR] │ [CONTENIDO PRINCIPAL]        │
│           │                              │
│ 7 opciones│ Dos columnas lado a lado    │
│           │ (Grafo | Detalles)           │
└──────────────────────────────────────────┘
```

### Tablet (768-1200px)
```
┌──────────────────────────────────────────┐
│ [SIDEBAR] │ [CONTENIDO PRINCIPAL]        │
│           │                              │
│ 7 opciones│ Una columna adaptada         │
│           │ (Responsive)                 │
└──────────────────────────────────────────┘
```

### Mobile (<768px)
```
┌─────────────────────────────────┐
│ [≡] │ PÁGINA ACTUAL             │
├─────────────────────────────────┤
│ [CONTENIDO PRINCIPAL]           │
│                                 │
│ (Optimizado para pantalla      │
│  pequeña, stack vertical)       │
└─────────────────────────────────┘

[≡] = Menú sidebar colapsible
```

---

## 🎨 Paleta de Colores

```
Primario:         #1e40af (Azul Legal)
  ↳ En botones, títulos, enlaces

Secundario:       #3b82f6 (Azul Claro)
  ↳ En hovers, estados activos

Advertencia:      #dc2626 (Rojo)
  ↳ En contradicciones, errores

Éxito:            #10b981 (Verde)
  ↳ En confirmaciones

Info:             #0369a1 (Azul Oscuro)
  ↳ En información, badges

Neutro:           #64748b (Gris)
  ↳ En textos secundarios
```

---

## 🔊 Feedback Visual

```
ESTADOS DE BOTONES:
┌────────────────┐ Normal
│ [Buscar]       │
└────────────────┘
     │
     └──> Hover → Cambia color
     │
     └──> Disabled → Opacidad reducida
     │
     └──> Loading → Animación spinner

INDICADORES:
✓ Éxito         (verde)
✗ Error         (rojo)
⚠ Advertencia   (naranja)
ℹ Información   (azul)

ANIMACIONES:
• Transición de zoom: 750ms
• Cambio de color: 200ms
• Aparición de modal: 300ms
```

---

## 📊 Ejemplos de Datos

### Entrada: Caso de Uso
```
"Juan García trabaja en empresa ABC desde 2020.
 Fue despedido el 1 de diciembre sin aviso previo.
 La empresa alega reestructuración.
 Juan desea saber qué protecciones tiene.
 Menciona el Art. 15 de la Ley de Trabajo."
```

### Salida: Análisis NLP
```
Artículos extraídos: [15]
Leyes extraídas: []
Entidades: [Juan García, empresa ABC]
Conceptos: [despido, contrato, derechos]
```

### Salida: Leyes Recomendadas
```
1. Ley de Trabajo N° 27442 (Score: 98%)
   Art. 15: Protecciones al despido
   
2. Ley de Protección de Derechos (Score: 85%)
   Art. 8: Derechos laborales
```

---

## ✨ Características Visuales Destacadas

### Grafo Interactivo
- 🎯 Nodos circulares coloreados
- 🔗 Enlaces con opacidad dinámica
- 📌 Labels con truncamiento inteligente
- 🎨 Colores según tipo de norma
- 🔄 Animación de fuerzas continua

### Árbol Jerárquico
- 🌳 Estructura vertical clara
- 📊 Nodos más grandes = más importante
- 🔗 Enlaces suave curvados
- 📈 Scroll infinito

### Listas de Resultados
- ⭐ Rating/Score visual
- 📍 Iconos de ubicación
- 📅 Fechas formateadas
- 🏷️ Badges de categoría
- 📄 Truncamiento de texto largo

---

## 🎓 Convenciones de UI

```
BUTTONS:
[Primario]     - Azul, acciones principales
[Secundario]   - Gris, acciones secundarias
[Peligro]      - Rojo, acciones destructivas
[Deshabilitado] - Opaco, no interactivo

INPUTS:
Texto          - Borde gris, fondo blanco
Textarea       - Fuente monoespaciada
Select         - Dropdown con icono
Checkbox       - Cuadrado con checkmark

CARDS:
Título         - Negrita, #1e3a8a
Descripción    - Normal, #475569
Metadatos      - Pequeño, #94a3b8
Acción         - Enlace azul
```

---

**Esta es la interfaz visual de LegalOnto v2.0** 🎉

Para interactuar, abre el navegador en `http://localhost:5173`
