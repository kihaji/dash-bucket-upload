"""Server-side half of the BucketUpload widget: per-widget upload configs and
the Flask routes the browser engine talks to.

The routes are deliberately stateless — nothing about an in-progress upload is
held in server memory, so the widget works unchanged under multi-worker
servers (gunicorn etc.). The boundary that keeps clients inside their sandbox
is `key_matches`: every route that receives a key verifies it has the shape
this widget's key generator produces for its prefix — the configured one, or
the one a `prefix_resolver` returns for the calling request.
"""
from __future__ import annotations

import logging
import posixpath
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal

import flask
from botocore.exceptions import BotoCoreError, ClientError, ConnectTimeoutError, ReadTimeoutError

from ._keys import MAX_PART, MiB, compute_part_size, generate_key, key_matches
from ._validation import UploadValidationError, validate_upload

if TYPE_CHECKING:
    from botocore.client import BaseClient
    from botocore.config import Config

logger = logging.getLogger(__name__)

PrefixResolver = Callable[[flask.Request, 'UploadConfig'], 'str | None']
"""`(request, config) -> prefix | None`: the key prefix for the caller making
`request`, or `None` to refuse it (HTTP 403)."""

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
    """Configuration for one widget instance (one `upload_id`).

    Created by `BucketUploadManager` (the manager-level defaults become the
    `'default'` config) and by `BucketUploadManager.register`. Frozen: to change
    a config, register it again.

    Attributes:
        upload_id: Name the component refers to via `upload_id=`.
        bucket: Target bucket (a container on Swift).
        prefix: Key prefix; objects land at `<prefix>/<uuid4>/<filename>`.
        mode: `'direct'` (browser → bucket via presigned URLs) or `'relay'`
            (browser → Dash server → bucket).
        max_file_size: Maximum file size in bytes, enforced server-side
            (HTTP 413) and mirrored client-side. `None` means unlimited.
        allowed_extensions: Allowed filename extensions such as `['.csv']`
            (leading dot optional, case-insensitive). `None` allows any.
        allowed_mime_types: Allowed browser-reported MIME types. `None`
            allows any. Browsers report what the OS guesses from the
            extension, so treat this as a convenience, not a security control.
        part_size: Fixed multipart part size in bytes. `None` picks one
            automatically (16 MiB minimum, grown to stay under 10,000 parts).
            Must be at least 5 MiB.
        presign_expiration: Lifetime of presigned part URLs in seconds
            (direct mode). Expired URLs are refreshed automatically.
        prefix_resolver: `(request, config) -> prefix | None`, called with the
            `flask.Request` on every route. Its result replaces `prefix` for
            that request, both for new keys and for checking keys on follow-up
            calls, so a caller can only touch uploads under its own prefix.
            Returning `None` or a blank prefix rejects the request with HTTP
            403. `None` (no resolver) uses the static `prefix`.
    """
    upload_id: str
    bucket: str
    prefix: str = ''
    mode: Literal['direct', 'relay'] = 'direct'
    max_file_size: int | None = None
    allowed_extensions: Sequence[str] | None = None
    allowed_mime_types: Sequence[str] | None = None
    part_size: int | None = None
    presign_expiration: int = 3600
    prefix_resolver: PrefixResolver | None = None


