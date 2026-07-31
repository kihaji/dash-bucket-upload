import os

import boto3
import pytest

from dash_bucket_upload.manager import BucketUploadManager

# Point BUCKET_UPLOAD_S3_ENDPOINT at a real S3-compatible service (e.g. the
# MinIO compose file in examples/) to run this whole suite against it instead
# of moto. Defaults are airgap-friendly: moto runs in-process, no network.
ACCESS_KEY = os.environ.get('BUCKET_UPLOAD_S3_ACCESS_KEY', 'testing')
SECRET_KEY = os.environ.get('BUCKET_UPLOAD_S3_SECRET_KEY', 'testing')
REGION = os.environ.get('BUCKET_UPLOAD_S3_REGION', 'us-east-1')
BUCKET = os.environ.get('BUCKET_UPLOAD_S3_BUCKET', 'dash-bucket-upload-tests')


@pytest.fixture(scope = 'session')
def moto_endpoint():
    """A real HTTP S3 endpoint: an external one when configured, otherwise a
    moto server thread (real HTTP so presigned URLs can actually be PUT to)."""
    external = os.environ.get('BUCKET_UPLOAD_S3_ENDPOINT')
    if external:
        yield external
        return
    from moto.server import ThreadedMotoServer
    server = ThreadedMotoServer(port = 0)
    server.start()
    host, port = server.get_host_and_port()
    yield f'http://{host}:{port}'
    server.stop()


@pytest.fixture
def s3(moto_endpoint):
    client = boto3.client(
        's3',
        endpoint_url = moto_endpoint,
        region_name = REGION,
        aws_access_key_id = ACCESS_KEY,
        aws_secret_access_key = SECRET_KEY,
    )
    client.create_bucket(Bucket = BUCKET)
    yield client
    # Full cleanup so tests stay independent.
    for page in client.get_paginator('list_objects_v2').paginate(Bucket = BUCKET):
        for obj in page.get('Contents', []):
            client.delete_object(Bucket = BUCKET, Key = obj['Key'])
    uploads = client.list_multipart_uploads(Bucket = BUCKET).get('Uploads', [])
    for up in uploads:
        client.abort_multipart_upload(Bucket = BUCKET, Key = up['Key'], UploadId = up['UploadId'])
    client.delete_bucket(Bucket = BUCKET)


def make_manager(flask_app, moto_endpoint, **kwargs):
    defaults = dict(
        endpoint_url = moto_endpoint,
        region = REGION,
        access_key = ACCESS_KEY,
        secret_key = SECRET_KEY,
        bucket = BUCKET,
        prefix = 'incoming',
    )
    defaults.update(kwargs)
    return BucketUploadManager(flask_app, **defaults)


@pytest.fixture
def flask_app():
    import flask
    app = flask.Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def direct_manager(flask_app, s3, moto_endpoint):
    return make_manager(flask_app, moto_endpoint, mode = 'direct')


@pytest.fixture
def relay_manager(flask_app, s3, moto_endpoint):
    return make_manager(flask_app, moto_endpoint, mode = 'relay')


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()
