#!/bin/bash
# setup.sh - Script de instalación de dependencias para LegalOnto v2.0

echo "==============================================="
echo "LegalOnto v2.0 - Instalación de Dependencias"
echo "==============================================="
echo ""

# Detectar sistema operativo
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "Sistema detectado: Windows (PowerShell/Git Bash)"
    IS_WINDOWS=true
else
    echo "Sistema detectado: Unix/Linux/Mac"
    IS_WINDOWS=false
fi

echo ""
echo "========== BACKEND SETUP =========="
echo "Instalando dependencias del backend..."
echo ""

cd backend 2>/dev/null || cd ../backend 2>/dev/null || {
    echo "Error: No se encontró la carpeta 'backend'"
    echo "Por favor, ejecuta este script desde la raíz del proyecto"
    exit 1
}

# Verificar/crear venv
if [ ! -d ".venv" ]; then
    echo "Creando virtual environment..."
    python -m venv .venv
fi

# Activar venv
if [ "$IS_WINDOWS" = true ]; then
    echo "Activando venv (Windows)..."
    source .venv/Scripts/activate
else
    echo "Activando venv (Unix/Linux)..."
    source .venv/bin/activate
fi

echo "Instalando paquetes Python..."
pip install --upgrade pip
pip install flask flask-cors rdflib requests spacy

echo ""
echo "Descargando modelo de spaCy para español..."
python -m spacy download es_core_news_sm

if [ $? -eq 0 ]; then
    echo "✓ Modelo spaCy descargado exitosamente"
else
    echo "⚠ Advertencia: No se pudo descargar es_core_news_sm"
    echo "  El sistema funcionará con modelo en blanco"
fi

echo ""
echo "========== FRONTEND SETUP =========="
cd ../frontend 2>/dev/null || cd ../../frontend 2>/dev/null || {
    echo "Error: No se encontró la carpeta 'frontend'"
    exit 1
}

echo "Verificando Node.js..."
if ! command -v node &> /dev/null; then
    echo "Error: Node.js no está instalado"
    echo "Descarga desde: https://nodejs.org/"
    exit 1
fi

echo "Versión de Node: $(node --version)"
echo "Versión de npm: $(npm --version)"

echo ""
echo "Instalando dependencias de npm..."
npm install

echo ""
echo "==============================================="
echo "✓ Instalación completada"
echo "==============================================="
echo ""
echo "Próximos pasos:"
echo ""
echo "Terminal 1 (Backend):"
echo "  cd backend"
echo "  source .venv/Scripts/activate  (Windows)"
echo "  source .venv/bin/activate      (Unix/Mac)"
echo "  python -m flask --app app:APP run --host=127.0.0.1 --port=5000"
echo ""
echo "Terminal 2 (Frontend):"
echo "  cd frontend"
echo "  npm run dev"
echo ""
echo "Luego abre el navegador en:"
echo "  http://localhost:5173"
echo ""
