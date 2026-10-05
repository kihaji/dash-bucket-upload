# dash-bucket-upload

Large-file uploads for [Plotly Dash](https://dash.plotly.com/), stored in any
S3-compatible bucket (AWS S3, MinIO, Ceph, …).

A drop-in replacement for the `dcc.Upload` experience — drag-and-drop or file
picker, multiple files, per-file progress bars — that streams files into a
bucket with S3 multipart uploads instead of base64-encoding them through a
Dash callback (which adds ~33% overhead and falls over past a few hundred MB).
Handles multi-gigabyte files. Callbacks receive the bucket location and
metadata, never the file contents; end users see a normal upload widget and
nothing else.

- **Two transports, one API.** Files go either **direct** from the browser to
  the bucket via presigned multipart URLs (no bytes touch the Dash server), or
  are **relayed** through a streaming route on the Dash server (no bucket CORS
  or browser-to-bucket connectivity needed). Your callback code is identical
  in both modes.
- **Collision-free keys.** Objects are stored as
  `<prefix>/<uuid4>/<original-filename>` — original names preserved, no
  collisions.
- **Airgap-safe.** All JavaScript ships inside the wheel and is served locally
  by Dash. No CDN, no external assets, ever.
- **Robust engine.** Parallel part uploads, exponential-backoff retries,
  presigned-URL refresh on expiry, cancellation with server-side multipart
  abort, throttled progress reporting.

**Documentation: <https://kihaji.github.io/dash-bucket-upload/>** — guides,
full API reference, and [troubleshooting](https://kihaji.github.io/dash-bucket-upload/guide/troubleshooting/).

## Installation

```bash
pip install dash-bucket-upload      # or: uv add dash-bucket-upload
```

## Quickstart

```python
from dash import Dash, Input, Output, html
from dash_bucket_upload import BucketUpload, BucketUploadManager

app = Dash(__name__)

mgr = BucketUploadManager(
    app,
    endpoint_url = 'http://localhost:9000',   # any S3-compatible store; omit for AWS S3
    access_key = 'minioadmin',
    secret_key = 'minioadmin',
    region = 'us-east-1',
    bucket = 'uploads',
    prefix = 'incoming',
    mode = 'direct',                          # or 'relay'
)

app.layout = html.Div([
    BucketUpload(id = 'up', manager = mgr),
    html.Div(id = 'out'),
])

@app.callback(Output('out', 'children'), Input('up', 'lastUploadedBatch'))
def on_upload(batch):
    if not batch:
        return 'Nothing uploaded yet.'
    # batch: [{'bucket': ..., 'key': ..., 'filename': ..., 'size': ..., 'etag': ..., 'status': 'done'}]
    return f"Uploaded {len(batch)} file(s): " + ', '.join(f['key'] for f in batch)

if __name__ == '__main__':
    app.run(debug = True)
```

Try it locally with MinIO:

```bash
docker compose -f examples/docker-compose.minio.yml up -d
uv run python examples/direct_mode.py
```

## S3-compatible stores

The manager speaks the S3 protocol (via boto3 as a protocol library), not
"AWS": point `endpoint_url` at any S3-compatible store and pass its
access/secret key pair using the provider-neutral parameter names
(`access_key`, `secret_key`, `session_token`, `region`,
`addressing_style`). The boto3 spellings (`aws_access_key_id`, …) are
accepted as aliases. `bucket` is a Swift *container* / GCS *bucket* /
Ceph *bucket* — same concept everywhere.

| Store | Setup notes |
|---|---|
| AWS S3 | Omit `endpoint_url`; omit credentials to use the normal AWS chain (env vars, config files, instance/IRSA roles). |
| MinIO | `endpoint_url='http(s)://minio:9000'` + root or service-account keys. Path-style addressing is applied automatically. |
| Ceph RGW | `endpoint_url` at the RGW endpoint + S3 keys from `radosgw-admin user create`. |
| OpenStack Swift (s3api middleware) | `endpoint_url` at the Swift proxy's S3 endpoint; credentials are Keystone EC2-style: `openstack ec2 credentials create` → pass the resulting access/secret pair. `region` should match the Keystone region if SigV4 validation is strict (often `RegionOne`). Multipart uploads are backed by SLO segments and honor the same ≥5 MiB part rule. For direct mode, CORS lives on the container: `swift post uploads -H 'X-Container-Meta-Access-Control-Allow-Origin: https://your-app' -H 'X-Container-Meta-Access-Control-Expose-Headers: etag'`. |
| Anything else | If `mc`/`aws s3api` works against it, this does too. `addressing_style='virtual'` for stores behind wildcard DNS; `signature_version` and `botocore_config` are escape hatches for exotic setups. |

Relay mode is the lowest-friction path on stores where you can't (or don't
want to) configure CORS — the browser never talks to the store directly.

## Choosing a transport

| | `mode='direct'` | `mode='relay'` |
|---|---|---|
| Data path | browser → bucket | browser → Dash server → bucket |
| Dash server load | none (metadata only) | streams every byte (bounded memory) |
| Browser must reach bucket | yes | no |
| Bucket CORS required | yes (see below) | no |
| Best for | biggest files, many users | locked-down networks, no CORS control |

Both modes use S3 multipart uploads under the hood and never buffer whole
files in server memory.

## Multiple widgets, buckets, and limits

```python
mgr = BucketUploadManager(app, ..., bucket = 'uploads')      # registers 'default'
mgr.register('videos', bucket = 'media', prefix = 'video', mode = 'relay',
             max_file_size = 10 * 2**30, allowed_extensions = ['.mp4', '.mkv'])

BucketUpload(id = 'up1', manager = mgr)                       # -> uploads/
BucketUpload(id = 'up2', manager = mgr, upload_id = 'videos') # -> media/video/
```

Size/extension/MIME limits are enforced server-side; the component also
mirrors them client-side for instant feedback.

## Callback-facing props

| prop | fires | contents |
|---|---|---|
| `lastUploadedBatch` | once per completed drop/selection batch | the new files: `[{bucket, key, filename, size, etag, status}]` — **use this as your callback Input** |
| `uploadedFiles` | after each file | same shape, cumulative for the component's lifetime — useful as `State` |
| `isUploading` | on change | `True` while any file is in flight |
| `progress` | throttled (~4/s) | per-file `{filename, size, loaded, percent, speedBps, status}` for custom progress UI (set `show_file_list=False`) |
| `lastError` | on failure | `{filename, message, phase}` |

## Bucket CORS (direct mode only)

Direct mode PUTs parts from the browser straight to the bucket, so the bucket
must allow it — **including exposing the `ETag` response header**, without
which the browser cannot finish the multipart upload (the widget raises a
targeted error if this is missing).

AWS S3 (`aws s3api put-bucket-cors --bucket uploads --cors-configuration file://cors.json`):

```json
{
  "CORSRules": [{
    "AllowedOrigins": ["https://your-app.example.com"],
    "AllowedMethods": ["PUT", "GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }]
}
```

MinIO (`mc cors set local/uploads examples/minio-init/cors.xml`) — see
`examples/minio-init/cors.xml`; the example compose file applies it
automatically.

## Production checklist

- **Authentication.** The upload routes are open by default. Gate them:

  ```python
  from flask_login import current_user
  BucketUploadManager(app, ..., auth_check = lambda request: current_user.is_authenticated)
  ```

- **Limits.** Set `max_file_size`, and `allowed_extensions` /
  `allowed_mime_types` where applicable.
- **Abandoned uploads.** Add a bucket lifecycle rule aborting incomplete
  multipart uploads (browsers closed mid-upload leave invisible parts behind):
  see `examples/minio-init/lifecycle.json`; on AWS use
  `AbortIncompleteMultipartUpload` with `DaysAfterInitiation: 1`.
- **Reverse proxies (relay mode).** Every part travels as one request of up to
  the part size (16 MiB default, larger for huge files). Raise
  `client_max_body_size` (nginx) or equivalent accordingly, and keep Flask's
  `MAX_CONTENT_LENGTH` above the part size if your app sets one.
- **Credentials.** The browser never sees bucket credentials in either mode —
  direct mode uses short-lived presigned URLs (`presign_expiration`, default
  1h; the engine refreshes expired URLs automatically).

## How it works

1. The component POSTs `create` → the server validates, generates the
   collision-free key, starts an S3 multipart upload, and picks a part size
   (files are split so they always fit S3's 10,000-part limit; parts are
   `Blob.slice` views, so browser memory stays flat regardless of file size).
2. Parts upload in parallel (4 per file, 6 total by default) — via presigned
   URLs (direct) or the streaming `part` route (relay) — with retry and
   backoff.
3. `complete` finishes the multipart upload; the server reads the final size
   from the bucket and the component fires your callback.

Cancel buttons, unmount, and failures all abort the S3 multipart upload
server-side.

## Development

Requires Python ≥ 3.12, Node ≥ 20, [uv](https://docs.astral.sh/uv/).

```bash
npm install            # JS toolchain
npm run build          # webpack bundle + regenerate the Dash component classes
uv sync                # Python env (.venv)
npm test               # vitest (JS engine)
uv run pytest          # Python suite (moto-backed, no Docker needed)
make quality           # ruff + pyright
make docs-serve        # live-reloading docs site at http://127.0.0.1:8000
```

The wheel is self-building: `uv build` compiles the JS bundle via a hatchling
hook, so the bundle is never committed to git.

## License

MIT
