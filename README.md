# Shopee Aff AI Studio

Thai-first affiliate video workspace. Next.js/TypeScript frontend, FastAPI/SQLAlchemy backend, SQLite durable queue, independent Python worker, official Google Gen AI / Google Cloud TTS SDKs and FFmpeg.

## Run locally

See [Windows](docs/INSTALL_WINDOWS.md) or [Linux](docs/INSTALL_LINUX.md). Production instructions are in [PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md).

## Workflow

1. Sign in using an administrator account initialized on the server.
2. Add product facts and preserve the original Shopee affiliate URL. In Add New Product, Fetch Information can populate available public JSON-LD/Open Graph metadata; review all fields before saving. JavaScript-only or blocked Shopee pages require manual entry or future authorized API integration. Authorized Shopee API credentials have not been supplied, so URL import opens the manual editor; no scraping or CAPTCHA bypass occurs.
3. Upload authorized product photos. The first photo is the primary image; reorder and remove images in the editor, then save.
4. Open Studio; choose Mock, Google Veo, or manual Google Flow clips. Review duration, narration and Product Accuracy Mode.
5. For Mock/manual, generate and edit the Thai storyboard. For Google, Gemini creates the storyboard after approval. Approve the displayed estimated USD budget and create a draft.
6. Optionally upload narration or Flow scene clips to the draft; start generation. Jobs survive service restarts; successful clips are reused.
7. Review the completed video for product accuracy and factual claims. Edit captions, download MP4/ZIP, and publish manually. Save the published Shopee URL.

## Provider truthfulness

ElevenLabs narration is available independently of the video provider, with an encrypted API key, Thai-capable model/voice selection and explicit budget approval. See [ElevenLabs and Gemini access](docs/ELEVENLABS_AND_GEMINI.md).

Version 1.1 adds independent authenticated/live Gemini/live TTS/configuration checks, scoped Veo operation evidence, expiring Studio quotes and at-most-once paid submission. See [Google integration update](docs/GOOGLE_INTEGRATION_UPDATE.md) for approval semantics, API compatibility and opt-in real verification commands.

Mock generates a real labeled vertical MP4. Its default narration track is **silence**, not synthetic Thai speech. Upload your own narration or configure Google TTS for speech. Mock scripts are deterministic local templates. Google uses real authenticated Vertex AI requests; no fabricated API successes. Integration status remains **Implemented — Live Verification Required** until an authenticated generation completes. No paid generation is included in automated tests.

## Security and data

Signed-in users can change their password in **ตั้งค่าระบบ → เปลี่ยนรหัสผ่าน** using their current password and a new password of 14–128 characters. Successful changes revoke every session for that account and require a fresh sign-in. Password checks are limited to five attempts per 15-minute window. Sessions are bound to the actual signed-in user; older sessions without an identity binding must sign in again after this update.

For an administrator-initiated recovery on the server, load the production environment and run `python -m app.admin --username admin --reset --generate` from the backend directory with the application virtual environment. This deliberately resets the existing account, prints a generated password once to the operator's terminal, and revokes its sessions. Never put the generated password in source control or logs.

Argon2 passwords, opaque server-side expiring sessions, Secure/HttpOnly/SameSite cookies in production, session CSRF tokens, same-origin write validation, persistent login throttling, encrypted service account JSON, authenticated media, strict Shopee URL validation and validated uploads. The explicit Fetch Information action reads public HTML metadata from HTTPS Shopee links only, with public-IP validation, pinned TLS connections, restricted redirects, time/size limits and per-account throttling. It sends no account cookies, does not execute page JavaScript or call private Shopee APIs, and never fabricates data when a page is blocked or has no metadata. The original affiliate link and existing product data remain unchanged until the user reviews and saves the form. Product images still require manual upload. Production secrets and all runtime data are excluded from Git.

SQLAlchemy tables store users, sessions, durable jobs and provider operations. Typed JSON records store product facts/images, provider configuration, templates and settings; a job snapshot contains projects, analysis, storyboard scenes, captions, generated asset references, usage reservations and publication history. Alembic tracks schema revisions. SQLite WAL and a single process lock keep queue ownership explicit. Deployment uses one worker; concurrency beyond one is deliberately unsupported.

Costs are configurable **estimates**, not billing reconciliation. Daily rolling 24-hour and monthly rolling 31-day limits conservatively count reservations. Paid video submission intent is persisted before calling Google. An ambiguous submission is blocked for operator reconciliation rather than resubmitted. See Google setup documentation for pricing and IAM.

## Verification

`cd backend && python -m pytest tests -q` runs authentication, CSRF, products, image handling, URL restrictions, CSV, approvals, queue transitions, duplicate paid submission protection, storyboard and full FFmpeg tests (FFmpeg must be on PATH).

`cd frontend && npm ci && npm run build` verifies the production frontend.

## Operational limits

No automatic Shopee publishing. No unauthorized scraping. Google availability depends on account permissions, enabled services, billing, selected region and model. Subtitles use scene-level timing, not word-aligned transcription. Creative AI output always requires human product-accuracy review. Mock output and all live verification limits must remain visibly labeled.
