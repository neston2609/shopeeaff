# Windows local setup

Install Python 3.12, Node 20+, Git, FFmpeg/FFprobe and Noto Sans Thai. Ensure executable paths are available. Run `scripts/setup_windows.ps1` from repository root. Copy `.env.example` to `.env`, set an absolute STORAGE_PATH and generate CREDENTIAL_ENCRYPTION_KEY with `.venv\Scripts\python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`.

Load the `.env` values into the PowerShell process (scripts/start_windows.ps1 does this). Initialize administrator with `cd backend; ..\.venv\Scripts\python -m app.admin`. Run backend, worker and frontend in separate terminals as described by the start script. Use the same environment for all Python processes. Open http://localhost:3000.
