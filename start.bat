@echo off
REM ECHO — start the local backend companion (Windows).
REM Start Supermemory Local first (it must serve http://localhost:6767).

cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo Starting ECHO backend on http://localhost:8765 ...
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
