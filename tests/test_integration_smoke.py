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
        region = REGION,
        access_key = ACCESS_KEY,
        secret_key = SECRET_KEY,
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


def test_reset_clears_ui_but_keeps_uploaded_objects(dash_duo, s3, moto_endpoint, tmp_path):
    from dash import Dash, Input, Output, html

    from dash_bucket_upload import BucketUpload, BucketUploadManager

    from .conftest import ACCESS_KEY, BUCKET, REGION, SECRET_KEY

    app = Dash(__name__)
    mgr = BucketUploadManager(
        app,
        endpoint_url = moto_endpoint,
        region = REGION,
        access_key = ACCESS_KEY,
        secret_key = SECRET_KEY,
        bucket = BUCKET,
        prefix = 'smoke',
        mode = 'relay',
    )
    app.layout = html.Div([
        BucketUpload(id = 'up', manager = mgr),
        html.Button('Reset', id = 'reset'),
        html.Pre(id = 'out'),
    ])

    @app.callback(Output('up', 'resetKey'), Input('reset', 'n_clicks'), prevent_initial_call = True)
    def reset(_):
        return BucketUpload.reset()

    @app.callback(Output('out', 'children'), Input('up', 'uploadedFiles'))
    def show(files):
        return json.dumps(files) if files else 'none'

    dash_duo.start_server(app)

    test_file = tmp_path / 'keep me.bin'
    test_file.write_bytes(os.urandom(64 * 1024))
    dash_duo.driver.find_element('css selector', '#up input[type=file]').send_keys(str(test_file))
    dash_duo.wait_for_contains_text('#out', 'keep me.bin', timeout = 30)
    key = json.loads(dash_duo.find_element('#out').text)[0]['key']
    assert 'keep me.bin' in dash_duo.find_element('#up').text   # built-in file list row

    dash_duo.find_element('#reset').click()
    dash_duo.wait_for_text_to_equal('#out', 'none', timeout = 10)
    assert 'keep me.bin' not in dash_duo.find_element('#up').text
    assert s3.head_object(Bucket = BUCKET, Key = key)['ContentLength'] == 64 * 1024

    # The widget is fully usable after a reset, and uploadedFiles starts afresh.
    second = tmp_path / 'after reset.bin'
    second.write_bytes(b'x' * 1024)
    dash_duo.driver.find_element('css selector', '#up input[type=file]').send_keys(str(second))
    dash_duo.wait_for_contains_text('#out', 'after reset.bin', timeout = 30)
    files = json.loads(dash_duo.find_element('#out').text)
    assert [f['filename'] for f in files] == ['after reset.bin']
