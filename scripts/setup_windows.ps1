$ErrorActionPreference='Stop'
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Push-Location frontend
npm ci
Pop-Location
Write-Host 'Configure .env and initialize the administrator; see docs/INSTALL_WINDOWS.md.'
