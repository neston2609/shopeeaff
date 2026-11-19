# ElevenLabs voice and Gemini access

The application now separates video generation from narration. Existing projects keep their previous behavior through `narration_provider=auto`.

## ElevenLabs

Open **AI / voice settings** and scroll to ElevenLabs. API keys are write-only and Fernet-encrypted with the server's existing external encryption key. The browser receives only configuration, sanitized provider status and a credential-revision digest. No API key is stored in source control, returned by an API, or logged.

**Verify key / load voices** makes read-only requests to the official ElevenLabs voices, models and subscription endpoints. This verifies account access and Thai model capability; it does not claim successful synthesized audio. Model availability and Thai language support come from the actual `/v1/models` response. The default is `eleven_v3`; Flash/Multilingual models must not be assumed to support Thai.

Choose an available voice and set a conservative USD-per-1,000-character estimate for your plan. This is a configurable application estimate; ElevenLabs meters credits and bills independently. Voice-library voices may have different rates, so review your account pricing.

The **real voice preview** uses a fixed 54-character Thai sample. It displays the estimate and requires an explicit approved USD limit and checkbox. Request IDs, recorded submission intent and cached results prevent automatic re-billing after a lost response or timeout. The generated MP3 is validated and served only to authenticated users. A read-only key check never sets the live-audio verification flag.

In Studio, select **ElevenLabs** as the narration provider and choose a voice. Speaking speed is limited to the supported 0.7–1.2 range. Request a new estimate, approve the total budget, create the project and start it. The narration cost is included in per-project, daily and monthly application limits even with local Mock video or imported Flow clips. Uploaded narration and silent mode remain available. Mock video remains visibly labeled as simulated even when its ElevenLabs narration is real.

Provider/key/voice changes invalidate quotes and are blocked while active paid jobs or previews are running. The worker records each TTS submission before making the request. It never automatically repeats an ambiguous paid request, reuses successful audio, and does not silently fall back to another provider. Audio exceeding the scene's eight seconds requires a shorter script; regeneration requires new approval.

## Gemini model and region

As of November 19, 2026, Google lists `gemini-2.5-flash` as retired on October 20, 2026. New configurations default to `gemini-3.8-flash` in the `us` multi-region. Gemini text requests use the separate `text_location`; Veo keeps its configured `location` (default `us-central1`). Existing saved model choices are retained until explicitly updated. No automatic paid fallback or retry is performed.

References: [Google lifecycle](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions), [Gemini 3.8 Flash regions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash).

## Gemini 403

ElevenLabs narration does not replace Gemini's script/storyboard generation or Veo's video generation. Successful Google TTS or model lookup does not prove permission to generate Gemini text.

In the authenticated Google settings panel, the app shows the project and service-account email, plus links to the relevant project's IAM and API pages. A Google Cloud project administrator should:

1. Enable `aiplatform.googleapis.com` in the selected project.
2. Grant the uploaded service account `roles/aiplatform.user` (Vertex AI User), or an appropriate custom role including `aiplatform.endpoints.predict`.
3. Check project billing and any organization policy affecting prediction.
4. Enable `cloudresourcemanager.googleapis.com` if IAM diagnostics are desired. Optional metadata-reading access includes `serviceusage.services.get` and `serviceusage.quotas.get`; unavailable metadata does not itself prove that generation is denied.
5. Rerun the explicitly approved live Gemini check after access is corrected.

For a project administrator's Cloud Shell (replace placeholders; these commands modify IAM and service enablement):

```bash
gcloud services enable aiplatform.googleapis.com cloudresourcemanager.googleapis.com --project=PROJECT_ID
gcloud projects add-iam-policy-binding PROJECT_ID --member=serviceAccount:SERVICE_ACCOUNT_EMAIL --role=roles/aiplatform.user
```

VPS administrator access does not confer Google project administrator privileges. The application cannot elevate a restricted service account's own IAM permissions. Structured Google error reasons, service names and permission names are whitelisted before display; raw provider error messages and credentials remain private.

## Verification

Tests cover encrypted key handling, read-only verification, safe errors, quotes for local-video/paid-audio combinations, stale key/voice rejection, request idempotency, credit/quota failures, ambiguous submission blocking, private preview downloads, and FFmpeg composition with an isolated voice adapter. Test doubles never represent successful live provider verification.

Official references: [speech conversion API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert), [voice list](https://elevenlabs.io/docs/api-reference/voices/search), [ElevenLabs models](https://elevenlabs.io/docs/overview/models), [Google access control](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/access-control).
