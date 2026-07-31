"""Direct-to-bucket upload demo: the browser PUTs file parts straight to MinIO
via presigned URLs; only metadata reaches the Dash callback.

Start MinIO first:
    docker compose -f examples/docker-compose.minio.yml up -d
Then:
    uv run python examples/direct_mode.py
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

app.layout = html.Div(
    [
        html.H3('dash-bucket-upload: direct-to-bucket mode'),
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
