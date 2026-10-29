#!/usr/bin/env bash
set -euo pipefail
cd /app/shopeeaff
bash scripts/backup_production.sh
git pull --ff-only
bash scripts/deploy_production.sh
bash scripts/check_production.sh
