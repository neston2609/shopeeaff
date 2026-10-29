# Production deployment — aff.pramool.bid

Code: `/app/shopeeaff`. Persistent database/media: `/var/lib/shopee-aff-ai-studio`. Secrets: `/etc/shopee-aff-ai-studio/production.env` (root:shopeeaff, 0640). Services run as non-login user `shopeeaff`. Journal contains service logs. Existing Nginx sites must be preserved.

## Install

Requires Ubuntu 24.04/Debian, Node 20+, Python 3.12-compatible, sudo and DNS pointing to the VPS (directly or through Cloudflare).

```bash
cd /app/shopeeaff
sudo bash scripts/deploy_production.sh
```

This installs supported apt dependencies, Python venv dependencies, locked Node dependencies, builds Next, migrates SQLite and installs three services and backup timer. It generates secrets once, preserves data and does not overwrite other hosts. Frontend binds 127.0.0.1:3100; backend binds 127.0.0.1:8100 because 3000/8000 are occupied on this VPS. Do not expose either port publicly. Preserve SSH and existing unrelated firewall rules; allow 80/443 for web traffic.

The installer now invokes `scripts/configure_https.sh` and the public readiness check by default. Set `CONFIGURE_HTTPS=0` only when deliberately preparing services before DNS is ready. The helper verifies origin routing before initial certificate issuance and refuses to overwrite a locally modified or conflicting dedicated host.

## Dedicated Nginx host and TLS

First inspect `sudo nginx -T`. If no `aff.pramool.bid` site already exists:

```bash
sudo install -d /var/www/shopee-aff-acme
sudo cp deployment/nginx-http.conf /etc/nginx/sites-available/shopeeaff
sudo ln -s /etc/nginx/sites-available/shopeeaff /etc/nginx/sites-enabled/shopeeaff
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/shopee-aff-acme -d aff.pramool.bid --non-interactive --agree-tos --register-unsafely-without-email
```

Use the repository's `deployment/nginx-https.conf` after certificate issuance. Its HTTP block preserves ACME renewal and redirects to HTTPS. Cloudflare origin mode should be Full (strict). Do not disable verification. Cloudflare A-record answers are proxy addresses, so verify origin routing using an ACME challenge and `curl --resolve aff.pramool.bid:443:103.40.118.129 https://aff.pramool.bid/api/health` as well as public HTTPS.

## Initial administrator

No default password is shipped. Create an account interactively:

```bash
cd /app/shopeeaff/backend
sudo bash -c 'set -a; source /etc/shopee-aff-ai-studio/production.env; set +a; sudo -E -u shopeeaff /app/shopeeaff/.venv/bin/python -m app.admin --username admin'
```

The deployment operator can generate a random password using `--generate`, retaining it in a root-only file. Never commit it or reuse the VPS password as the application password.

## Operate

```bash
sudo systemctl status shopee-aff-{frontend,backend,worker}
sudo systemctl restart shopee-aff-{frontend,backend,worker}
sudo systemctl stop shopee-aff-{frontend,backend,worker}
sudo systemctl start shopee-aff-{frontend,backend,worker}
sudo journalctl -u shopee-aff-worker -n 100 --no-pager
sudo bash /app/shopeeaff/scripts/check_production.sh
sudo bash /app/shopeeaff/scripts/backup_production.sh
sudo systemctl list-timers shopee-aff-backup.timer
```

Update with `sudo bash scripts/update_production.sh` after configuring read-only Git access for the deployment account. It backs up first, pulls fast-forward, installs/builds/migrates, restarts and checks HTTPS. Avoid uploading or deleting production runtime data during updates.

## Backup and recovery

Daily backups at 03:15 server local time (+ random delay), with 14-day retention, are stored root-only in `/var/backups/shopee-aff-ai-studio`. Backend/worker stop briefly for a consistent snapshot of database and media; SQLite's online backup API creates the database copy. Secrets are excluded; preserve the environment/encryption key separately in encrypted off-server storage. An encrypted credential database is unusable without its original encryption key.

```bash
sudo bash scripts/restore_production.sh /var/backups/shopee-aff-ai-studio/backup-TIMESTAMP.tar.gz
```

Restore verifies database integrity, takes a pre-restore backup and preserves the existing data directory under a timestamp before installing restored data. Verify login, product image, MP4 download and worker status after recovery. Keep a matching code revision for the schema you restore.

## Paid operation recovery

Queued/running jobs and operation IDs persist in SQLite. Restarting a worker polls an existing video operation instead of paying again. An intent with no operation ID means the process may have crashed between submission and persistence. Do not delete the operation or click generate again until the Google console confirms whether it was submitted. Reconcile the operation ID in `provider_operations` using an administrative SQLite transaction, with services stopped and a prior backup. Then resume. Billing reconciliation itself is manual.

## Acceptance checks

Run pytest on the VPS, then public HTTPS checks, administrator login, create a sample product, upload image, generate Mock MP4, download ZIP, FFprobe dimensions/duration, service restart, and check product/job persistence. Google real generation requires customer credentials and explicit paid approval; never equate mock success with Google verification.
