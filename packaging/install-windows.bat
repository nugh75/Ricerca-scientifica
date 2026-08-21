@echo off
REM Install or update Ricerca in LocalAppData, refresh the shortcut, and start it.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-or-update.ps1"
if errorlevel 1 pause
