#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 && $# == 1 && -f "$1" ]] || { echo 'Usage: sudo bash scripts/restore_production.sh /absolute/backup.tar.gz'; exit 1; }
ARCHIVE=$(realpath "$1")
WORK=$(mktemp -d /var/backups/shopee-aff-ai-studio/restore.XXXXXX)
trap 'rm -rf -- "$WORK"' EXIT
python3 - "$ARCHIVE" "$WORK" <<'PY'
import tarfile,sys,sqlite3,pathlib
with tarfile.open(sys.argv[1]) as t:t.extractall(sys.argv[2],filter='data')
p=pathlib.Path(sys.argv[2])/'data'/'studio.db'
with sqlite3.connect(p) as c:
 if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Invalid database backup')
PY
bash /app/shopeeaff/scripts/backup_production.sh
systemctl stop shopee-aff-worker shopee-aff-backend
DATA=/var/lib/shopee-aff-ai-studio
[[ $(realpath "$DATA") = /var/lib/shopee-aff-ai-studio ]] || exit 1
mv "$DATA" "$DATA.pre-restore-$(date +%s)"
mv "$WORK/data" "$DATA"
chown -R shopeeaff:shopeeaff "$DATA"
systemctl start shopee-aff-backend shopee-aff-worker
bash /app/shopeeaff/scripts/check_production.sh
