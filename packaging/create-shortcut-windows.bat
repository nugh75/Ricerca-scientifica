@echo off
REM Crea un collegamento a Ricerca sul Desktop, con icona.
REM Creates a desktop shortcut to Ricerca, with icon.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Ricerca.lnk');" ^
  "$s.TargetPath='%CD%\start.bat'; $s.WorkingDirectory='%CD%';" ^
  "$s.IconLocation='%CD%\Ricerca.ico'; $s.Description='Assistente di strategia di ricerca bibliografica'; $s.Save()"
echo Collegamento creato sul Desktop. / Shortcut created on the Desktop.
pause
