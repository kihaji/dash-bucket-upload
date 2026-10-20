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

<!-- Not dash_bucket_upload.BucketUpload: statically that path is the generated
     BucketUpload.py *module* (the runtime import rebinds it to the class), so
     mkdocstrings would render an empty module. -->
::: dash_bucket_upload.component.BucketUpload
    options:
      members: [reset]
      inherited_members: false
      show_bases: false
