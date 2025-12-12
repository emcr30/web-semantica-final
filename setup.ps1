# setup.ps1 - Script de instalación para Windows PowerShell

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "LegalOnto v2.0 - Instalación de Dependencias" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Backend Setup
Write-Host "========== BACKEND SETUP ==========" -ForegroundColor Yellow
Write-Host "Instalando dependencias del backend..." -ForegroundColor Green
Write-Host ""

Push-Location
try {
    cd backend
} catch {
    Write-Host "Error: No se encontró la carpeta 'backend'" -ForegroundColor Red
    Write-Host "Ejecuta el script desde la raíz del proyecto" -ForegroundColor Red
    exit 1
}

# Crear venv si no existe
if (-not (Test-Path ".\.venv")) {
    Write-Host "Creando virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

# Activar venv
Write-Host "Activando venv..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

# Instalar dependencias
Write-Host "Instalando paquetes Python..." -ForegroundColor Cyan
pip install --upgrade pip
pip install flask flask-cors rdflib requests spacy beautifulsoup4 pdfminer.six

# Descargar modelo spaCy
Write-Host "Descargando modelo de spaCy para español..." -ForegroundColor Cyan
python -m spacy download es_core_news_sm

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Modelo spaCy descargado exitosamente" -ForegroundColor Green
} else {
    Write-Host "⚠ Advertencia: No se pudo descargar es_core_news_sm" -ForegroundColor Yellow
    Write-Host "  El sistema funcionará con modelo en blanco" -ForegroundColor Yellow
}

Pop-Location

# Frontend Setup
Write-Host ""
Write-Host "========== FRONTEND SETUP ==========" -ForegroundColor Yellow
Write-Host "Instalando dependencias del frontend..." -ForegroundColor Green

Push-Location
try {
    cd frontend
} catch {
    Write-Host "Error: No se encontró la carpeta 'frontend'" -ForegroundColor Red
    exit 1
}

# Verificar Node.js
Write-Host "Verificando Node.js..." -ForegroundColor Cyan
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Node.js no está instalado" -ForegroundColor Red
    Write-Host "Descarga desde: https://nodejs.org/" -ForegroundColor Red
    exit 1
}

Write-Host "Versión de Node: $(node --version)" -ForegroundColor Green
Write-Host "Versión de npm: $(npm --version)" -ForegroundColor Green

# Instalar npm dependencies
Write-Host ""
Write-Host "Instalando dependencias de npm..." -ForegroundColor Cyan
npm install

Pop-Location

# Resumen final
Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "✓ Instalación completada" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Próximos pasos:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Terminal 1 (Backend):" -ForegroundColor Cyan
Write-Host "  cd backend" -ForegroundColor White
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  python -m flask --app app:APP run --host=127.0.0.1 --port=5000 --reload" -ForegroundColor White
Write-Host ""
Write-Host "Terminal 2 (Frontend):" -ForegroundColor Cyan
Write-Host "  cd frontend" -ForegroundColor White
Write-Host "  npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "Luego abre el navegador en:" -ForegroundColor Cyan
Write-Host "  http://localhost:5173" -ForegroundColor White
Write-Host ""
