#!/usr/bin/env bash
set -euo pipefail
[[ $EUID = 0 ]] || { echo 'Run as root'; exit 1; }
ROOT=/app/shopeeaff
SITE=/etc/nginx/sites-available/shopeeaff
LINK=/etc/nginx/sites-enabled/shopeeaff
getent ahostsv4 aff.pramool.bid >/dev/null || { echo 'DNS missing: A aff -> 103.40.118.129'; exit 1; }
if [[ -e "$SITE" ]] && ! cmp -s "$SITE" "$ROOT/deployment/nginx-http.conf" && ! cmp -s "$SITE" "$ROOT/deployment/nginx-https.conf"; then
 echo 'Dedicated Nginx configuration has local changes; merge manually before rerunning.';exit 1
fi
if [[ -e "$LINK" && $(readlink -f "$LINK") != "$SITE" ]]; then echo 'Conflicting Nginx link; inspect before proceeding';exit 1;fi
if [[ ! -e "$SITE" ]] && nginx -T 2>/dev/null | grep -E 'server_name[[:space:]].*aff\.pramool\.bid' >/dev/null; then echo 'Hostname already configured elsewhere; inspect nginx -T';exit 1;fi
install -d /var/www/shopee-aff-acme/.well-known/acme-challenge
if [[ ! -f /etc/letsencrypt/live/aff.pramool.bid/fullchain.pem ]]; then
 cp "$ROOT/deployment/nginx-http.conf" "$SITE"
 ln -sfn "$SITE" "$LINK"
 nginx -t; systemctl reload nginx
 CHALLENGE=$(openssl rand -hex 24)
 printf '%s' "$CHALLENGE" > /var/www/shopee-aff-acme/.well-known/acme-challenge/studio-origin
 [[ $(curl --fail --silent http://aff.pramool.bid/.well-known/acme-challenge/studio-origin) = "$CHALLENGE" ]] || { echo 'DNS/proxy does not route to this origin; correct aff A record before TLS issuance';exit 1; }
 certbot certonly --webroot -w /var/www/shopee-aff-acme -d aff.pramool.bid --non-interactive --agree-tos --register-unsafely-without-email
fi
cp "$ROOT/deployment/nginx-https.conf" "$SITE"
ln -sfn "$SITE" "$LINK"
nginx -t; systemctl reload nginx
curl --retry 5 --retry-delay 2 --retry-all-errors --fail --silent --resolve aff.pramool.bid:443:127.0.0.1 https://aff.pramool.bid/api/health
