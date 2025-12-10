@echo off
rem Start Flask using the venv python (no need to activate)
set PROJECT_ROOT=%~dp0\..
set VENV_PY=%PROJECT_ROOT%\.venv\Scripts\python.exe
if not exist "%VENV_PY%" (
  echo Could not find %VENV_PY%. Ensure .venv exists or activate manually.
  exit /b 1
)
"%VENV_PY%" -m flask run --host=127.0.0.1 --port=5000
