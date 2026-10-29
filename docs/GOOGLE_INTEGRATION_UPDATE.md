# Google integration and Studio approval — version 1.1

## Connection verification

Service-account JSON remains Fernet-encrypted in SQLite with its encryption key outside the repository. Upload accepts only Google service-account credentials with the official OAuth token URI and Google API universe. No private keys, OAuth tokens, raw provider exception bodies or credentials are returned or logged.

Test Connection requires an explicit checkbox acknowledging the small live Gemini/TTS requests. It reports four independent results:

1. **Authentication:** refresh the service-account/ADC credential with Google.
2. **Gemini:** submit a real short text-generation request to the configured text model and require nonempty generated text.
3. **TTS:** synthesize a short Thai MP3, validate its audio stream and expose a private authenticated preview.
4. **Vertex configuration:** check enabled service state, project IAM testIamPermissions and visible quota metadata through official Google APIs. Least-privilege accounts may not have metadata-reading permission; these fields explicitly report unavailable/limited rather than fabricating access or remaining quota. Quota metadata is bounded to one page, labeled when truncated, and is not a capacity reservation or a claim of current remaining usage.

A failure in text, audio or metadata does not hide the other checks. Authentication failure skips API calls. Network timeouts are bounded; raw provider errors are mapped to safe authentication/permission/quota/billing/model/timeout/service categories.

**Veo status is separate.** Only a completed real Veo long-running operation whose downloaded video passes FFprobe validation records live verification. Evidence contains operation ID, job ID and timestamp, scoped to project, model, region and credential revision. Subsequent connection tests preserve matching evidence. Changing model, region or credentials requires new video evidence. Historical unscoped status strings cannot prove a current live generation.

## Spending approval

The existing configured model/region are preserved. Defaults remain `veo-3.1-fast-generate-001` and `us-central1`; other Veo model IDs and regions can be configured, with availability verified through the real provider response.

Studio requests a server-side quote showing per-scene video cost, total video estimate, Gemini/TTS reserves, model, region and pricing verification note. Quotes expire after 15 minutes and bind product, storyboard/settings and provider/credential revision. The user must explicitly approve a sufficient USD limit. Changing inputs invalidates the displayed approval; the server independently rejects expired, modified or reused quotes.

**Approval is an application control for estimated spending. It does not enable Cloud Billing, purchase quota, guarantee capacity, or guarantee the actual Google invoice.** Google billing and quota enforcement remain independent. Pricing is configurable and remains labeled as an estimate.

Project creation uses a stable client request ID and a transactional idempotency record. A retry returns the original project without reserving another budget or adding another queued job. Successfully created projects can still be edited, started, cancelled and inspected through the existing job UI. Existing products, media, credentials, defaults and projects are preserved; no schema replacement or data reset is required. Legacy approved projects retain their existing approval checks; new Google projects require a quote.

## Billable submission and recovery

The worker stores submission intent before the official SDK call and disables the SDK's default automatic retries (`HttpRetryOptions(attempts=1)`). After receiving an operation ID, it persists it before polling. Polling can retry transient errors without another video submission. Output downloads use a temporary file and atomic rename after validation.

A timeout or disconnect during submission can mean Google already accepted the request. Such an operation is marked **submission_uncertain** and automatic re-submission is blocked. Known rejected requests and terminal failed operations also require deliberate new approval rather than silent resubmission. Inspect the Google operation/billing console before generating again. Existing operation IDs are reused after worker restarts and failed downloads.

Job details show operation IDs/states and actionable safe error categories. Validated output continues through the existing narration/subtitles/composition/export pipeline and appears in the media library.

## API changes

- `POST /api/settings/test`: `{ "approve_live_checks": true, "request_id": "unique-client-request-id" }`. Reuse the same request ID if a response is lost; it will not repeat paid checks. Completed partial results return HTTP 200 with individual statuses; inspect every check, not just HTTP status.
- `GET /api/settings/tests/{test_id}/audio`: authenticated preview only.
- `POST /api/estimate`: same project input as before, now returns `quote_id`, `expires_at` and a cost breakdown.
- `POST /api/jobs`: new Google projects require `quote_id`, stable `request_id`, `approved=true` and sufficient `approved_budget`. Existing Mock/manual workflow remains usable.
- `GET /api/settings` and job responses include separate verification evidence and provider operations.

## Tests and live verification

`cd backend && python -m pytest tests -q` runs regression and Google workflow integration tests using explicitly isolated SDK test doubles. These tests never represent actual live Google success and do not use the production database, even if DATABASE_URL was inherited. The FFmpeg regression requires FFmpeg/FFprobe on PATH.

For **actual** authenticated verification, use the web UI after approving live checks, or load the production environment and run:

```bash
cd /app/shopeeaff
# Runs real, potentially billable short Gemini and TTS checks; no Veo request.
.venv/bin/python scripts/check_google_live.py --approve-text-audio --request-id UNIQUE_REQUEST_ID
```

Only after deliberately approving a video budget:

```bash
.venv/bin/python scripts/check_google_live.py --approve-text-audio --request-id ANOTHER_UNIQUE_ID --product-id EXISTING_PRODUCT_ID --approved-veo-budget APPROVED_USD_LIMIT
```

The dedicated worker must be running. The optional video command creates a real 15-second project made of supported 8-second scenes; it stops without submission if the approved limit is insufficient. Retain request IDs for safe retries. Do not use these opt-in commands as unattended health checks.

Official references: [Google Gen AI SDK](https://github.com/googleapis/python-genai), [Veo image-to-video](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/googlegenaisdk-videogen-with-img), [TTS](https://docs.cloud.google.com/text-to-speech/docs/create-audio-text-client-libraries), [quota metadata](https://docs.cloud.google.com/service-usage/docs/reference/rest/v1beta1/services.consumerQuotaMetrics/list), [project permission checks](https://docs.cloud.google.com/resource-manager/reference/rest/v1/projects/testIamPermissions).
