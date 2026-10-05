# Changelog

## 0.1.1 (2026-10-05)

- Bucket errors are now logged on the `dash_bucket_upload.manager` logger with
  the store's full message (the browser still receives only the error code).
- Connection, TLS, timeout and credential failures now return a JSON error
  (`bucket request failed: <name>`, HTTP 502, or 504 for timeouts) instead of a
  bare 500 or a hung request that surfaced as a reverse-proxy 502.
- The bucket client now fails fast: 5 s connect timeout and at most 3 attempts.
  Override with `botocore_config`.
- Documentation site: https://kihaji.github.io/dash-bucket-upload/

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
