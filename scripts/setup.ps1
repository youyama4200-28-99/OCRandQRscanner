$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
Set-Location $projectRoot
if (-not (Test-Path -LiteralPath $venvPython)) {
    py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python virtual environment." }
}
$env:PADDLE_PDX_CACHE_HOME = Join-Path $projectRoot ".cache\paddlex"
function Invoke-ProjectPython {
    & $venvPython @args
    if ($LASTEXITCODE -ne 0) { throw "Python command failed with exit code $LASTEXITCODE." }
}
Invoke-ProjectPython -m pip install --upgrade pip setuptools wheel
Invoke-ProjectPython -m pip install "paddlepaddle==3.3.1" --extra-index-url "https://www.paddlepaddle.org.cn/packages/stable/cpu/"
Invoke-ProjectPython -m pip install -e ".[dev]"
Invoke-ProjectPython -m smartscan --diagnose
Write-Host "Setup completed. Run .\scripts\run.ps1" -ForegroundColor Green
