# Cria um backup criptografado do banco (usa as configurações do arquivo .env).
# Uso: powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
$ErrorActionPreference = "Stop"

$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Ambiente virtual não encontrado em $python. Veja o README."
    exit 1
}

Push-Location $raiz
try {
    & $python manage.py backup_banco
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
