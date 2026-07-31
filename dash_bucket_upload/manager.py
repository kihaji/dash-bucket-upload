"""Server-side half of the BucketUpload widget: per-widget upload configs and
the Flask routes the browser engine talks to.

The routes are deliberately stateless — nothing about an in-progress upload is
held in server memory, so the widget works unchanged under multi-worker
servers (gunicorn etc.). The boundary that keeps clients inside their sandbox
is `key_matches`: every route that receives a key verifies it has the shape
this widget's key generator produces for its configured prefix.
"""
from __future__ import annotations

import posixpath
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal

import flask
from botocore.exceptions import ClientError

from ._keys import MAX_PART, MiB, compute_part_size, generate_key, key_matches
from ._validation import UploadValidationError, validate_upload

if TYPE_CHECKING:
    from botocore.client import BaseClient
    from botocore.config import Config

SIGN_BATCH_MAX = 100
_RELAY_READ_CHUNK = 1 * MiB
_RELAY_SPOOL_MAX = 8 * MiB


def _pick(neutral_name: str, neutral: Any, alias_name: str, alias: Any) -> Any:
    """Resolve a neutral parameter against its boto3-flavored alias."""
    if neutral is not None and alias is not None:
        raise ValueError(f'pass either {neutral_name}= or {alias_name}=, not both')
    return neutral if neutral is not None else alias


@dataclass(frozen = True)
class UploadConfig:
    """Configuration for one widget instance (one `upload_id`)."""
    upload_id: str
    bucket: str
    prefix: str = ''
    mode: Literal['direct', 'relay'] = 'direct'
    max_file_size: int | None = None
    allowed_extensions: Sequence[str] | None = None
    allowed_mime_types: Sequence[str] | None = None
    part_size: int | None = None
    presign_expiration: int = 3600


