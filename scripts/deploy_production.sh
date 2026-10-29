#!/usr/bin/env bash
set -euo pipefail
ROOT=/app/shopeeaff
CONF=/etc/shopee-aff-ai-studio
DATA=/var/lib/shopee-aff-ai-studio
[[ $EUID == 0 ]] || { echo 'Run with sudo bash scripts/deploy_production.sh'; exit 1; }
source /etc/os-release
[[ "$ID" = ubuntu || "$ID" = debian ]] || { echo 'Only Debian/Ubuntu are supported'; exit 1; }
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip ffmpeg fonts-noto-core nginx certbot curl
node -e 'if(+process.versions.node.split(".")[0]<20)process.exit(1)' || { echo 'Install Node.js 20+ first'; exit 1; }
id shopeeaff >/dev/null 2>&1 || useradd --system --home "$DATA" --shell /usr/sbin/nologin shopeeaff
install -d -m 750 -o shopeeaff -g shopeeaff "$DATA"
install -d -m 750 -o root -g shopeeaff "$CONF"
if [[ ! -f "$CONF/production.env" ]]; then
 python3 -m venv "$ROOT/.venv"
 "$ROOT/.venv/bin/pip" install cryptography
 KEY=$("$ROOT/.venv/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
 umask 027
 cat > "$CONF/production.env" <<EOF
APP_ENV=production
APP_NAME="Shopee Aff AI Studio"
APP_URL=https://aff.pramool.bid
NEXT_PUBLIC_APP_URL=https://aff.pramool.bid
API_BASE_URL=https://aff.pramool.bid/api
ALLOWED_HOSTS=aff.pramool.bid,127.0.0.1,localhost
CORS_ALLOWED_ORIGINS=https://aff.pramool.bid
STORAGE_PATH=$DATA
DATABASE_URL=sqlite:///$DATA/studio.db
CREDENTIAL_ENCRYPTION_KEY=$KEY
SESSION_SECRET=$(openssl rand -hex 48)
LOG_LEVEL=INFO
WORKER_CONCURRENCY=1
MAX_GENERATION_COST=10
EOF
 chown root:shopeeaff "$CONF/production.env"; chmod 640 "$CONF/production.env"
fi
[[ -d "$ROOT/.venv" ]] || python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install -r "$ROOT/backend/requirements.txt"
cd "$ROOT/frontend"
npm ci --no-audit --no-fund
APP_ENV=production NEXT_TELEMETRY_DISABLED=1 npm run build
mkdir -p .next/standalone/.next
cp -a .next/static .next/standalone/.next/
if [[ -d public ]]; then cp -a public .next/standalone/; fi
cd "$ROOT/backend"
set -a; source "$CONF/production.env";set +a
"$ROOT/.venv/bin/alembic" upgrade head
chown -R shopeeaff:shopeeaff "$DATA"
for service in frontend backend worker; do
 cp "$ROOT/deployment/systemd/shopee-aff-$service.service" /etc/systemd/system/
done
cp "$ROOT/deployment/systemd/shopee-aff-backup.service" /etc/systemd/system/
cp "$ROOT/deployment/systemd/shopee-aff-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now shopee-aff-frontend shopee-aff-backend shopee-aff-worker shopee-aff-backup.timer
systemctl restart shopee-aff-frontend shopee-aff-backend shopee-aff-worker
echo 'Application services installed. Configure the dedicated Nginx host and TLS using docs/PRODUCTION_DEPLOYMENT.md, then run scripts/check_production.sh.'
