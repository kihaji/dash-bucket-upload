"""Relay-mode round trip: parts stream through the Flask route into the
bucket; the whole file is never buffered."""
from .conftest import BUCKET


def create(client, filename = 'video.mp4', size = 4096):
    resp = client.post('/dash-bucket-upload/create', json = {
        'uploadId': 'default', 'filename': filename, 'size': size, 'contentType': 'video/mp4',
    })
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def put_part(client, body, part_number, data):
    return client.put(
        f"/dash-bucket-upload/part?uploadId=default&key={body['key']}"
        f"&s3UploadId={body['s3UploadId']}&partNumber={part_number}",
        data = data,
        content_type = 'application/octet-stream',
    )


def test_full_relay_round_trip(relay_manager, client, s3):
    # All parts except the last must be >= 5 MiB (S3 rule, enforced by moto).
    payload_parts = [b'x' * (5 * 1024 * 1024), b'y' * 1000]
    total = sum(len(p) for p in payload_parts)
    body = create(client, size = total)
    assert body['mode'] == 'relay'

    etags = []
    for part_number, data in enumerate(payload_parts, start = 1):
        resp = put_part(client, body, part_number, data)
        assert resp.status_code == 200, resp.get_json()
        part = resp.get_json()
        assert part['partNumber'] == part_number
        assert part['etag']
        etags.append({'partNumber': part['partNumber'], 'etag': part['etag']})

    done = client.post('/dash-bucket-upload/complete', json = {
        'uploadId': 'default', 'key': body['key'], 's3UploadId': body['s3UploadId'], 'parts': etags,
    })
    assert done.status_code == 200
    assert done.get_json()['size'] == total

    stored = s3.get_object(Bucket = BUCKET, Key = body['key'])['Body'].read()
    assert stored == b''.join(payload_parts)


def test_part_rejects_foreign_key(relay_manager, client):
    body = create(client)
    resp = client.put(
        f"/dash-bucket-upload/part?uploadId=default&key=elsewhere/x.bin"
        f"&s3UploadId={body['s3UploadId']}&partNumber=1",
        data = b'x',
    )
    assert resp.status_code == 403


def test_part_rejects_bad_part_number(relay_manager, client):
    body = create(client)
    for bad in ('0', '10001', 'NaN', ''):
        resp = client.put(
            f"/dash-bucket-upload/part?uploadId=default&key={body['key']}"
            f"&s3UploadId={body['s3UploadId']}&partNumber={bad}",
            data = b'x',
        )
        assert resp.status_code == 400, bad


def test_part_size_cap_enforced(relay_manager, flask_app, s3, moto_endpoint, client):
    # Re-register with a tiny part size so the cap is testable without
    # shipping hundreds of MB through the test client.
    relay_manager.register('tiny', part_size = 1024)
    body_resp = client.post('/dash-bucket-upload/create', json = {
        'uploadId': 'tiny', 'filename': 'a.bin', 'size': 10,
    })
    body = body_resp.get_json()
    resp = client.put(
        f"/dash-bucket-upload/part?uploadId=tiny&key={body['key']}"
        f"&s3UploadId={body['s3UploadId']}&partNumber=1",
        data = b'z' * (1024 + 1024 * 1024 + 1),  # part_size + 1 MiB + 1
    )
    assert resp.status_code == 413


def test_sign_parts_refused_in_relay_mode(relay_manager, client):
    body = create(client)
    resp = client.post('/dash-bucket-upload/sign-parts', json = {
        'uploadId': 'default', 'key': body['key'], 's3UploadId': body['s3UploadId'],
        'partNumbers': [1],
    })
    assert resp.status_code == 403