class BucketUploadManager:
    """Registers the widget's upload routes on a Dash (or Flask) app and holds
    the object-store client plus per-widget `UploadConfig`s.

    Works with any S3-compatible store: AWS S3 (leave `endpoint_url` unset),
    MinIO, Ceph RGW, OpenStack Swift with the s3api middleware, and so on —
    point `endpoint_url` at the store and pass its access/secret key pair.

    Example (MinIO; identical shape for any other store):
        >>> app = Dash(__name__)
        >>> mgr = BucketUploadManager(app, endpoint_url='http://localhost:9000',
        ...                           access_key='minio', secret_key='minio123',
        ...                           bucket='uploads', prefix='incoming')
        >>> layout = BucketUpload(id='up', manager=mgr)

    Connection parameters use provider-neutral names (`access_key`,
    `secret_key`, `session_token`, `region`, `addressing_style`); the
    boto3-flavored spellings (`aws_access_key_id`, `aws_secret_access_key`,
    `aws_session_token`, `region_name`) are accepted as aliases. When no
    credentials are given at all, boto3's normal resolution chain runs
    (environment, shared config, instance/IRSA roles), which is usually what
    you want on AWS.

    Security note: the routes are open by default. In production, pass
    `auth_check` (e.g. `lambda r: current_user.is_authenticated`) and set
    `max_file_size` / `allowed_extensions`.
    """

    def __init__(
        self,
        app: Any,
        *,
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        session_token: str | None = None,
        addressing_style: Literal['path', 'virtual', 'auto'] | None = None,
        signature_version: str = 's3v4',
        # boto3-flavored aliases for the four connection parameters above
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        boto3_session: Any = None,
        botocore_config: 'Config | None' = None,
        s3_client: 'BaseClient | None' = None,
        bucket: str | None = None,
        prefix: str = '',
        mode: Literal['direct', 'relay'] = 'direct',
        max_file_size: int | None = None,
        allowed_extensions: Sequence[str] | None = None,
        allowed_mime_types: Sequence[str] | None = None,
        part_size: int | None = None,
        presign_expiration: int = 3600,
        url_prefix: str = '/dash-bucket-upload',
        auth_check: Callable[[flask.Request], bool] | None = None,
        key_generator: Callable[[UploadConfig, str], str] | None = None,
    ):
        server = getattr(app, 'server', app)  # dash.Dash -> flask.Flask
        if not isinstance(server, flask.Flask):
            raise TypeError('app must be a dash.Dash or flask.Flask instance')

        if s3_client is not None:
            self._s3 = s3_client
        else:
            from ._s3 import build_s3_client
            self._s3 = build_s3_client(
                endpoint_url = endpoint_url,
                region = _pick('region', region, 'region_name', region_name),
                access_key = _pick('access_key', access_key, 'aws_access_key_id', aws_access_key_id),
                secret_key = _pick('secret_key', secret_key, 'aws_secret_access_key', aws_secret_access_key),
                session_token = _pick('session_token', session_token, 'aws_session_token', aws_session_token),
                addressing_style = addressing_style,
                signature_version = signature_version,
                boto3_session = boto3_session,
                botocore_config = botocore_config,
            )

        self._url_prefix = url_prefix.rstrip('/')
        self._auth_check = auth_check
        self._key_generator = key_generator
        self._configs: dict[str, UploadConfig] = {}
        self._defaults = UploadConfig(
            upload_id = 'default',
            bucket = bucket or '',
            prefix = prefix,
            mode = mode,
            max_file_size = max_file_size,
            allowed_extensions = allowed_extensions,
            allowed_mime_types = allowed_mime_types,
            part_size = part_size,
            presign_expiration = presign_expiration,
        )
        if bucket is not None:
            self._configs['default'] = self._defaults

        self._register_routes(server)

    # -- configuration -----------------------------------------------------

    @property
    def url_prefix(self) -> str:
        return self._url_prefix

    def register(
        self,
        upload_id: str,
        *,
        bucket: str | None = None,
        prefix: str | None = None,
        mode: Literal['direct', 'relay'] | None = None,
        max_file_size: int | None = None,
        allowed_extensions: Sequence[str] | None = None,
        allowed_mime_types: Sequence[str] | None = None,
        part_size: int | None = None,
        presign_expiration: int | None = None,
    ) -> UploadConfig:
        """Register a named per-widget config; unset fields fall back to the
        manager-level defaults."""
        overrides = {
            key: value for key, value in {
                'bucket': bucket,
                'prefix': prefix,
                'mode': mode,
                'max_file_size': max_file_size,
                'allowed_extensions': allowed_extensions,
                'allowed_mime_types': allowed_mime_types,
                'part_size': part_size,
                'presign_expiration': presign_expiration,
            }.items() if value is not None
        }
        cfg = replace(self._defaults, upload_id = upload_id, **overrides)
        if not cfg.bucket:
            raise ValueError(f'upload config {upload_id!r} has no bucket (set one here or on the manager)')
        self._configs[upload_id] = cfg
        return cfg

    def get_config(self, upload_id: str) -> UploadConfig:
        try:
            return self._configs[upload_id]
        except KeyError:
            raise KeyError(
                f'no upload config named {upload_id!r} is registered on this manager '
                f'(known: {sorted(self._configs)})'
            ) from None

    # -- route plumbing ----------------------------------------------------

    def _register_routes(self, server: flask.Flask) -> None:
        # Blueprint name must be unique per manager so one app can mount
        # several managers under different url prefixes.
        name = 'dash_bucket_upload_' + self._url_prefix.strip('/').replace('/', '_')
        bp = flask.Blueprint(name, __name__, url_prefix = self._url_prefix)

        bp.before_request(self._guard)
        bp.post('/create')(self._route_create)
        bp.post('/sign-parts')(self._route_sign_parts)
        bp.put('/part')(self._route_part)
        bp.post('/complete')(self._route_complete)
        bp.post('/abort')(self._route_abort)
        bp.register_error_handler(UploadValidationError, self._handle_validation_error)
        bp.register_error_handler(ClientError, self._handle_client_error)

        server.register_blueprint(bp)

    def _guard(self):
        if self._auth_check is not None and not self._auth_check(flask.request):
            return flask.jsonify({'error': 'not authorized'}), 403
        return None

    @staticmethod
    def _handle_validation_error(err: UploadValidationError):
        return flask.jsonify({'error': str(err)}), err.status

    @staticmethod
    def _handle_client_error(err: ClientError):
        code = err.response.get('Error', {}).get('Code', 'S3Error')
        return flask.jsonify({'error': f'bucket operation failed: {code}'}), 502

    def _json_body(self) -> dict:
        body = flask.request.get_json(silent = True)
        if not isinstance(body, dict):
            raise UploadValidationError('request body must be a JSON object')
        return body

    def _config_from(self, body: dict) -> UploadConfig:
        upload_id = body.get('uploadId')
        if not isinstance(upload_id, str):
            raise UploadValidationError('uploadId is required')
        cfg = self._configs.get(upload_id)
        if cfg is None:
            raise UploadValidationError(f'unknown uploadId {upload_id!r}', status = 404)
        return cfg

    def _checked_key(self, cfg: UploadConfig, body: dict) -> str:
        key = body.get('key')
        if not isinstance(key, str) or not key_matches(cfg.prefix, key):
            raise UploadValidationError('key does not belong to this upload configuration', status = 403)
        return key

    @staticmethod
    def _s3_upload_id_from(body: dict) -> str:
        s3_upload_id = body.get('s3UploadId')
        if not isinstance(s3_upload_id, str) or not s3_upload_id:
            raise UploadValidationError('s3UploadId is required')
        return s3_upload_id

    # -- routes ------------------------------------------------------------

    def _route_create(self):
        body = self._json_body()
        cfg = self._config_from(body)
        filename = validate_upload(cfg, body.get('filename'), body.get('size'), body.get('contentType'))

        if self._key_generator is not None:
            key = self._key_generator(cfg, filename)
        else:
            key = generate_key(cfg.prefix, filename)

        created = self._s3.create_multipart_upload(
            Bucket = cfg.bucket,
            Key = key,
            ContentType = body.get('contentType') or 'application/octet-stream',
        )
        return flask.jsonify({
            'bucket': cfg.bucket,
            'key': key,
            's3UploadId': created['UploadId'],
            'partSize': compute_part_size(body.get('size', 0), cfg.part_size),
            'mode': cfg.mode,
        })

    def _route_sign_parts(self):
        body = self._json_body()
        cfg = self._config_from(body)
        if cfg.mode != 'direct':
            raise UploadValidationError('sign-parts is only available in direct mode', status = 403)
        key = self._checked_key(cfg, body)
        s3_upload_id = self._s3_upload_id_from(body)

        part_numbers = body.get('partNumbers')
        if (
            not isinstance(part_numbers, list)
            or not part_numbers
            or len(part_numbers) > SIGN_BATCH_MAX
            or not all(isinstance(n, int) and 1 <= n <= 10000 for n in part_numbers)
        ):
            raise UploadValidationError(f'partNumbers must be a list of 1-{SIGN_BATCH_MAX} part numbers in [1, 10000]')

        urls = {
            str(n): self._s3.generate_presigned_url(
                'upload_part',
                Params = {'Bucket': cfg.bucket, 'Key': key, 'UploadId': s3_upload_id, 'PartNumber': n},
                ExpiresIn = cfg.presign_expiration,
            )
            for n in part_numbers
        }
        return flask.jsonify({'urls': urls})

    def _route_part(self):
        args = flask.request.args
        body = {'uploadId': args.get('uploadId'), 'key': args.get('key'), 's3UploadId': args.get('s3UploadId')}
        cfg = self._config_from(body)
        if cfg.mode != 'relay':
            raise UploadValidationError('part upload is only available in relay mode', status = 403)
        key = self._checked_key(cfg, body)
        s3_upload_id = self._s3_upload_id_from(body)
        try:
            part_number = int(args.get('partNumber', ''))
        except ValueError:
            raise UploadValidationError('partNumber must be an integer') from None
        if not 1 <= part_number <= 10000:
            raise UploadValidationError('partNumber must be in [1, 10000]')

        # Stream the request body into a bounded spool — never the whole file,
        # and never request.data (which would buffer the body in memory).
        # boto3's upload_part needs a seekable, length-known body for SigV4.
        max_bytes = (cfg.part_size or MAX_PART) + 1 * MiB
        received = 0
        with tempfile.SpooledTemporaryFile(max_size = _RELAY_SPOOL_MAX) as spool:
            stream = flask.request.stream
            while True:
                chunk = stream.read(_RELAY_READ_CHUNK)
                if not chunk:
                    break
                received += len(chunk)
                if received > max_bytes:
                    raise UploadValidationError('part exceeds the maximum part size', status = 413)
                spool.write(chunk)
            spool.seek(0)
            result = self._s3.upload_part(
                Bucket = cfg.bucket,
                Key = key,
                UploadId = s3_upload_id,
                PartNumber = part_number,
                Body = spool,
                ContentLength = received,
            )
        return flask.jsonify({'partNumber': part_number, 'etag': result['ETag']})

    def _route_complete(self):
        body = self._json_body()
        cfg = self._config_from(body)
        key = self._checked_key(cfg, body)
        s3_upload_id = self._s3_upload_id_from(body)

        parts = body.get('parts')
        if (
            not isinstance(parts, list)
            or not parts
            or not all(
                isinstance(p, dict) and isinstance(p.get('partNumber'), int) and isinstance(p.get('etag'), str)
                for p in parts
            )
        ):
            raise UploadValidationError('parts must be a non-empty list of {partNumber, etag}')

        completed = self._s3.complete_multipart_upload(
            Bucket = cfg.bucket,
            Key = key,
            UploadId = s3_upload_id,
            MultipartUpload = {
                'Parts': [
                    {'PartNumber': p['partNumber'], 'ETag': p['etag']}
                    for p in sorted(parts, key = lambda p: p['partNumber'])
                ],
            },
        )
        # The client's size claim is never trusted; ask the bucket.
        head = self._s3.head_object(Bucket = cfg.bucket, Key = key)
        return flask.jsonify({
            'bucket': cfg.bucket,
            'key': key,
            'filename': posixpath.basename(key),
            'size': head['ContentLength'],
            'etag': completed.get('ETag', head.get('ETag', '')),
        })

    def _route_abort(self):
        body = self._json_body()
        cfg = self._config_from(body)
        key = self._checked_key(cfg, body)
        s3_upload_id = self._s3_upload_id_from(body)
        self._s3.abort_multipart_upload(Bucket = cfg.bucket, Key = key, UploadId = s3_upload_id)
        return flask.jsonify({'aborted': True})
