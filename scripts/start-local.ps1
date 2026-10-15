param([switch]$Install)
$ErrorActionPreference = 'Stop'
$sinyaraRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $sinyaraRoot
if ($Install) {
    uv sync --extra audio --extra eval
    if ($LASTEXITCODE -ne 0) { throw 'Dependency Python gagal dipasang.' }
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Dependency frontend gagal dipasang.' }
}
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if (-not (Test-Path -LiteralPath '.env.local')) { Copy-Item -LiteralPath '.env.frontend.example' -Destination '.env.local' }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) { throw 'Jalankan scripts/start-local.ps1 -Install terlebih dahulu.' }
$sinyaraPython = Join-Path $sinyaraRoot '.venv/Scripts/python.exe'
$sinyaraServer = Start-Process -FilePath $sinyaraPython -ArgumentList '-m','uvicorn','sinyara.api:app','--host','127.0.0.1','--port','8010','--no-access-log' -WorkingDirectory $sinyaraRoot -WindowStyle Hidden -PassThru
Write-Host 'API: http://127.0.0.1:8010/docs'
Write-Host 'Frontend: http://127.0.0.1:5174 — Ctrl+C untuk berhenti.'
try { npm.cmd run dev }
finally { if (-not $sinyaraServer.HasExited) { Stop-Process -Id $sinyaraServer.Id } }
