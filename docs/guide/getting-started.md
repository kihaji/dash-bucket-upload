# Getting started

## Install

Requires Python 3.12 or newer and Dash 3 or 4.

=== "pip"

    ```bash
    pip install dash-bucket-upload
    ```

=== "uv"

    ```bash
    uv add dash-bucket-upload
    ```

The wheel contains the compiled JavaScript. No Node.js is needed to use the
package.

## Run a local bucket

The repository ships a MinIO setup for development. It creates two buckets
(`uploads` and `media`), applies the CORS rules direct mode needs, and adds a
lifecycle rule that cleans up abandoned multipart uploads.

```bash
docker compose -f examples/docker-compose.minio.yml up -d
```

The MinIO console is at <http://localhost:9001> (user `minioadmin`, password
`minioadmin`).

## A minimal app

```python
from dash import Dash, Input, Output, html
from dash_bucket_upload import BucketUpload, BucketUploadManager

app = Dash(__name__)

# 1. One manager per app: it registers the upload routes on the Flask server
#    and holds the bucket connection.
mgr = BucketUploadManager(
    app,
    endpoint_url = 'http://localhost:9000',   # omit for AWS S3
    access_key = 'minioadmin',
    secret_key = 'minioadmin',
    region = 'us-east-1',
    bucket = 'uploads',
    prefix = 'incoming',
    mode = 'direct',                          # or 'relay'
)

# 2. The component finds the routes and limits through manager=.
app.layout = html.Div([
    BucketUpload(id = 'up', manager = mgr),
    html.Div(id = 'out'),
])

# 3. React to finished uploads. The callback gets metadata, never file bytes.
@app.callback(Output('out', 'children'), Input('up', 'lastUploadedBatch'))
def on_upload(batch):
    if not batch:
        return 'Nothing uploaded yet.'
    return f"Uploaded {len(batch)} file(s): " + ', '.join(f['key'] for f in batch)

if __name__ == '__main__':
    app.run(debug = True)
```

Drop a file on the widget. When the whole batch has finished,
`lastUploadedBatch` fires with one entry per successful file:

```python
[
    {
        'bucket': 'uploads',
        'key': 'incoming/3f2b9c1e-8d4a-4f7e-9b0c-2a1d5e6f7a8b/report.pdf',
        'filename': 'report.pdf',
        'size': 48213977,          # read back from the bucket, not trusted from the browser
        'etag': '"9b2cf535f27731c974343645a3985328-3"',
        'status': 'done',
    },
]
```

## Do something with the file

The callback runs on the server, which already has bucket access. Use any S3
client to read the object. For example, with the manager's own credentials:

```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url = 'http://localhost:9000',
    aws_access_key_id = 'minioadmin',
    aws_secret_access_key = 'minioadmin',
    region_name = 'us-east-1',
)

@app.callback(Output('out', 'children'), Input('up', 'lastUploadedBatch'), prevent_initial_call = True)
def on_upload(batch):
    lines = []
    for f in batch:
        obj = s3.get_object(Bucket = f['bucket'], Key = f['key'])
        first_line = obj['Body'].read(200).split(b'\n', 1)[0]   # stream; don't .read() a 5 GB file
        lines.append(f"{f['filename']}: {first_line!r}")
    return html.Pre('\n'.join(lines))
```

!!! tip "Long-running processing"
    Dash callbacks hold a request open. For work that takes more than a few
    seconds (parsing a multi-GB file, transcoding), hand the bucket key to a
    background job ([Dash background callbacks](https://dash.plotly.com/background-callbacks),
    Celery, a queue) and return immediately.

## Example apps

The `examples/` directory in the repository has runnable apps:

| File | Shows |
|---|---|
| `examples/direct_mode.py` | Browser uploads straight to MinIO with presigned URLs |
| `examples/relay_mode.py` | Parts relayed through the Dash server |
| `examples/multiple_widgets.py` | Two widgets with different buckets, transports and limits |
| `examples/reset.py` | A form whose "Start over" button resets the widget along with the rest of the app |

```bash
uv run python examples/direct_mode.py
```

## Next steps

- Decide between [direct and relay mode](transports.md).
- Connect to your [S3-compatible store](stores.md).
- Learn every [callback output](callbacks.md).
