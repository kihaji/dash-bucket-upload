"""Resetting the widget as part of an app-wide "start over": a small dataset
submission form whose button clears the text fields, the upload list, and the
component's outputs in one callback. Uploaded objects stay in the bucket.

Start MinIO first:
    docker compose -f examples/docker-compose.minio.yml up -d
Then:
    uv run python examples/reset.py
"""
import json

from dash import Dash, Input, Output, State, dcc, html

from dash_bucket_upload import BucketUpload, BucketUploadManager

app = Dash(__name__)

mgr = BucketUploadManager(
    app,
    endpoint_url = 'http://localhost:9000',
    region = 'us-east-1',
    access_key = 'minioadmin',
    secret_key = 'minioadmin',
    bucket = 'uploads',
    prefix = 'submissions',
    mode = 'direct',
)

app.layout = html.Div(
    [
        html.H3('Dataset submission'),
        dcc.Input(id = 'title', placeholder = 'Dataset title', style = {'width': '100%', 'marginBottom': '8px'}),
        dcc.Textarea(id = 'notes', placeholder = 'Notes', style = {'width': '100%', 'height': '60px'}),
        BucketUpload(id = 'uploader', manager = mgr),
        html.Div(
            [
                html.Button('Submit', id = 'submit', disabled = True),
                html.Button('Start over', id = 'start-over', style = {'marginLeft': '8px'}),
            ],
            style = {'marginTop': '12px'},
        ),
        html.H4('Status'),
        html.Pre(id = 'status'),
    ],
    style = {'maxWidth': '700px', 'margin': '40px auto', 'fontFamily': 'sans-serif'},
)


@app.callback(
    Output('submit', 'disabled'),
    Input('title', 'value'),
    Input('uploader', 'uploadedFiles'),
    Input('uploader', 'isUploading'),
)
def can_submit(title, files, uploading):
    return not title or not files or bool(uploading)


@app.callback(
    Output('status', 'children'),
    Input('uploader', 'uploadedFiles'),
    Input('submit', 'n_clicks'),
    State('title', 'value'),
    State('notes', 'value'),
)
def show_status(files, n_submits, title, notes):
    # After a reset, uploadedFiles is None again and this shows the empty state.
    if not files:
        return 'No files uploaded yet.'
    summary = {'title': title, 'notes': notes, 'files': [f['key'] for f in files]}
    prefix = 'Submitted:\n' if n_submits else 'Ready to submit:\n'
    return prefix + json.dumps(summary, indent = 2)


@app.callback(
    Output('uploader', 'resetKey'),
    Output('title', 'value'),
    Output('notes', 'value'),
    Output('submit', 'n_clicks'),
    Input('start-over', 'n_clicks'),
    prevent_initial_call = True,
)
def start_over(_):
    # One callback resets the whole form. BucketUpload.reset() returns a new
    # token each call; the widget clears its file list and outputs (and
    # cancels anything still uploading) whenever resetKey changes. Objects that
    # already finished uploading are left in the bucket.
    return BucketUpload.reset(), None, None, None


if __name__ == '__main__':
    app.run(debug = True)
