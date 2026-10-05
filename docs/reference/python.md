# Python API

Everything public is importable from the package root:

```python
from dash_bucket_upload import BucketUpload, BucketUploadManager, UploadConfig
```

`BucketUploadBase` is also exported. It is the auto-generated Dash component
class that `BucketUpload` wraps, taking camelCase props and no `manager=`.
You only need it in code that builds layouts without a manager; see
[Component props](component-props.md).

::: dash_bucket_upload.BucketUploadManager

::: dash_bucket_upload.UploadConfig

::: dash_bucket_upload.BucketUpload
    options:
      members: false
      inherited_members: false
