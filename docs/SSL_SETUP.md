# TLS

See the dedicated Nginx/Certbot procedure in [Production deployment](PRODUCTION_DEPLOYMENT.md). Certificate files are in `/etc/letsencrypt/live/aff.pramool.bid/`. Certbot's existing system timer handles renewal. Test with `sudo certbot renew --dry-run --cert-name aff.pramool.bid`. Validate public HTTPS without `-k`; validate the origin with curl's `--resolve` flag. Preserve unrelated hosts and certificates.
