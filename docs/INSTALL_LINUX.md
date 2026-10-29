# Linux local setup

Install Node 20+, Python 3.12, FFmpeg and Noto Sans Thai fonts. From repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
# Generate Fernet key, set CREDENTIAL_ENCRYPTION_KEY in .env; set an absolute STORAGE_PATH.
.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
set -a; source .env;set +a
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.admin
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100
```

In a second terminal, load the same environment, `cd backend` and run `../.venv/bin/python -m app.worker`. In a third: `cd frontend && npm ci && npm run dev`. Open http://localhost:3000. The development proxy sends same-origin API calls to 127.0.0.1:8100.
