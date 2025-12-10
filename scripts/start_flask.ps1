# Start Flask using the venv python so activation is not required interactively.
# Usage: .\scripts\start_flask.ps1
# Determine project root (script is in ./scripts/, so project root is parent of that)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projRoot = Split-Path -Parent $scriptDir
Push-Location $projRoot
try {
    $venvPython = Join-Path $projRoot ".venv\Scripts\python.exe"
    if (-Not (Test-Path $venvPython)) {
        # Fallback: if the user already activated the venv in this session, use the active 'python'
        $activePython = (Get-Command python -ErrorAction SilentlyContinue).Path
        if ($activePython) {
            Write-Host "Using active python at $activePython" -ForegroundColor Green
            $venvPython = $activePython
        } else {
            Write-Host "Could not find venv python at $venvPython. Ensure .venv exists or activate manually." -ForegroundColor Yellow
            return
        }
    }
    # Use the determined python to run flask; .env will be read by python-dotenv when Flask starts
    & $venvPython -m flask run --host=127.0.0.1 --port=5000
} finally {
    Pop-Location
}
