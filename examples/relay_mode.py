"""Relay-mode demo: file parts are PUT to the Dash server, which streams them
into the bucket — for deployments where the browser cannot reach the bucket
(no CORS setup needed).

Start MinIO first:
    docker compose -f examples/docker-compose.minio.yml up -d
Then:
    uv run python examples/relay_mode.py
"""
import json

from dash import Dash, Input, Output, html

from dash_bucket_upload import BucketUpload, BucketUploadManager

app = Dash(__name__)

mgr = BucketUploadManager(
    app,
    endpoint_url = 'http://localhost:9000',
    region_name = 'us-east-1',
    aws_access_key_id = 'minioadmin',
    aws_secret_access_key = 'minioadmin',
    bucket = 'uploads',
    prefix = 'relayed',
    mode = 'relay',
)

app.layout = html.Div(
    [
        html.H3('dash-bucket-upload: relay mode'),
        BucketUpload(id = 'uploader', manager = mgr),
        html.H4('Last completed batch'),
        html.Pre(id = 'output'),
    ],
    style = {'maxWidth': '700px', 'margin': '40px auto', 'fontFamily': 'sans-serif'},
)


@app.callback(Output('output', 'children'), Input('uploader', 'lastUploadedBatch'))
def show_batch(batch):
    if not batch:
        return 'Nothing uploaded yet.'
    return json.dumps(batch, indent = 2)


if __name__ == '__main__':
    app.run(debug = True)
