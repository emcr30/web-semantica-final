@echo off
REM Regenerate Penal Code RDF Data
REM Script for Windows PowerShell

echo Regenerating Penal Code RDF data...
cd backend
.\.venv\Scripts\python.exe ingest_penal_code.py
echo.
echo Done! Data saved to Ontologia\legal_working.ttl
pause
