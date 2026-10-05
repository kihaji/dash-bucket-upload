# S3-compatible stores

The manager speaks the S3 protocol, using boto3 purely as a protocol library.
Nothing assumes AWS: point `endpoint_url` at any S3-compatible store and pass
its access/secret key pair. If `aws s3api` or MinIO's `mc` works against a
store, this package does too.

## Connection parameters

The parameters use provider-neutral names. The boto3 spellings are accepted as
aliases, but passing both spellings of the same parameter raises `ValueError`.

| Parameter | boto3 alias | Purpose |
|---|---|---|
| `endpoint_url` | | Store URL. Omit for AWS S3. |
| `access_key` | `aws_access_key_id` | Access key ID |
| `secret_key` | `aws_secret_access_key` | Secret key |
| `session_token` | `aws_session_token` | Temporary-credential token |
| `region` | `region_name` | Signing region |
| `addressing_style` | | `'path'`, `'virtual'` or `'auto'` |
| `signature_version` | | Signing version, default `'s3v4'` |

With no credentials at all, boto3's normal resolution chain runs: environment
variables, shared config files, then instance, ECS or IRSA roles.

For anything not covered here there are three escape hatches, applied in this
order of precedence:

1. `s3_client=`: a ready-made boto3 S3 client. Every connection parameter is
   ignored.
2. `boto3_session=`: a `boto3.Session` (for example, one with a named profile).
3. `botocore_config=`: a `botocore.config.Config` merged over the defaults.

## Per-store setup

=== "AWS S3"

    ```python
    BucketUploadManager(app, region = 'eu-west-1', bucket = 'uploads')
    ```

    Omit `endpoint_url` and the credentials to use the AWS credential chain.
    `region` **must** match the bucket's region, or every request fails with
    `AuthorizationHeaderMalformed` or `PermanentRedirect`.

    IAM permissions needed on `arn:aws:s3:::uploads/*`:

    - `s3:PutObject` (creating, uploading parts of and completing a multipart upload)
    - `s3:AbortMultipartUpload`
    - `s3:GetObject` (the size check after completion uses `HeadObject`)

    If the bucket uses SSE-KMS default encryption, the role also needs
    `kms:GenerateDataKey` and `kms:Decrypt` on the key.

=== "MinIO"

    ```python
    BucketUploadManager(
        app,
        endpoint_url = 'https://minio.example.com:9000',
        access_key = '...',
        secret_key = '...',
        bucket = 'uploads',
    )
    ```

    Use root credentials or, better, a service account limited to the bucket.
    Path-style addressing is applied automatically.

=== "Ceph RGW"

    ```python
    BucketUploadManager(
        app,
        endpoint_url = 'https://rgw.example.com',
        access_key = '...',
        secret_key = '...',
        bucket = 'uploads',
    )
    ```

    Create S3 keys with `radosgw-admin user create --uid=dash --display-name=dash`.

=== "OpenStack Swift"

    Requires the `s3api` middleware on the Swift proxy.

    ```python
    BucketUploadManager(
        app,
        endpoint_url = 'https://swift.example.com',
        access_key = '...',          # from: openstack ec2 credentials create
        secret_key = '...',
        region = 'RegionOne',        # match the Keystone region if SigV4 checks are strict
        bucket = 'uploads',          # a Swift container
    )
    ```

    Multipart uploads are stored as SLO segments and follow the same
    5 MiB minimum part rule.

=== "Other stores"

    ```python
    BucketUploadManager(
        app,
        endpoint_url = 'https://s3.example.com',
        access_key = '...',
        secret_key = '...',
        addressing_style = 'virtual',   # only if the store uses wildcard DNS for buckets
        bucket = 'uploads',
    )
    ```

## Timeouts and retries

The client the manager builds uses these defaults:

| Setting | Default | Why |
|---|---|---|
| `connect_timeout` | 5 s | Fail fast when the store is unreachable |
| `retries` | 3 total attempts, `standard` mode | Worst case about 18 s, under gunicorn's 30 s worker timeout |
| `read_timeout` | 60 s (botocore default) | Left long so slow relay part uploads aren't cut off |

Override any of them with `botocore_config`; your values win:

```python
from botocore.config import Config

BucketUploadManager(
    app, ...,
    botocore_config = Config(
        connect_timeout = 10,
        read_timeout = 120,
        retries = {'total_max_attempts': 5, 'mode': 'adaptive'},
        proxies = {'https': 'http://egress-proxy:3128'},
    ),
)
```

!!! warning "A `botocore_config` is merged, not replaced"
    Only the fields you set override the defaults. To remove the short connect
    timeout you must set `connect_timeout` explicitly.

## TLS with a private CA

boto3 validates certificates against `certifi` by default. For a store with an
internal CA, either set `AWS_CA_BUNDLE=/path/to/ca.pem` in the environment, or
build the client yourself:

```python
import boto3

client = boto3.client(
    's3',
    endpoint_url = 'https://minio.internal:9000',
    aws_access_key_id = '...',
    aws_secret_access_key = '...',
    verify = '/etc/ssl/internal-ca.pem',
)
BucketUploadManager(app, s3_client = client, bucket = 'uploads')
```

In direct mode the *browser* also connects to the store, so the CA must be
trusted by your users' browsers as well.
