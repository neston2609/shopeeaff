$ErrorActionPreference='Stop'
Get-Content -LiteralPath .env | ForEach-Object { if ($_ -match '^([A-Z_]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1],$Matches[2],'Process') } }
Write-Host 'Run separately from backend: ../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100'
Write-Host 'Run separately from backend: ../.venv/Scripts/python -m app.worker'
Write-Host 'Run separately from frontend: npm run dev'
