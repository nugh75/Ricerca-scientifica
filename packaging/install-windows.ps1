$ErrorActionPreference = "Stop"

$Source = (Resolve-Path $PSScriptRoot).Path
$Base = $env:LOCALAPPDATA
$Target = Join-Path $Base "Ricerca"
$Temporary = Join-Path $Base (".Ricerca-install-" + $PID)
$Previous = Join-Path $Base "Ricerca-previous"

if ($Source.TrimEnd('\') -ieq $Target.TrimEnd('\')) {
    Start-Process (Join-Path $Target "start.bat")
    exit 0
}

if (Test-Path $Temporary) { Remove-Item -LiteralPath $Temporary -Recurse -Force }
New-Item -ItemType Directory -Path $Temporary | Out-Null
Get-ChildItem -LiteralPath $Source -Force |
    Where-Object { $_.Name -notin @('.tools', '.venv') } |
    Copy-Item -Destination $Temporary -Recurse -Force
New-Item -ItemType File -Path (Join-Path $Temporary '.installed') | Out-Null

# Keep one previous copy for recovery, instead of accumulating releases.
if (Test-Path $Previous) { Remove-Item -LiteralPath $Previous -Recurse -Force }
if (Test-Path $Target) { Move-Item -LiteralPath $Target -Destination $Previous }
try {
    Move-Item -LiteralPath $Temporary -Destination $Target
} catch {
    if (!(Test-Path $Target) -and (Test-Path $Previous)) {
        Move-Item -LiteralPath $Previous -Destination $Target
    }
    throw
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Ricerca.lnk'))
$Shortcut.TargetPath = Join-Path $Target 'start.bat'
$Shortcut.WorkingDirectory = $Target
$Shortcut.IconLocation = Join-Path $Target 'Ricerca.ico'
$Shortcut.Description = 'Literature search assistant'
$Shortcut.Save()

Write-Host "Ricerca updated in $Target"
Start-Process (Join-Path $Target "start.bat")
