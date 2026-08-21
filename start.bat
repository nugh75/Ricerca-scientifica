@echo off
REM Ricerca - avvio su Windows. / Start Ricerca on Windows.
REM Non serve installare nulla: se manca Python, lo scarica uv in questa cartella.
setlocal
cd /d "%~dp0"

REM Se la cartella dell'app non e' scrivibile, uv lavora sotto %USERPROFILE%\.ricerca.
set "TOOLS=%CD%\.tools"
set "SCRIVIBILE=1"
if exist ".installed" set "SCRIVIBILE=0"
copy /y nul ".prova-scrittura" >nul 2>nul
if errorlevel 1 (
  set "SCRIVIBILE=0"
  set "TOOLS=%USERPROFILE%\.ricerca\tools"
  if not exist "%USERPROFILE%\.ricerca\tools" mkdir "%USERPROFILE%\.ricerca\tools"
) else if "%SCRIVIBILE%"=="1" (
  del ".prova-scrittura" >nul 2>nul
)
if "%SCRIVIBILE%"=="0" if exist ".prova-scrittura" del ".prova-scrittura" >nul 2>nul
if "%SCRIVIBILE%"=="0" (
  set "TOOLS=%USERPROFILE%\.ricerca\tools"
  if not exist "%USERPROFILE%\.ricerca\tools" mkdir "%USERPROFILE%\.ricerca\tools"
)

set "UV="
where uv >nul 2>nul && for /f "delims=" %%i in ('where uv') do set "UV=%%i"
if not defined UV if exist "%TOOLS%\uv.exe" set "UV=%TOOLS%\uv.exe"

if not defined UV (
  echo Preparazione al primo avvio... / First-run setup...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$env:UV_INSTALL_DIR='%TOOLS%'; $env:UV_NO_MODIFY_PATH='1'; irm https://astral.sh/uv/install.ps1 | iex" >nul 2>nul
  if exist "%TOOLS%\uv.exe" set "UV=%TOOLS%\uv.exe"
)

if defined UV (
  if "%SCRIVIBILE%"=="1" (
    "%UV%" run --quiet ricerca serve %*
  ) else (
    set "VENV=%USERPROFILE%\.ricerca\venv"
    set "VERSIONE="
    for /f "tokens=2 delims== " %%v in ('findstr /b /c:"version" pyproject.toml') do if not defined VERSIONE set "VERSIONE=%%~v"
    set "INSTALLATA="
    if exist "%USERPROFILE%\.ricerca\venv\.versione" set /p INSTALLATA=<"%USERPROFILE%\.ricerca\venv\.versione"
    REM Senza questo confronto una versione nuova non verrebbe mai installata.
    if not exist "%USERPROFILE%\.ricerca\venv\Scripts\ricerca.exe" set "INSTALLATA=nessuna"
    if not "%INSTALLATA%"=="%VERSIONE%" (
      echo Preparazione dell'ambiente in %USERPROFILE%\.ricerca ...
      "%UV%" venv --quiet --clear --python 3.12 "%USERPROFILE%\.ricerca\venv"
      "%UV%" pip install --quiet --python "%USERPROFILE%\.ricerca\venv\Scripts\python.exe" .
      echo %VERSIONE%>"%USERPROFILE%\.ricerca\venv\.versione"
    )
    "%USERPROFILE%\.ricerca\venv\Scripts\ricerca.exe" serve %*
  )
  goto :fine
)

where python >nul 2>nul
if errorlevel 1 (
  echo Non sono riuscito a scaricare uv e non trovo Python.
  echo Could not download uv and no Python found: https://www.python.org/downloads/
  pause
  exit /b 1
)
if "%SCRIVIBILE%"=="0" goto :python_utente
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\pip install --quiet --upgrade pip
  .venv\Scripts\pip install --quiet -e .
)
.venv\Scripts\ricerca serve %*
goto :fine

:python_utente
set "VENV=%USERPROFILE%\.ricerca\venv"
set "VERSIONE="
for /f "tokens=2 delims== " %%v in ('findstr /b /c:"version" pyproject.toml') do if not defined VERSIONE set "VERSIONE=%%~v"
set "INSTALLATA="
if exist "%USERPROFILE%\.ricerca\venv\.versione" set /p INSTALLATA=<"%USERPROFILE%\.ricerca\venv\.versione"
if not exist "%USERPROFILE%\.ricerca\venv\Scripts\ricerca.exe" set "INSTALLATA=nessuna"
if not "%INSTALLATA%"=="%VERSIONE%" (
  python -m venv --clear "%USERPROFILE%\.ricerca\venv"
  "%USERPROFILE%\.ricerca\venv\Scripts\pip.exe" install --quiet --upgrade pip
  "%USERPROFILE%\.ricerca\venv\Scripts\pip.exe" install --quiet .
  echo %VERSIONE%>"%USERPROFILE%\.ricerca\venv\.versione"
)
"%USERPROFILE%\.ricerca\venv\Scripts\ricerca.exe" serve %*

:fine
pause
