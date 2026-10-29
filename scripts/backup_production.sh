#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run as root';exit 1; }
DIR=/var/backups/shopee-aff-ai-studio
install -d -m 700 "$DIR"
WORK=$(mktemp -d "$DIR/staging.XXXXXX")
trap 'rm -rf -- "$WORK"' EXIT
# Stop writer services for a consistent DB + media snapshot. Frontend remains online.
systemctl stop shopee-aff-worker shopee-aff-backend
trap 'systemctl start shopee-aff-backend shopee-aff-worker; rm -rf -- "$WORK"' EXIT
python3 - "$WORK" <<'PY'
import sqlite3,sys,pathlib,shutil
source=pathlib.Path('/var/lib/shopee-aff-ai-studio')
target=pathlib.Path(sys.argv[1])/'data';target.mkdir()
with sqlite3.connect(source/'studio.db') as src, sqlite3.connect(target/'studio.db') as dst:src.backup(dst)
for p in source.iterdir():
 if p.is_dir():shutil.copytree(p,target/p.name)
(pathlib.Path(sys.argv[1])/'config-redacted.txt').write_text('APP_ENV=production\nAPP_URL=https://aff.pramool.bid\nSecrets are excluded. Back up /etc/shopee-aff-ai-studio/production.env separately using encrypted storage.\n')
PY
tar -czf "$DIR/backup-$(date -u +%Y%m%dT%H%M%SZ).tar.gz" -C "$WORK" .
chmod 600 "$DIR"/*.tar.gz
find "$DIR" -maxdepth 1 -name 'backup-*.tar.gz' -type f -mtime +14 -delete
echo 'Consistent database and media backup complete; retention 14 days.'
