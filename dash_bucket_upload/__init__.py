"""dash-bucket-upload: large-file uploads for Plotly Dash, stored in an
S3-compatible bucket.

A dcc.Upload look-alike (drag-and-drop / file picker) whose files go to a
bucket via S3 multipart upload — either directly from the browser with
presigned URLs, or relayed through a streaming route on the Dash server.
Callbacks receive the bucket location, never the file contents.

Example:
    >>> from dash import Dash
    >>> from dash_bucket_upload import BucketUpload, BucketUploadManager
    >>>
    >>> app = Dash(__name__)
    >>> mgr = BucketUploadManager(app, endpoint_url='http://localhost:9000',
    ...                           access_key='minio', secret_key='minio123',
    ...                           bucket='uploads', prefix='incoming')
    >>> app.layout = BucketUpload(id='up', manager=mgr)
"""
import json
import os as _os
import sys as _sys

import dash as _dash

from .component import BucketUpload as BucketUpload
from .component import BucketUploadBase as BucketUploadBase
from .manager import BucketUploadManager, UploadConfig

__all__ = ['BucketUpload', 'BucketUploadBase', 'BucketUploadManager', 'UploadConfig']

if not hasattr(_dash, '__plotly_dash') and not hasattr(_dash, 'development'):
    print('Dash was not successfully imported. '
          'Make sure you don\'t have a file '
          'named \n"dash.py" in your current directory.', file = _sys.stderr)
    _sys.exit(1)

_basepath = _os.path.dirname(__file__)
_filepath = _os.path.abspath(_os.path.join(_basepath, 'package-info.json'))
with open(_filepath) as f:
    package = json.load(f)

package_name = package['name'].replace(' ', '_').replace('-', '_')
__version__ = package['version']

# The bundle is always served locally from the wheel (never a CDN), which is
# what makes the component airgap-safe.
_js_dist = [
    {
        'relative_package_path': 'dash_bucket_upload.min.js',
        'namespace': package_name,
    }
]

# The source map is excluded from the wheel to keep it small; only declare it
# when present (dev checkouts) so Dash never references a missing file.
if _os.path.exists(_os.path.join(_basepath, 'dash_bucket_upload.min.js.map')):
    _js_dist.append(
        {
            'relative_package_path': 'dash_bucket_upload.min.js.map',
            'namespace': package_name,
            'dynamic': True,
        }
    )

_css_dist = []

# Standard Dash component class attributes for asset registration.
BucketUpload._js_dist = _js_dist  # type: ignore[attr-defined]
BucketUpload._css_dist = _css_dist  # type: ignore[attr-defined]
BucketUploadBase._js_dist = _js_dist  # type: ignore[attr-defined]
BucketUploadBase._css_dist = _css_dist  # type: ignore[attr-defined]
