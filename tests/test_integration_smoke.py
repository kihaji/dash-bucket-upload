"""Browser smoke test: drive a real file through the component with selenium.

Gated behind BUCKET_UPLOAD_BROWSER_TESTS=1 (needs Chrome + chromedriver).
Uses relay mode against a moto server so no bucket CORS setup is required —
the browser only ever talks to the Dash origin.
"""
import json
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get('BUCKET_UPLOAD_BROWSER_TESTS') != '1',
    reason = 'browser smoke tests are opt-in: set BUCKET_UPLOAD_BROWSER_TESTS=1',
)


def test_upload_via_browser(dash_duo, s3, moto_endpoint, tmp_path):
    from dash import Dash, Input, Output, html

    from dash_bucket_upload import BucketUpload, BucketUploadManager

    from .conftest import ACCESS_KEY, BUCKET, REGION, SECRET_KEY

    app = Dash(__name__)
    mgr = BucketUploadManager(
        app,
        endpoint_url = moto_endpoint,
        region_name = REGION,
        aws_access_key_id = ACCESS_KEY,
        aws_secret_access_key = SECRET_KEY,
        bucket = BUCKET,
        prefix = 'smoke',
        mode = 'relay',
    )
    app.layout = html.Div([
        BucketUpload(id = 'up', manager = mgr),
        html.Pre(id = 'out'),
    ])

    @app.callback(Output('out', 'children'), Input('up', 'lastUploadedBatch'))
    def show(batch):
        return json.dumps(batch) if batch else 'none'

    dash_duo.start_server(app)

    payload = os.urandom(256 * 1024)
    test_file = tmp_path / 'smoke test.bin'
    test_file.write_bytes(payload)

    file_input = dash_duo.driver.find_element('css selector', '#up input[type=file]')
    file_input.send_keys(str(test_file))

    dash_duo.wait_for_contains_text('#out', 'smoke test.bin', timeout = 30)
    batch = json.loads(dash_duo.find_element('#out').text)
    assert len(batch) == 1
    assert batch[0]['filename'] == 'smoke test.bin'
    assert batch[0]['size'] == len(payload)
    assert batch[0]['status'] == 'done'

    stored = s3.get_object(Bucket = BUCKET, Key = batch[0]['key'])['Body'].read()
    assert stored == payload
