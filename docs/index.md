# dash-bucket-upload

Large-file uploads for [Plotly Dash](https://dash.plotly.com/), stored in any
S3-compatible bucket: AWS S3, MinIO, Ceph RGW, OpenStack Swift and others.

`BucketUpload` looks and behaves like `dcc.Upload`: drag-and-drop or file
picker, multiple files, per-file progress bars. Instead of base64-encoding file
contents into a Dash callback (about 33% overhead, and unusable past a few
hundred MB), it streams files into a bucket with S3 multipart uploads. Files of
many gigabytes work. Your callbacks receive the bucket location and metadata,
never the file bytes.

```python
from dash import Dash, Input, Output, html
from dash_bucket_upload import BucketUpload, BucketUploadManager

app = Dash(__name__)
mgr = BucketUploadManager(
    app,
    endpoint_url = 'http://localhost:9000',
    access_key = 'minioadmin',
    secret_key = 'minioadmin',
    bucket = 'uploads',
)

app.layout = html.Div([BucketUpload(id = 'up', manager = mgr), html.Pre(id = 'out')])

@app.callback(Output('out', 'children'), Input('up', 'lastUploadedBatch'))
def on_upload(batch):
    return '\n'.join(f"s3://{f['bucket']}/{f['key']}" for f in batch or [])
```

## Features

Two transports, one API
:   Files go either **direct** from the browser to the bucket through presigned
    multipart URLs, so no bytes touch the Dash server, or are **relayed**
    through a streaming route on the Dash server, which needs no bucket CORS and
    no browser-to-bucket connectivity. Callback code is identical in both modes.
    See [Choosing a transport](guide/transports.md).

Collision-free keys
:   Objects are stored as `<prefix>/<uuid4>/<original-filename>`, so original
    names are preserved and two uploads never overwrite each other.

Airgap-safe
:   All JavaScript ships inside the wheel and is served locally by Dash. No CDN
    and no external assets.

Robust engine
:   Parallel part uploads, exponential-backoff retries, presigned-URL refresh on
    expiry, cancellation with server-side multipart abort, and throttled
    progress reporting. Browser memory stays flat regardless of file size.

Stateless server
:   The routes keep no in-memory upload state, so the widget works unchanged
    under multi-worker servers such as gunicorn.

## Where to go next

- **New here?** Start with [Getting started](guide/getting-started.md).
- **Deploying?** Read [Production deployment](guide/production.md) and keep
  [Troubleshooting](guide/troubleshooting.md) handy.
- **Looking up a parameter?** See the [Python API](reference/python.md) and
  [Component props](reference/component-props.md).
