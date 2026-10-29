# Production verification — 29 October 2026

Production: https://aff.pramool.bid on 103.40.118.129, source at https://github.com/neston2609/shopeeaff, code in /app/shopeeaff.

Verified results:

- Next.js production build and TypeScript check passed.
- npm audit reports zero known production dependency vulnerabilities.
- **12 backend tests passed on Ubuntu**, including the full FFmpeg workflow.
- Public HTTPS homepage and backend health responded successfully; HTTP redirects to HTTPS.
- Origin certificate validates with Let's Encrypt issuer, expiring 27 January 2027; automated renewal is installed.
- Frontend, backend and dedicated worker run as separate systemd services with boot enablement.
- Ports 3100 and 8100 listen only on 127.0.0.1. Existing Nginx hosts remain configured.
- Public authenticated smoke test created a product, preserved affiliate URL, uploaded an image, created a Thai storyboard and durable job, generated a real mock MP4, and downloaded the ZIP.
- Final smoke output: 1080×1920, 15.0 seconds, 574114 bytes; ZIP 530343 bytes. Job ID `7b083e9551a44dc0b59bc2dd00c8dd7c7`.
- Unauthenticated media download was rejected with 401.
- Product, session and completed job survived restart of all three services.
- Browser login, responsive navigation, content library, video preview and export actions were inspected.
- Consistent backup created; extracted backup database passed SQLite integrity_check. Daily backup timer is enabled with 14-day retention.

The tests cover CSRF/origin rejection, authentication, product/image/CSV handling, unsafe URL/image identifiers, Google credential parsing/encryption, truthful API verification status, provider submission parameters, cost approval/limits, atomic job claims, recovery, ambiguous paid request protection, archival/restore, defaults, captions/publication recording, MP4 validation and ZIP packaging.

## External verification still required

**No live Google generation was run.** No Google service-account credentials were provided. Veo, Gemini and Thai TTS adapters use official Google SDKs and are implemented, but project-specific IAM, billing, region/model availability, Google video output and Google voice output require the user's authenticated test. The UI explicitly reports this status. No paid generation was authorized or submitted during verification.

Mock narration defaults to silence unless narration is uploaded. No claim of synthesized Thai speech is made for Mock mode. Authorized Shopee API access was not provided; manual/CSV product import and image upload are the supported production import paths. No scraping or automatic Shopee publishing is implemented.

Scene/voice regeneration creates a new approved project, reusing successful existing clips where applicable. It conservatively reserves the full estimate again. Actual cloud billing is reconciled manually. Subtitle timing is phrase/scene based and editable through advanced storyboard JSON, not forced word alignment. Product accuracy remains a human review responsibility.

Optional Gemini Developer API-key authentication is not included; the primary integration is Google Cloud Service Account or ADC. Generation concurrency is deliberately one dedicated worker on this VPS. Backups exclude plaintext production secrets; preserve the encryption key separately in encrypted off-server storage.
