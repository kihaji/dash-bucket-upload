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


def test_malformed_json_is_a_clean_400(flask_app, moto_endpoint):
    make_manager(flask_app, moto_endpoint)
    client = flask_app.test_client()
    resp = client.post('/dash-bucket-upload/create', data = 'not json', content_type = 'application/json')
    assert resp.status_code == 400
    assert 'error' in resp.get_json()
