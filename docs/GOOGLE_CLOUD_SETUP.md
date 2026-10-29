# Google Cloud setup

1. Create/select a Google Cloud project and enable billing.
2. Enable `aiplatform.googleapis.com`, `texttospeech.googleapis.com`, and `storage.googleapis.com` if using GCS output.
3. Create a dedicated service account. Grant Vertex AI User and the documented permission to synthesize speech. On a dedicated private GCS bucket, grant only required object read/create permissions (for example Storage Object User scoped to that bucket); avoid project Owner/Editor.
4. Create a JSON key only if your organization's policy permits it; otherwise use Application Default Credentials attached to the VPS runtime. Protect and rotate keys.
5. Sign in to this application, open Google Cloud AI, upload JSON, check project ID, region and model, then save.
6. Select a currently supported Veo model: `veo-3.1-fast-generate-001` or `veo-3.1-generate-001`. The default region is `us-central1`; validate your project/model access. Gemini text model is configurable. Optional GCS bucket is its bare name.
7. Configure conservative USD video/second, text reserve and TTS/character estimates and record the pricing verification date. Defaults are estimates, **not verified current pricing**. Set daily/monthly/per-video limits before live use.
8. Test Connection requires approval for small live Gemini/TTS checks. It independently checks credential refresh, actual generated text, actual synthesized Thai audio and available Vertex API/IAM/quota metadata. Authentication or metadata alone never marks Veo generation verified. See [version 1.1 details](GOOGLE_INTEGRATION_UPDATE.md).
9. Generate Test Video opens the normal paid Studio workflow. Select a product/photo, check the estimate, enter the approved budget, explicitly approve, create and start the project. No paid API request is made before this approval.
10. Watch job status. Successful Google output is downloaded from inline video bytes or authenticated GCS storage, validated by FFprobe and composed. Only a completed live project sets Live Generation Tested.

Thai TTS voices come from the connection test. Do not assume a male/female voice exists under an invented name. Enter a supported returned voice name. Uploaded narration is a provider-independent alternative.

Official implementation references:

- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/googlegenaisdk-videogen-with-img
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos-from-an-image
- https://github.com/googleapis/python-genai
- https://docs.cloud.google.com/text-to-speech/docs/create-audio-text-client-libraries
- https://cloud.google.com/vertex-ai/generative-ai/pricing

Veo scenes are generated as 8-second 9:16 clips at 720p; final composition trims to 15/20/30/45/60 seconds and can scale to 1080×1920. Upscaling does not create additional native detail. Image accuracy uses the supplied primary reference image; human review is still necessary. This adapter does not claim guaranteed preservation of branding.
