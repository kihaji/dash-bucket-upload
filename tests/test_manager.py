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
