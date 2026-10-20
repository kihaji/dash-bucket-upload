# Callbacks and outputs

`BucketUpload` exposes five read-only props for callbacks. They use camelCase
names, like every Dash component prop.

| Prop | Updates | Contents |
|---|---|---|
| `lastUploadedBatch` | once per completed drop or selection | the batch's successful files |
| `uploadedFiles` | once per completed batch | every successful file so far, cumulative |
| `isUploading` | when uploading starts or stops | `True` while any file is pending or in flight |
| `progress` | throttled, about 4 times a second | per-file progress for custom UI |
| `lastError` | on a failure or rejection | the most recent error |

## `lastUploadedBatch`: react to new uploads

This is the prop to use as a callback `Input`. A *batch* is one drop or one
file-picker selection. The prop is set once, when every file in the batch has
finished (successfully, with an error, or canceled), and contains only that
batch's **successful** files:

```python
[{'bucket': str, 'key': str, 'filename': str, 'size': int, 'etag': str, 'status': 'done'}]
```

- `key` is the object key: `<prefix>/<uuid4>/<filename>`.
- `filename` is the sanitized original name (path components and control
  characters removed).
- `size` is read back from the bucket with `HeadObject`, so it is trustworthy.

```python
@app.callback(
    Output('table', 'data'),
    Input('up', 'lastUploadedBatch'),
    State('table', 'data'),
    prevent_initial_call = True,
)
def add_rows(batch, rows):
    return (rows or []) + [{'name': f['filename'], 'bytes': f['size'], 'key': f['key']} for f in batch]
```

!!! note "A batch where every file fails"
    The prop is still set, to an empty list. Guard with `if not batch` if your
    callback can't handle that.

## `uploadedFiles`: everything so far

Same entry shape, accumulated for the life of the component (it resets when the
page reloads). Most useful as a `State`, for example to submit a form that
references all uploaded files:

```python
@app.callback(
    Output('status', 'children'),
    Input('submit', 'n_clicks'),
    State('up', 'uploadedFiles'),
    prevent_initial_call = True,
)
def submit(_, files):
    keys = [f['key'] for f in files or []]
    save_submission(keys)
    return f'Submitted {len(keys)} file(s).'
```

## `isUploading`: lock the UI during uploads

```python
@app.callback(Output('submit', 'disabled'), Input('up', 'isUploading'))
def lock_submit(uploading):
    return bool(uploading)
```

## `progress`: custom progress UI

A dict keyed by an internal file ID (opaque; don't parse it):

```python
{
    'f3': {
        'filename': 'video.mp4',
        'size': 2147483648,
        'loaded': 536870912,
        'percent': 25,
        'speedBps': 41943040,       # bytes per second, smoothed
        'status': 'uploading',      # pending | uploading | done | error | canceled
    },
}
```

Hide the built-in list with `show_file_list=False` and render your own:

```python
BucketUpload(id = 'up', manager = mgr, show_file_list = False)

@app.callback(Output('bars', 'children'), Input('up', 'progress'))
def bars(progress):
    return [
        html.Div([
            html.Span(f"{p['filename']}: {p['percent']}%"),
            html.Progress(value = p['percent'], max = 100),
        ])
        for p in (progress or {}).values()
    ]
```

!!! warning "Keep `progress` callbacks cheap"
    It fires about four times a second per component while uploading. Don't use
    it to trigger database writes or other heavy work; use `lastUploadedBatch`
    for that.

    For progress UI with no server round-trip at all, use a
    [clientside callback](https://dash.plotly.com/clientside-callbacks).

## `lastError`: show failures

```python
{'filename': 'big.iso', 'message': 'file exceeds the maximum size of 1073741824 bytes', 'phase': 'validate'}
```

`phase` says where the upload failed:

| Phase | Meaning |
|---|---|
| `validate` | Rejected in the browser before uploading (too large for `max_file_size`) |
| `create` | The server refused or failed to start the upload: validation, auth or bucket error |
| `part` | A part upload failed after all retries |
| `complete` | Finishing the multipart upload failed |

`message` is the server's `error` text when the server answered with JSON (see
[HTTP routes](../reference/http-api.md#errors)), otherwise a generic message
such as `PUT failed with status 502`.

```python
@app.callback(Output('alert', 'children'), Output('alert', 'is_open'), Input('up', 'lastError'), prevent_initial_call = True)
def show_error(err):
    return f"{err['filename']}: {err['message']}", True
```

!!! note "Only the most recent error is kept"
    If several files in a batch fail, `lastError` holds the last one. The
    built-in file list shows each file's status individually.

## Resetting the widget

To put the widget back to how it looked when the page loaded, typically as part
of a larger "clear form" or "start over" action, return `BucketUpload.reset()`
to its `resetKey` prop:

```python
@app.callback(
    Output('up', 'resetKey'),
    Output('project', 'value'),
    Output('notes', 'value'),
    Input('start-over', 'n_clicks'),
    prevent_initial_call = True,
)
def start_over(_):
    return BucketUpload.reset(), None, ''
```

A reset:

- clears the built-in file list and progress bars;
- sets `uploadedFiles`, `lastUploadedBatch`, `progress` and `lastError` back to
  `None`, and `isUploading` to `False`;
- cancels uploads still in progress, aborting their incomplete multipart
  uploads in the bucket.

For a complete app, see `examples/reset.py` in the repository.

Files that **finished** uploading are not touched; they stay in the bucket. To
delete them as part of the reset, do it in the same callback with your own S3
client (read the keys from `State('up', 'uploadedFiles')`).

`BucketUpload.reset()` returns a new random token on every call. The component
resets only when `resetKey` *changes*, so don't return a constant.

!!! note "Reset fires your output callbacks"
    Setting the outputs back to `None` triggers callbacks that use them as
    `Input`, with `None` as the value. Callbacks that already guard with
    `if not batch:` need no change.

## Writing to component props

Most props besides the outputs can be updated from callbacks like any Dash
component's. A common pattern is disabling the widget until a form is valid:

```python
@app.callback(Output('up', 'disabled'), Input('project', 'value'))
def gate(project):
    return not project
```

Changing `uploadId`, `apiPath`, `maxConcurrency` or `maxFileSize` while files
are uploading cancels those uploads, because the component builds a new upload
engine for the new settings. Their rows show as canceled; finished rows stay.
