@echo off
REM Avvio di Ricerca su Windows. / Start Ricerca on Windows.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Serve Python 3.11 o superiore: https://www.python.org/downloads/
  echo Python 3.11+ is required: https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist .venv (
  echo Preparazione dell'ambiente... / Preparing the environment...
  python -m venv .venv
  .venv\Scripts\pip install --quiet --upgrade pip
  .venv\Scripts\pip install --quiet -e .
)

.venv\Scripts\ricerca serve %*
pause
