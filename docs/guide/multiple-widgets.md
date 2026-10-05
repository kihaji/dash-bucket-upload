# Multiple widgets and limits

## Upload configs

A manager holds named **upload configs** (`UploadConfig`). Each one sets a bucket,
prefix, transport and limits. A component picks a config with `upload_id=`
(default `'default'`).

The manager's constructor arguments do two jobs:

- They become the **defaults** that every `register()` call inherits.
- If you pass `bucket=`, they also register the `'default'` config.

```python
mgr = BucketUploadManager(
    app,
    endpoint_url = 'http://localhost:9000', access_key = '...', secret_key = '...',
    bucket = 'uploads',          # registers 'default'
    prefix = 'incoming',
    max_file_size = 2 * 2**30,   # inherited by every config below
)

mgr.register('videos', bucket = 'media', prefix = 'video', mode = 'relay',
             max_file_size = 10 * 2**30, allowed_extensions = ['.mp4', '.mkv'])
mgr.register('avatars', prefix = 'avatars', max_file_size = 5 * 2**20,
             allowed_mime_types = ['image/png', 'image/jpeg'])

app.layout = html.Div([
    BucketUpload(id = 'docs', manager = mgr),                           # uploads/incoming/...
    BucketUpload(id = 'videos', manager = mgr, upload_id = 'videos'),   # media/video/...
    BucketUpload(id = 'avatar', manager = mgr, upload_id = 'avatars',   # uploads/avatars/...
                 multiple = False),
])
```

Several components can share one config. Each keeps its own `uploadedFiles`.

!!! warning "Register before building the layout"
    `BucketUpload(manager=mgr, upload_id='videos')` looks the config up when the
    component is constructed and raises `KeyError` if it isn't registered yet.
    Call `register()` first.

    If you pass no `bucket` to the constructor, no `'default'` config exists and
    `BucketUpload(manager=mgr)` without an `upload_id` raises `KeyError`.

## Limits and validation

The server validates every upload in `/create` before anything reaches the
bucket:

| Check | Config field | Rejection |
|---|---|---|
| File size | `max_file_size` | HTTP 413 |
| Extension | `allowed_extensions` | HTTP 400 |
| MIME type | `allowed_mime_types` | HTTP 400 |
| Filename | always | HTTP 400 for empty names, `.`/`..`, or names over 512 bytes of UTF-8 |

The failure reaches the browser as a [`lastError`](callbacks.md#lasterror-show-failures)
with `phase: 'create'`.

With `manager=`, the component mirrors two of these limits in the browser for
instant feedback:

- `max_file_size` becomes the component's `max_file_size`. Oversized files are
  rejected before any request (`phase: 'validate'`).
- `allowed_extensions` becomes the file picker's `accept` filter.

Pass `max_file_size=` or `accept=` to the component to override what it shows;
the server's limits still apply.

!!! note "MIME types are the browser's guess"
    The browser reports a MIME type based on the file extension and the
    operating system's type registry. Files it can't classify are sent as
    `application/octet-stream`. Use `allowed_extensions` for predictable
    filtering, and inspect file contents server-side if the type matters for
    security.

## Filenames and keys

Keys are `<prefix>/<uuid4>/<filename>`:

- The UUID folder makes every key unique, so uploading `report.pdf` twice
  creates two objects.
- The filename is the original basename with directory parts (both `/` and `\`)
  and control characters stripped. Spaces and non-ASCII letters are kept.
- A leading or trailing `/` on `prefix` is ignored. An empty prefix puts the
  UUID folder at the bucket root.

### Custom keys

`key_generator` replaces the default naming:

```python
import datetime
import uuid

def dated_keys(cfg, filename):
    return f'{cfg.prefix}/{uuid.uuid4()}/{datetime.date.today():%Y%m%d}-{filename}'

BucketUploadManager(app, ..., key_generator = dated_keys)
```

!!! danger "Custom keys must keep the default shape"
    The routes are stateless. After `/create`, every request is checked against
    the pattern `<prefix>/<uuid4>/<one path segment>`, and keys that don't match
    are refused with HTTP 403 (`key does not belong to this upload
    configuration`). A generator may change the final segment but must keep the
    prefix and UUID folder, and must not add `/` to the filename part.

    To organize objects differently, copy them in your `lastUploadedBatch`
    callback instead.

## Several managers on one app

One manager can serve any number of configs, so you rarely need two. If you do
(for example, two stores with different credentials), give each its own
`url_prefix`:

```python
aws = BucketUploadManager(app, bucket = 'archive', url_prefix = '/upload-aws')
lab = BucketUploadManager(app, endpoint_url = 'http://minio:9000', ..., bucket = 'raw',
                          url_prefix = '/upload-lab')

BucketUpload(id = 'a', manager = aws)
BucketUpload(id = 'b', manager = lab)
```

Two managers with the same `url_prefix` fail at startup, because Flask won't
register two blueprints with the same name.
