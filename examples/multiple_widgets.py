"""Two upload widgets with different buckets, prefixes, and transports on one
page, sharing a single manager.

Start MinIO first:
    docker compose -f examples/docker-compose.minio.yml up -d
Then:
    uv run python examples/multiple_widgets.py
"""
import json

from dash import Dash, Input, Output, html

from dash_bucket_upload import BucketUpload, BucketUploadManager

app = Dash(__name__)

mgr = BucketUploadManager(
    app,
    endpoint_url = 'http://localhost:9000',
    region = 'us-east-1',
    access_key = 'minioadmin',
    secret_key = 'minioadmin',
    bucket = 'uploads',
    prefix = 'incoming',
    mode = 'direct',
)
# Second widget: different bucket, relayed through the server, capped at 1 GB,
# CSV/parquet only.
mgr.register(
    'datasets',
    bucket = 'media',
    prefix = 'datasets',
    mode = 'relay',
    max_file_size = 1 * 1024**3,
    allowed_extensions = ['.csv', '.parquet'],
)

app.layout = html.Div(
    [
        html.H3('Any files → uploads/incoming (direct)'),
        BucketUpload(id = 'up-any', manager = mgr),
        html.H3('Datasets → media/datasets (relay, ≤1 GB, .csv/.parquet)'),
        BucketUpload(id = 'up-data', manager = mgr, upload_id = 'datasets'),
        html.H4('Results'),
        html.Pre(id = 'output'),
    ],
    style = {'maxWidth': '700px', 'margin': '40px auto', 'fontFamily': 'sans-serif'},
)


@app.callback(
    Output('output', 'children'),
    Input('up-any', 'uploadedFiles'),
    Input('up-data', 'uploadedFiles'),
)
def show_all(any_files, data_files):
    return json.dumps({'up-any': any_files or [], 'up-data': data_files or []}, indent = 2)


if __name__ == '__main__':
    app.run(debug = True)
