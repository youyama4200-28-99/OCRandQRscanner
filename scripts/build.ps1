param(
    [switch]$SkipSmokeTest,
    [switch]$Archive
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$specPath = Join-Path $projectRoot "packaging\SmartScan.spec"
$bundlePath = Join-Path $projectRoot "dist\SmartScan"
$executablePath = Join-Path $bundlePath "SmartScan.exe"
$settingsSource = Join-Path $projectRoot "config\settings.json"
$settingsDestination = Join-Path $bundlePath "config"
$smokeLog = Join-Path $projectRoot "build\bundle-smoke-test.log"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}

Set-Location $projectRoot
$env:PADDLE_PDX_CACHE_HOME = Join-Path $projectRoot ".cache\paddlex"

& $venvPython -m PyInstaller --noconfirm --clean $specPath
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed with code $LASTEXITCODE." }

New-Item -ItemType Directory -Path $settingsDestination -Force | Out-Null
Copy-Item -LiteralPath $settingsSource -Destination $settingsDestination -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $bundlePath -Force

if (-not $SkipSmokeTest) {
    $env:SMARTSCAN_SMOKE_LOG = $smokeLog
    $process = Start-Process -FilePath $executablePath -ArgumentList "--smoke-test" `
        -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $smokeLog) { Get-Content -LiteralPath $smokeLog }
        throw "Bundled executable smoke test failed with code $($process.ExitCode)."
    }
    Get-Content -LiteralPath $smokeLog
}

if ($Archive) {
    $archivePath = Join-Path $projectRoot "dist\SmartScan-windows-x64.zip"
    if (Test-Path -LiteralPath $archivePath) { Remove-Item -LiteralPath $archivePath -Force }
    Compress-Archive -LiteralPath $bundlePath -DestinationPath $archivePath -CompressionLevel Optimal
    Write-Host "Archive: $archivePath" -ForegroundColor Green
}

Write-Host "Build completed: $executablePath" -ForegroundColor Green
