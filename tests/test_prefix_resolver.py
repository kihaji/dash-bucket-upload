"""Per-request key prefixes: a `prefix_resolver` picks the prefix from the
caller's request, and every follow-up call is checked against the prefix
resolved for *that* caller. Two Users are simulated with an `X-User` header."""
import pytest
import requests

from dash_bucket_upload._keys import MiB

from .conftest import BUCKET, make_manager

API = '/dash-bucket-upload'


def by_user(request, config):
    user = request.headers.get('X-User')
    return f'users/{user}' if user else None


def as_user(user):
    return {'X-User': user}


def create(client, user, upload_id = 'default', filename = 'data.bin', size = 1024):
    resp = client.post(f'{API}/create', headers = as_user(user), json = {
        'uploadId': upload_id, 'filename': filename, 'size': size, 'contentType': 'application/octet-stream',
    })
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def ids(body, upload_id = 'default'):
    return {'uploadId': upload_id, 'key': body['key'], 's3UploadId': body['s3UploadId']}


def put_direct_parts(client, user, body, payload_parts):
    sign = client.post(f'{API}/sign-parts', headers = as_user(user), json = {
        **ids(body), 'partNumbers': list(range(1, len(payload_parts) + 1)),
    })
    assert sign.status_code == 200, sign.get_json()
    urls = sign.get_json()['urls']
    etags = []
    for n, data in enumerate(payload_parts, start = 1):
        put = requests.put(urls[str(n)], data = data, timeout = 10)
        assert put.status_code == 200
        etags.append({'partNumber': n, 'etag': put.headers['ETag']})
    return etags


@pytest.fixture
def resolving_manager(flask_app, s3, moto_endpoint):
    return make_manager(flask_app, moto_endpoint, mode = 'direct', prefix_resolver = by_user)


def test_create_places_key_under_the_callers_prefix(resolving_manager, client):
    body = create(client, 'alice')
    assert body['key'].startswith('users/alice/')
    assert body['key'].endswith('/data.bin')


def test_user_completes_own_direct_upload(resolving_manager, client, s3):
    payload_parts = [b'a' * (5 * MiB), b'b' * 2048]
    body = create(client, 'alice', size = sum(len(p) for p in payload_parts))
    etags = put_direct_parts(client, 'alice', body, payload_parts)

    done = client.post(f'{API}/complete', headers = as_user('alice'), json = {**ids(body), 'parts': etags})
    assert done.status_code == 200, done.get_json()
    assert s3.get_object(Bucket = BUCKET, Key = body['key'])['Body'].read() == b''.join(payload_parts)


def test_other_user_cannot_sign_parts_for_an_upload(resolving_manager, client):
    body = create(client, 'alice')
    resp = client.post(f'{API}/sign-parts', headers = as_user('bob'), json = {**ids(body), 'partNumbers': [1]})
    assert resp.status_code == 403


def test_other_user_cannot_complete_an_upload(resolving_manager, client, s3):
    payload = b'a' * 2048
    body = create(client, 'alice', size = len(payload))
    parts = put_direct_parts(client, 'alice', body, [payload])

    resp = client.post(f'{API}/complete', headers = as_user('bob'), json = {**ids(body), 'parts': parts})
    assert resp.status_code == 403
    listed = s3.list_objects_v2(Bucket = BUCKET).get('Contents', [])
    assert listed == []


def test_other_user_cannot_abort_an_upload(resolving_manager, client, s3):
    body = create(client, 'alice')
    resp = client.post(f'{API}/abort', headers = as_user('bob'), json = ids(body))
    assert resp.status_code == 403
    uploads = s3.list_multipart_uploads(Bucket = BUCKET).get('Uploads', [])
    assert [u['Key'] for u in uploads] == [body['key']]


def test_other_user_cannot_relay_parts_into_an_upload(flask_app, s3, moto_endpoint, client):
    make_manager(flask_app, moto_endpoint, mode = 'relay', prefix_resolver = by_user)
    body = create(client, 'alice')
    path = f"{API}/part?uploadId=default&key={body['key']}&s3UploadId={body['s3UploadId']}&partNumber=1"

    assert client.put(path, headers = as_user('bob'), data = b'x').status_code == 403
    assert client.put(path, headers = as_user('alice'), data = b'x').status_code == 200


def test_a_caller_without_a_prefix_is_refused(resolving_manager, client):
    resp = client.post(f'{API}/create', json = {'uploadId': 'default', 'filename': 'a.bin', 'size': 1})
    assert resp.status_code == 403


def test_resolver_can_be_set_per_registered_config(flask_app, s3, moto_endpoint, client):
    mgr = make_manager(flask_app, moto_endpoint)
    mgr.register('workspace', prefix_resolver = lambda request, config: f"{config.prefix}/ws-{request.headers['X-User']}")

    assert create(client, 'alice', upload_id = 'workspace')['key'].startswith('incoming/ws-alice/')
    assert create(client, 'alice')['key'].startswith('incoming/')
    assert not create(client, 'alice')['key'].startswith('incoming/ws-alice/')


@pytest.mark.parametrize('blank', ['', '/', '  '])
def test_a_blank_resolved_prefix_is_refused(flask_app, s3, moto_endpoint, client, blank):
    # A blank prefix would put every such caller in the bucket root, together.
    make_manager(flask_app, moto_endpoint, prefix_resolver = lambda request, config: blank)
    resp = client.post(f'{API}/create', json = {'uploadId': 'default', 'filename': 'a.bin', 'size': 1})
    assert resp.status_code == 403
