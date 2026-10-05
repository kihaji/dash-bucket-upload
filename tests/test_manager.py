import flask
import pytest

from dash_bucket_upload.manager import BucketUploadManager

from .conftest import make_manager


def test_requires_dash_or_flask():
    with pytest.raises(TypeError):
        BucketUploadManager(object(), bucket = 'b')


def test_register_falls_back_to_defaults(flask_app, moto_endpoint):
    mgr = make_manager(flask_app, moto_endpoint, max_file_size = 123)
    cfg = mgr.register('other', bucket = 'media')
    assert cfg.bucket == 'media'
    assert cfg.prefix == 'incoming'      # inherited
    assert cfg.max_file_size == 123      # inherited
    assert mgr.get_config('other') is cfg


def test_register_without_bucket_anywhere_raises(flask_app, moto_endpoint):
    mgr = make_manager(flask_app, moto_endpoint)
    mgr._configs.clear()
    mgr._defaults = mgr._defaults.__class__(upload_id = 'default', bucket = '')
    with pytest.raises(ValueError):
        mgr.register('x')


def test_get_config_unknown_raises_helpfully(flask_app, moto_endpoint):
    mgr = make_manager(flask_app, moto_endpoint)
    with pytest.raises(KeyError, match = 'known'):
        mgr.get_config('missing')


def test_auth_check_gates_every_route(flask_app, moto_endpoint):
    make_manager(flask_app, moto_endpoint, auth_check = lambda request: False)
    client = flask_app.test_client()
    for method, path in [
        ('post', '/dash-bucket-upload/create'),
        ('post', '/dash-bucket-upload/sign-parts'),
        ('put', '/dash-bucket-upload/part'),
        ('post', '/dash-bucket-upload/complete'),
        ('post', '/dash-bucket-upload/abort'),
    ]:
        resp = getattr(client, method)(path, json = {})
        assert resp.status_code == 403, path


def test_two_managers_on_one_app(flask_app, moto_endpoint):
    make_manager(flask_app, moto_endpoint)
    make_manager(flask_app, moto_endpoint, url_prefix = '/other-upload')
    rules = {str(r) for r in flask_app.url_map.iter_rules()}
    assert '/dash-bucket-upload/create' in rules
    assert '/other-upload/create' in rules


def test_manager_accepts_dash_app(moto_endpoint):
    dash = pytest.importorskip('dash')
    app = dash.Dash(__name__)
    mgr = make_manager(app, moto_endpoint)
    assert isinstance(app.server, flask.Flask)
    assert mgr.url_prefix == '/dash-bucket-upload'


def test_boto3_flavored_aliases_still_work(flask_app, moto_endpoint):
    from .conftest import ACCESS_KEY, BUCKET, REGION, SECRET_KEY
    mgr = BucketUploadManager(
        flask_app,
        endpoint_url = moto_endpoint,
        region_name = REGION,
        aws_access_key_id = ACCESS_KEY,
        aws_secret_access_key = SECRET_KEY,
        bucket = BUCKET,
    )
    creds = mgr._s3._request_signer._credentials
    assert creds.access_key == ACCESS_KEY
    assert mgr._s3.meta.region_name == REGION


def test_neutral_and_alias_together_is_an_error(flask_app, moto_endpoint):
    with pytest.raises(ValueError, match = 'access_key'):
        BucketUploadManager(
            flask_app,
            endpoint_url = moto_endpoint,
            access_key = 'a',
            aws_access_key_id = 'b',
            secret_key = 's',
            bucket = 'bkt',
        )


def test_addressing_style_and_signature_version_pass_through(flask_app, moto_endpoint):
    from .conftest import ACCESS_KEY, BUCKET, SECRET_KEY
    mgr = BucketUploadManager(
        flask_app,
        endpoint_url = moto_endpoint,
        access_key = ACCESS_KEY,
        secret_key = SECRET_KEY,
        bucket = BUCKET,
        addressing_style = 'virtual',
    )
    assert mgr._s3.meta.config.s3['addressing_style'] == 'virtual'
    assert mgr._s3.meta.config.signature_version == 's3v4'


def test_malformed_json_is_a_clean_400(flask_app, moto_endpoint):
    make_manager(flask_app, moto_endpoint)
    client = flask_app.test_client()
    resp = client.post('/dash-bucket-upload/create', data = 'not json', content_type = 'application/json')
    assert resp.status_code == 400
    assert 'error' in resp.get_json()


def _create(client, upload_id = 'default'):
    return client.post('/dash-bucket-upload/create', json = {'uploadId': upload_id, 'filename': 'a.txt', 'size': 10})


def test_bucket_error_is_502_and_logged(flask_app, s3, moto_endpoint, caplog):
    mgr = make_manager(flask_app, moto_endpoint)
    mgr.register('missing', bucket = 'no-such-bucket-for-tests')
    with caplog.at_level('WARNING', logger = 'dash_bucket_upload.manager'):
        resp = _create(flask_app.test_client(), 'missing')
    assert resp.status_code == 502
    assert resp.get_json() == {'error': 'bucket operation failed: NoSuchBucket'}
    assert 'CreateMultipartUpload' in caplog.text
    assert 'bucket does not exist' in caplog.text   # store's full message reaches the log only


def test_unreachable_endpoint_is_clean_502(flask_app, caplog):
    import socket
    with socket.socket() as sock:   # grab a port nothing is listening on
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    from botocore.config import Config
    make_manager(flask_app, f'http://127.0.0.1:{port}', botocore_config = Config(retries = {'total_max_attempts': 1}))
    with caplog.at_level('ERROR', logger = 'dash_bucket_upload.manager'):
        resp = _create(flask_app.test_client())
    assert resp.status_code == 502
    assert resp.get_json() == {'error': 'bucket request failed: EndpointConnectionError'}
    assert 'EndpointConnectionError' in caplog.text


def test_store_timeout_is_504(flask_app):
    from botocore.exceptions import ConnectTimeoutError

    class TimingOutClient:
        def create_multipart_upload(self, **_):
            raise ConnectTimeoutError(endpoint_url = 'http://store.invalid')

    BucketUploadManager(flask_app, s3_client = TimingOutClient(), bucket = 'b')
    resp = _create(flask_app.test_client())
    assert resp.status_code == 504
    assert resp.get_json() == {'error': 'bucket request failed: ConnectTimeoutError'}


def test_client_fails_fast_by_default(flask_app, moto_endpoint):
    from dash_bucket_upload._s3 import CONNECT_TIMEOUT, MAX_ATTEMPTS
    mgr = make_manager(flask_app, moto_endpoint)
    assert mgr._s3.meta.config.connect_timeout == CONNECT_TIMEOUT
    assert mgr._s3.meta.config.retries['total_max_attempts'] == MAX_ATTEMPTS


def test_botocore_config_overrides_timeouts(flask_app, moto_endpoint):
    from botocore.config import Config
    mgr = make_manager(flask_app, moto_endpoint, botocore_config = Config(connect_timeout = 30))
    assert mgr._s3.meta.config.connect_timeout == 30
