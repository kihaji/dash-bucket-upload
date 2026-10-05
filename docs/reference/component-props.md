# Component props

`BucketUpload` accepts snake_case keyword arguments in Python. In callbacks,
props use their camelCase names (`Output('up', 'disabled')`,
`Input('up', 'lastUploadedBatch')`).

## Inputs

| Python argument | Callback prop | Type | Default | Description |
|---|---|---|---|---|
| `id` | `id` | `str` | | Component ID. |
| `manager` | | `BucketUploadManager` | | Wires `apiPath` and mirrors the config's `max_file_size` and `allowed_extensions`. Python-only. |
| `upload_id` | `uploadId` | `str` | `'default'` | Registered config to use. |
| `api_path` | `apiPath` | `str` | manager's `url_prefix` | Browser-facing base URL of the routes. Required without `manager`. |
| `multiple` | `multiple` | `bool` | `True` | Allow several files per drop or selection. |
| `accept` | `accept` | `str` | config's extensions | File-picker filter, e.g. `'.csv,.parquet'` or `'image/*'`. |
| `max_file_size` | `maxFileSize` | `int` | config's limit | Client-side size check in bytes. |
| `disabled` | `disabled` | `bool` | `False` | Disable the drop zone and picker. |
| `max_concurrency` | `maxConcurrency` | `int` | `6` | Part uploads in flight across all files (at most 4 per file). |
| `show_file_list` | `showFileList` | `bool` | `True` | Show the built-in progress list. |
| `style` | `style` | `dict` | | Drop-zone style. |
| `class_name` | `className` | `str` | | Drop-zone CSS class. |
| `style_active` | `styleActive` | `dict` | | Extra style while dragging files over. |
| `style_disabled` | `styleDisabled` | `dict` | | Extra style while disabled. |
| `children` | `children` | component(s) | "Drag and Drop or Select Files" | Drop-zone content. |

## Outputs

Set by the component; read them in callbacks. Details and examples are in
[Callbacks and outputs](../guide/callbacks.md).

| Prop | Type | Description |
|---|---|---|
| `lastUploadedBatch` | `list[dict]` | Successful files of the latest finished batch. |
| `uploadedFiles` | `list[dict]` | All successful files, cumulative. |
| `isUploading` | `bool` | `True` while any file is pending or uploading. |
| `progress` | `dict[str, dict]` | Per-file `{filename, size, loaded, percent, speedBps, status}`. |
| `lastError` | `dict` | `{filename, message, phase}` of the latest failure. |

File entries in `lastUploadedBatch` and `uploadedFiles`:

| Key | Type | Description |
|---|---|---|
| `bucket` | `str` | Bucket the object was written to. |
| `key` | `str` | Object key, `<prefix>/<uuid4>/<filename>`. |
| `filename` | `str` | Sanitized original filename. |
| `size` | `int` | Object size in bytes, read from the bucket. |
| `etag` | `str` | The multipart ETag, quotes included (e.g. `'"…-3"'`). Not an MD5 of the file. |
| `status` | `str` | Always `'done'`. |

## Styling

The drop zone uses inline styles so the component needs no CSS files. Your
`style` is merged over the defaults, `style_active` over that while dragging,
and `style_disabled` while disabled:

```python
BucketUpload(
    id = 'up',
    manager = mgr,
    style = {'border': '2px dashed #999', 'borderRadius': '12px', 'padding': '48px'},
    style_active = {'borderColor': '#4f46e5', 'background': '#eef2ff'},
    children = html.Div(['Drop datasets here, or ', html.A('browse')]),
)
```

`class_name` works with stylesheets in your app's `assets/` folder, but the
default inline styles take precedence over class rules. Override defaults
through `style`, or use `!important` in your stylesheet.

## Without a manager

When the layout is built where no manager object exists (a separate module or
process), pass `api_path` instead. Use the same `upload_id` the server
registered:

```python
BucketUpload(id = 'up', api_path = '/dash-bucket-upload', upload_id = 'videos')
```

Without `manager`, client-side limits aren't mirrored automatically; pass
`max_file_size` and `accept` yourself if you want instant feedback.
