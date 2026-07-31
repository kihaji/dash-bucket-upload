import pytest

from dash_bucket_upload import BucketUpload

from .conftest import make_manager


def test_requires_manager_or_api_path():
    with pytest.raises(ValueError):
        BucketUpload(id = 'x')


def test_manual_api_path():
    c = BucketUpload(id = 'x', api_path = '/my-upload')
    assert c.apiPath == '/my-upload'
    assert c.uploadId == 'default'
    assert c.multiple is True


def test_manager_wiring(flask_app, moto_endpoint):
    mgr = make_manager(flask_app, moto_endpoint, max_file_size = 42, allowed_extensions = ['.csv', 'txt'])
    c = BucketUpload(id = 'x', manager = mgr)
    assert c.apiPath == '/dash-bucket-upload'
    assert c.maxFileSize == 42          # mirrored from server config
    assert c.accept == '.csv,.txt'      # derived from allowed_extensions


def test_manager_wiring_unknown_upload_id_raises_early(flask_app, moto_endpoint):
    mgr = make_manager(flask_app, moto_endpoint)
    with pytest.raises(KeyError):
        BucketUpload(id = 'x', manager = mgr, upload_id = 'nope')


def test_explicit_props_beat_mirrored_config(flask_app, moto_endpoint):
    mgr = make_manager(flask_app, moto_endpoint, max_file_size = 42)
    c = BucketUpload(id = 'x', manager = mgr, max_file_size = 10, accept = '.bin')
    assert c.maxFileSize == 10
    assert c.accept == '.bin'


def test_snake_case_style_props():
    c = BucketUpload(
        id = 'x', api_path = '/p',
        class_name = 'zone', style_active = {'borderColor': 'red'}, show_file_list = False,
    )
    assert c.className == 'zone'
    assert c.styleActive == {'borderColor': 'red'}
    assert c.showFileList is False


def test_version_is_exposed():
    import dash_bucket_upload
    assert dash_bucket_upload.__version__
