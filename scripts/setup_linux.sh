#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm ci)
echo 'Configure .env and initialize administrator; see docs/INSTALL_LINUX.md.'