class BucketUploadManager:
    """Registers the upload routes on a Dash (or Flask) app and holds the
    object-store client plus the per-widget `UploadConfig`s.

    Works with any S3-compatible store: AWS S3 (leave `endpoint_url` unset),
    MinIO, Ceph RGW, OpenStack Swift with the s3api middleware, and so on.
    Point `endpoint_url` at the store and pass its access/secret key pair.

    Construct it once, at import time, before the app starts serving: the
    routes are a Flask blueprint, and Flask refuses new blueprints after the
    first request.

    Examples:
        >>> app = Dash(__name__)
        >>> mgr = BucketUploadManager(app, endpoint_url='http://localhost:9000',
        ...                           access_key='minio', secret_key='minio123',
        ...                           bucket='uploads', prefix='incoming')
        >>> layout = BucketUpload(id='up', manager=mgr)

    Args:
        app: The `dash.Dash` app (or a bare `flask.Flask` server) to mount the
            routes on.
        endpoint_url: URL of the S3-compatible endpoint, e.g.
            `'http://minio:9000'`. Leave unset for AWS S3.
        region: Signing region. Required by AWS; other stores usually accept
            any value (`'us-east-1'` is a safe default). Alias: `region_name`.
        access_key: Access key ID. Alias: `aws_access_key_id`. When no
            credentials are given at all, boto3's normal resolution chain runs
            (environment, shared config files, instance/IRSA roles).
        secret_key: Secret access key. Alias: `aws_secret_access_key`.
        session_token: Session token for temporary credentials. Alias:
            `aws_session_token`.
        addressing_style: `'path'`, `'virtual'` or `'auto'`. Defaults to
            `'path'` when `endpoint_url` is set (self-hosted stores rarely have
            wildcard DNS), otherwise boto3's default.
        signature_version: Request signing version. Presigned URLs need SigV4
            (`'s3v4'`) on every current store.
        region_name: boto3-flavored alias of `region`.
        aws_access_key_id: boto3-flavored alias of `access_key`.
        aws_secret_access_key: boto3-flavored alias of `secret_key`.
        aws_session_token: boto3-flavored alias of `session_token`.
        boto3_session: A `boto3.Session` to build the client from instead of
            the credential parameters (e.g. one using a named profile).
        botocore_config: A `botocore.config.Config` merged over the defaults
            (it wins). Use it to tune timeouts, retries, proxies or TLS.
        s3_client: A ready-made boto3 S3 client. Overrides every connection
            parameter above.
        bucket: Bucket for the `'default'` upload config. When omitted, no
            `'default'` config exists and every widget needs a `register()`ed
            config of its own.
        prefix: Default key prefix.
        mode: Default transport, `'direct'` or `'relay'`.
        max_file_size: Default maximum file size in bytes.
        allowed_extensions: Default extension allowlist.
        allowed_mime_types: Default MIME type allowlist.
        part_size: Default fixed part size in bytes (`None` = automatic).
        presign_expiration: Default presigned-URL lifetime in seconds.
        prefix_resolver: Default per-request prefix hook,
            `(request, config) -> prefix | None`, so one caller cannot touch
            another's upload. See `UploadConfig.prefix_resolver`.
        url_prefix: URL path the routes are mounted under. Each manager on one
            app needs its own.
        auth_check: Called with the `flask.Request` before every route; return
            `False` to reject with HTTP 403. The routes are open without it.
        key_generator: `(config, sanitized_filename) -> key` replacement for
            the default `<prefix>/<uuid4>/<filename>` scheme. Generated keys
            must still match that shape, because the stateless routes check
            every later request against it. With a `prefix_resolver`, the
            config passed in carries the resolved prefix.

    Raises:
        TypeError: `app` is neither a Dash nor a Flask app.
        ValueError: A neutral parameter and its alias were both given.
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
        prefix_resolver: PrefixResolver | None = None,
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
            prefix_resolver = prefix_resolver,
        )
        if bucket is not None:
            self._configs['default'] = self._defaults

        self._register_routes(server)

    # -- configuration -----------------------------------------------------

    @property
    def url_prefix(self) -> str:
        """URL path the routes are mounted under (no trailing slash)."""
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
        prefix_resolver: PrefixResolver | None = None,
    ) -> UploadConfig:
        """Register a named per-widget config; unset fields fall back to the
        manager-level defaults.

        Registering an existing name replaces it. Call this before building any
        layout that uses the name, because `BucketUpload(manager=...)` looks
        the config up when it is constructed.

        Examples:
            >>> mgr.register('videos', bucket='media', prefix='video', mode='relay',
            ...              max_file_size=10 * 2**30, allowed_extensions=['.mp4'])

        Args:
            upload_id: Name the component selects with `upload_id=`.
            bucket: Target bucket.
            prefix: Key prefix.
            mode: `'direct'` or `'relay'`.
            max_file_size: Maximum file size in bytes.
            allowed_extensions: Extension allowlist.
            allowed_mime_types: MIME type allowlist.
            part_size: Fixed part size in bytes.
            presign_expiration: Presigned-URL lifetime in seconds.
            prefix_resolver: Per-request prefix hook for this config,
                `(request, config) -> prefix | None`.

        Returns:
            The stored config.

        Raises:
            ValueError: Neither this call nor the manager sets a bucket.
        """
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
                'prefix_resolver': prefix_resolver,
            }.items() if value is not None
        }
        cfg = replace(self._defaults, upload_id = upload_id, **overrides)
        if not cfg.bucket:
            raise ValueError(f'upload config {upload_id!r} has no bucket (set one here or on the manager)')
        self._configs[upload_id] = cfg
        return cfg

    def get_config(self, upload_id: str) -> UploadConfig:
        """Return the config registered under `upload_id`.

        Raises:
            KeyError: No config by that name; the message lists the known names.
        """
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
        bp.register_error_handler(BotoCoreError, self._handle_botocore_error)

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
        # The store answered with an error. Only the code goes to the browser;
        # the full message (which can name buckets/ARNs) stays in the server log.
        code = err.response.get('Error', {}).get('Code', 'S3Error')
        logger.warning('dash-bucket-upload: %s %s: %s', flask.request.path, err.operation_name, err)
        return flask.jsonify({'error': f'bucket operation failed: {code}'}), 502

    @staticmethod
    def _handle_botocore_error(err: BotoCoreError):
        # Client-side failures: unreachable endpoint, TLS, timeouts, missing
        # credentials. Without this they surface as a bare 500 (or, after
        # botocore's retries, a reverse-proxy 502 the operator can't trace).
        name = type(err).__name__
        logger.error('dash-bucket-upload: %s: %s: %s', flask.request.path, name, err)
        status = 504 if isinstance(err, (ConnectTimeoutError, ReadTimeoutError)) else 502
        return flask.jsonify({'error': f'bucket request failed: {name}'}), status

    def _json_body(self) -> dict:
        body = flask.request.get_json(silent = True)
        if not isinstance(body, dict):
            raise UploadValidationError('request body must be a JSON object')
        return body

    def _config_for_caller(self, body: dict) -> UploadConfig:
        upload_id = body.get('uploadId')
        if not isinstance(upload_id, str):
            raise UploadValidationError('uploadId is required')
        cfg = self._configs.get(upload_id)
        if cfg is None:
            raise UploadValidationError(f'unknown uploadId {upload_id!r}', status = 404)
        if cfg.prefix_resolver is None:
            return cfg
        prefix = cfg.prefix_resolver(flask.request, cfg)
        # A blank prefix would put every such caller in the bucket root, together.
        if prefix is None or not prefix.strip().strip('/'):
            raise UploadValidationError('no upload prefix for this caller', status = 403)
        return replace(cfg, prefix = prefix)

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
        cfg = self._config_for_caller(body)
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
        cfg = self._config_for_caller(body)
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
        cfg = self._config_for_caller(body)
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
        cfg = self._config_for_caller(body)
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
        cfg = self._config_for_caller(body)
        key = self._checked_key(cfg, body)
        s3_upload_id = self._s3_upload_id_from(body)
        self._s3.abort_multipart_upload(Bucket = cfg.bucket, Key = key, UploadId = s3_upload_id)
        return flask.jsonify({'aborted': True})
