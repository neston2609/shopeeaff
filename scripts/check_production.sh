#!/usr/bin/env bash
set -euo pipefail
systemctl is-active shopee-aff-frontend shopee-aff-backend shopee-aff-worker
curl --fail --silent --show-error https://aff.pramool.bid/api/health
curl --fail --silent --show-error https://aff.pramool.bid/ >/dev/null
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://aff.pramool.bid/)
[[ $CODE = 301 || $CODE = 308 ]] || { echo 'HTTP redirect missing';exit 1; }
echo 'HTTPS, redirect, homepage and API checks passed.'
