"""Direct-mode round trip: create → sign-parts → real HTTP PUTs against the
moto server with the presigned URLs → complete. This exercises the actual
SigV4 presign path a browser would use."""
import requests

from dash_bucket_upload._keys import MiB

from .conftest import BUCKET


def create(client, filename = 'data.bin', size = 1024, upload_id = 'default'):
    resp = client.post('/dash-bucket-upload/create', json = {
        'uploadId': upload_id, 'filename': filename, 'size': size, 'contentType': 'application/octet-stream',
    })
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def test_create_returns_upload_descriptor(direct_manager, client):
    body = create(client)
    assert body['bucket'] == BUCKET
    assert body['key'].startswith('incoming/')
    assert body['key'].endswith('/data.bin')
    assert body['mode'] == 'direct'
    assert body['partSize'] == 16 * MiB
    assert body['s3UploadId']


def test_full_direct_round_trip(direct_manager, client, s3):
    # All parts except the last must be >= 5 MiB (S3 rule, enforced by moto).
    payload_parts = [b'a' * (5 * MiB), b'b' * 2048]
    body = create(client, size = sum(len(p) for p in payload_parts))

    sign = client.post('/dash-bucket-upload/sign-parts', json = {
        'uploadId': 'default', 'key': body['key'], 's3UploadId': body['s3UploadId'],
        'partNumbers': [1, 2],
    })
    assert sign.status_code == 200
    urls = sign.get_json()['urls']

    etags = []
    for part_number, data in enumerate(payload_parts, start = 1):
        put = requests.put(urls[str(part_number)], data = data, timeout = 10)
        assert put.status_code == 200
        assert put.headers.get('ETag')
        etags.append({'partNumber': part_number, 'etag': put.headers['ETag']})

    done = client.post('/dash-bucket-upload/complete', json = {
        'uploadId': 'default', 'key': body['key'], 's3UploadId': body['s3UploadId'], 'parts': etags,
    })
    assert done.status_code == 200
    result = done.get_json()
    assert result['size'] == sum(len(p) for p in payload_parts)
    assert result['filename'] == 'data.bin'

    stored = s3.get_object(Bucket = BUCKET, Key = body['key'])['Body'].read()
    assert stored == b''.join(payload_parts)


def test_abort_removes_multipart_upload(direct_manager, client, s3):
    body = create(client)
    resp = client.post('/dash-bucket-upload/abort', json = {
        'uploadId': 'default', 'key': body['key'], 's3UploadId': body['s3UploadId'],
    })
    assert resp.status_code == 200
    uploads = s3.list_multipart_uploads(Bucket = BUCKET).get('Uploads', [])
    assert uploads == []


def test_sign_parts_rejects_foreign_key(direct_manager, client):
    body = create(client)
    resp = client.post('/dash-bucket-upload/sign-parts', json = {
        'uploadId': 'default', 'key': 'somewhere/else.bin', 's3UploadId': body['s3UploadId'],
        'partNumbers': [1],
    })
    assert resp.status_code == 403


def test_sign_parts_rejects_oversized_batch(direct_manager, client):
    body = create(client)
    resp = client.post('/dash-bucket-upload/sign-parts', json = {
        'uploadId': 'default', 'key': body['key'], 's3UploadId': body['s3UploadId'],
        'partNumbers': list(range(1, 102)),
    })
    assert resp.status_code == 400


def test_create_rejects_unknown_upload_id(direct_manager, client):
    resp = client.post('/dash-bucket-upload/create', json = {
        'uploadId': 'nope', 'filename': 'a.bin', 'size': 1,
    })
    assert resp.status_code == 404


def test_relay_part_route_refused_in_direct_mode(direct_manager, client):
    body = create(client)
    resp = client.put(
        f"/dash-bucket-upload/part?uploadId=default&key={body['key']}"
        f"&s3UploadId={body['s3UploadId']}&partNumber=1",
        data = b'x',
    )
    assert resp.status_code == 403
