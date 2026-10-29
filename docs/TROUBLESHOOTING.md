# Troubleshooting

- **502:** check all three systemd services and journal; ensure ports 3100/8100 are free and the Nginx hostname is correct.
- **Cloudflare 525/526:** obtain a valid origin certificate and verify it with `curl --resolve`; do not bypass TLS verification.
- **403 on write:** reload/sign in again for CSRF token; origin must match APP_URL exactly. Browser API calls use same-origin `/api`.
- **401:** session expired (12h); sign in again. There is no public registration.
- **429:** login is limited to 10 attempts per origin IP per 15-minute window.
- **Worker offline:** inspect `journalctl -u shopee-aff-worker`; check storage permissions and FFmpeg installation. Only one worker is supported.
- **Font missing:** install `fonts-noto-core`, run `fc-match 'Noto Sans Thai'`, regenerate output.
- **Google 403:** check billing, service enablement, service-account IAM, project and region. Test Connection must precede model testing. Model listing success is not Veo entitlement proof.
- **Narration too long:** shorten the scene script or increase speaking speed before generating another approved project. Each scene is 8s; there is no claimed word-level alignment.
- **Ambiguous submission:** follow paid operation reconciliation in production documentation. Never automatically resubmit an intent without a known provider operation ID.
- **Disk pressure:** retain backups off-server and remove obsolete exports deliberately. Application updates preserve data.
- **URL import needs manual input:** this is expected without officially authorized Shopee API credentials. Affiliate URL is preserved exactly; no remote scraping occurs.
