# Production deployment

## Checklist

- [ ] Gate the routes with [`auth_check`](#authentication).
- [ ] Set `max_file_size`, plus `allowed_extensions` where it makes sense.
- [ ] Add a bucket lifecycle rule that [aborts incomplete multipart uploads](#abandoned-uploads).
- [ ] Direct mode: configure [bucket CORS](transports.md#bucket-cors) with your real origin and `ExposeHeaders: ETag`.
- [ ] Relay mode: raise [reverse-proxy body limits](#reverse-proxies) above the part size.
- [ ] Make sure [logging](#logging) from `dash_bucket_upload` reaches your logs.
- [ ] Give the bucket credentials only the permissions they need (see [S3-compatible stores](stores.md)).

## Authentication

The upload routes are **open by default**: anyone who can reach the Dash server
can upload to the bucket. Pass `auth_check`, a function that receives the
`flask.Request` and returns `True` to allow it. It runs before every route;
returning `False` answers HTTP 403.

=== "Flask-Login"

    ```python
    from flask_login import current_user

    BucketUploadManager(app, ..., auth_check = lambda request: current_user.is_authenticated)
    ```

=== "dash-auth"

    ```python
    import flask

    # dash-auth BasicAuth protects every Flask route, including the upload routes,
    # once it is set up on the app. auth_check adds per-user rules on top.
    UPLOADERS = {'alice', 'bob'}

    BucketUploadManager(app, ..., auth_check = lambda request: request.authorization is not None
                        and request.authorization.username in UPLOADERS)
    ```

=== "Header or token"

    ```python
    import hmac
    import os

    TOKEN = os.environ['UPLOAD_TOKEN']

    def check(request):
        return hmac.compare_digest(request.cookies.get('upload_token', ''), TOKEN)

    BucketUploadManager(app, ..., auth_check = check)
    ```

The browser requests carry the page's cookies, so session-based auth works
without extra setup.

!!! note "Bucket credentials never reach the browser"
    In direct mode the browser only receives presigned URLs, each valid for one
    part of one upload for `presign_expiration` seconds (default one hour).
    Lower it if your threat model needs to, but keep it longer than the time a
    single part can take on your slowest users' connections; expired URLs are
    refreshed automatically.

## Abandoned uploads

When a user closes the tab mid-upload, the widget can't abort the multipart
upload. Its parts stay in the bucket, invisible in listings, and are billed as
storage until removed. Add a lifecycle rule as the backstop:

=== "AWS S3"

    ```json
    {
      "Rules": [{
        "ID": "abort-incomplete-multipart",
        "Status": "Enabled",
        "Filter": {"Prefix": ""},
        "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}
      }]
    }
    ```

    `aws s3api put-bucket-lifecycle-configuration --bucket uploads --lifecycle-configuration file://lifecycle.json`

=== "MinIO"

    Save the same JSON as `lifecycle.json`, then:

    `mc ilm import local/uploads < lifecycle.json`

Cancels, failures and component unmounts already abort server-side; the rule
only catches what the browser can't.

## Workers and servers

The routes are stateless, so any number of gunicorn workers or replicas behind a
load balancer work without sticky sessions.

**Direct mode** requests are small and fast. Default worker settings are fine.

**Relay mode** holds a worker for the duration of every part upload. With the
default concurrency of up to 6 parts per browser, a few active users can occupy
many workers. Use threaded or async workers and allow for the time a part
upload takes:

```bash
gunicorn app:server --workers 4 --threads 8 --timeout 120
```

The manager's bucket client times out connections after 5 seconds and makes at
most 3 attempts, so an unreachable store fails in about 18 seconds, inside
gunicorn's default 30-second worker timeout. See
[Timeouts and retries](stores.md#timeouts-and-retries) to tune this.

## Reverse proxies

Upload routes live under `url_prefix` (default `/dash-bucket-upload`) on the
same host as the Dash app, so a proxy that serves Dash serves them too.

In **relay mode** each part is one `PUT` request of up to the part size: 16 MiB
for files up to about 150 GB, larger above that. Raise body limits accordingly:

=== "nginx"

    ```nginx
    location /dash-bucket-upload/ {
        proxy_pass http://dash_upstream;
        client_max_body_size 64m;
        proxy_request_buffering off;    # stream parts instead of spooling them to disk first
        proxy_read_timeout 120s;
    }
    ```

=== "Apache"

    ```apache
    <Location /dash-bucket-upload/>
        LimitRequestBody 67108864
        ProxyPass http://127.0.0.1:8050/dash-bucket-upload/ timeout=120
    </Location>
    ```

If your Flask app sets `MAX_CONTENT_LENGTH`, keep it above the part size too.

For **both modes**, make the proxy's upstream timeout longer than the bucket
client's worst case (about 18 seconds by default). Otherwise a slow or
unreachable store shows up as a proxy-generated 502 or 504 instead of the
library's JSON error. See [Troubleshooting](troubleshooting.md#502-or-504-from-create).

### Serving Dash under a path prefix

The manager mounts its routes at `url_prefix` on the Flask server; it does not
read Dash's pathname settings. Which value to change depends on whether the
proxy strips the prefix:

=== "Flask serves the prefix"

    The app uses `url_base_pathname` (or `routes_pathname_prefix`), and Flask
    itself answers under `/tools/`. Put the routes there too:

    ```python
    app = Dash(__name__, url_base_pathname = '/tools/')
    mgr = BucketUploadManager(app, ..., url_prefix = '/tools/dash-bucket-upload')
    BucketUpload(id = 'up', manager = mgr)
    ```

=== "The proxy strips the prefix"

    The app uses only `requests_pathname_prefix`: the browser requests
    `/tools/...`, the proxy removes `/tools`, and Flask sees `/...`. Keep the
    routes where Flask sees them and tell the component the browser-facing path:

    ```python
    app = Dash(__name__, requests_pathname_prefix = '/tools/')
    mgr = BucketUploadManager(app, ...)                       # Flask route: /dash-bucket-upload
    BucketUpload(id = 'up', manager = mgr,
                 api_path = '/tools/dash-bucket-upload')      # browser URL
    ```

## Logging

Bucket failures are logged on the `dash_bucket_upload.manager` logger, with the
store's full error message. The browser only receives the error code, because
the full message can include bucket names or ARNs.

| Level | When |
|---|---|
| `WARNING` | The store rejected a request (`AccessDenied`, `NoSuchBucket`, …) |
| `ERROR` | The store couldn't be reached or the client failed (connection refused, TLS, timeout, missing credentials) |

Gunicorn and most hosts show these with no configuration. If yours doesn't:

```python
import logging

logging.basicConfig(level = logging.INFO)
logging.getLogger('dash_bucket_upload').setLevel(logging.WARNING)
```
