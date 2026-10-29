#!/usr/bin/env bash
set -euo pipefail
set -a;source .env;set +a
echo 'Run backend: cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100'
echo 'Run worker: cd backend && ../.venv/bin/python -m app.worker'
echo 'Run frontend: cd frontend && npm run dev'
