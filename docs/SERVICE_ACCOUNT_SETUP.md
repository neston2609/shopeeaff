# Service Account

Follow [Google Cloud setup](GOOGLE_CLOUD_SETUP.md). JSON uploads are validated for service-account structure, Google token URL and parseable private key. They are then encrypted with Fernet using the server's external environment key. Private keys are never returned to the browser. The UI reveals only project, account email and status. Test Connection is required to validate authentication/API permissions. Real generation requires separate cost approval.

Keep the encryption key with encrypted disaster recovery configuration. Rotating it requires re-encrypting credentials or re-uploading the service-account JSON. Rotate Google keys through IAM and promptly replace the application's credential.
