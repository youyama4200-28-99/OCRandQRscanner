$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$settingsPath = Join-Path $projectRoot "config\settings.json"
if (-not (Test-Path -LiteralPath $venvPython)) { throw "Run .\scripts\setup.ps1 first." }
$env:PADDLE_PDX_CACHE_HOME = Join-Path $projectRoot ".cache\paddlex"
Set-Location $projectRoot
& $venvPython -m smartscan --config $settingsPath
if ($LASTEXITCODE -ne 0) { throw "SmartScan exited with code $LASTEXITCODE." }
