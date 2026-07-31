# Changelog

## 0.1.0 (unreleased)

Initial release.

- `BucketUpload` component: dcc.Upload-style drop zone with per-file progress,
  speed, and cancel; multiple files; several-GB file support via S3 multipart
  uploads with parallel parts, retry/backoff, and abort-on-cancel.
- `BucketUploadManager`: registers the server routes, holds per-widget configs
  (bucket/prefix/mode/limits), works with any S3-compatible endpoint via boto3.
- Direct mode (browser → bucket via presigned URLs) and relay mode
  (browser → Dash server → bucket, streaming, bounded memory).
- Collision-free object keys: `<prefix>/<uuid4>/<original-filename>`.
- Server-side validation (size, extension, MIME), optional `auth_check` hook.
- Airgapped-friendly: all JS bundled in the wheel and served locally.
