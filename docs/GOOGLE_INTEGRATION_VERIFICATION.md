# Google integration upgrade verification

The upgrade is deployed at https://aff.pramool.bid. Verification began 29 October and continued 30 October 2026 (Asia/Bangkok).

## Application checks

- **41 backend tests passed on the production Ubuntu host**, including the existing FFmpeg/Thai subtitle/MP4/ZIP regression and new Google SDK, approval, operation recovery and error-handling integration tests.
- Next.js production build and TypeScript checks passed. npm production audit reported zero known vulnerabilities.
- HTTPS, redirect, backend health and all three systemd services passed.
- A production backup was created before updating. Hash comparisons confirmed existing provider configuration, encrypted service-account JSON and defaults were unchanged.
- Integration tests use explicitly isolated SDK transports/doubles; their responses are never represented as real Google verification.
- The real SDK regression caught and now guards client lifetime: generation/submission/polling retain an open SDK client until the request finishes. SDK automatic billable submission retries remain disabled.

## Actual Google results

These were authenticated requests using the server's configured service account, with user approval for the small live text/audio checks:

| Check | Actual result |
| --- | --- |
| Service-account authentication | Passed: Google access-token refresh succeeded. |
| Gemini text generation | Failed: the fixed client reached Google and received HTTP **403 PERMISSION_DENIED**. No generated text is claimed. |
| Thai Cloud TTS | Passed: generated a real 26,496-byte Thai MP3 and validated its audio stream with FFprobe. |
| Read-only Gemini model lookup | Passed for the configured text model. Model metadata access does not imply text-generation permission. |
| Vertex service / IAM / quota metadata | Limited: read attempts returned HTTP 403 permission errors. These are labeled unavailable, not fabricated quota exhaustion or proof of Veo readiness. |
| Veo generation | **Not run and not verified.** No video generation spending approval was provided during upgrade testing. |

The two earlier Gemini failures happened locally because the SDK client was closed before sending HTTP. After fixing client lifetime, the authorized request reached Google and reported the real 403. No successful live Gemini result was fabricated. TTS was not repeated during Gemini diagnostics.

## Remaining Google setup

Review the uploaded service account's Vertex AI access for the configured project. Check that Vertex AI API is enabled, the account has the relevant prediction permission (commonly through Vertex AI User), and organization policies/billing permit the request. The specific reason behind a 403 must be confirmed in the Google Cloud project; it is not inferred from successful TTS or model lookup.

Service Usage / Resource Manager metadata-reading permissions may be added if the operator wants quota and permission diagnostics. They are distinct from model-generation access. Use least privilege; do not grant project Owner/Editor simply to make metadata checks green.

After fixing access, explicitly approve and rerun Test Connection. Only a user-approved Studio video whose real Veo operation completes and whose downloaded video validates can set the separate **Veo live generation verified** status.
