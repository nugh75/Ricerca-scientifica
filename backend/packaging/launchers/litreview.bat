@echo off
setlocal

set "BASE_URL=%LITREVIEW_ASSET_URL%"
if "%BASE_URL%"=="" set "BASE_URL=https://github.com/nugh75/Ricerca-scientifica/releases/latest/download"
set "ASSET=litreview-backend-windows.exe"
set "BIN_DIR=%USERPROFILE%\.litreview\bin"
set "BIN=%BIN_DIR%\%ASSET%"

if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

where curl.exe >nul 2>&1
if errorlevel 1 goto use_powershell

echo Downloading LitReview backend...
curl.exe -fsSL --retry 3 -o "%BIN%.tmp" "%BASE_URL%/%ASSET%"
if errorlevel 1 (
  echo Errore: download fallito da %BASE_URL%/%ASSET% 1>&2
  exit /b 1
)
move /y "%BIN%.tmp" "%BIN%" >nul
"%BIN%"
exit /b %errorlevel%

:use_powershell
echo Downloading LitReview backend...
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%BASE_URL%/%ASSET%' -OutFile '%BIN%.tmp'"
if errorlevel 1 (
  echo Errore: download fallito da %BASE_URL%/%ASSET% 1>&2
  exit /b 1
)
move /y "%BIN%.tmp" "%BIN%" >nul
"%BIN%"
exit /b %errorlevel%
