# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component, _explicitize_args

ComponentSingleType = typing.Union[str, int, float, Component, None]
ComponentType = typing.Union[
    ComponentSingleType,
    typing.Sequence[ComponentSingleType],
]

NumberType = typing.Union[
    typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex
]


class BucketUpload(Component):
    """A BucketUpload component.
BucketUpload: a dcc.Upload look-alike that stores files in an S3-compatible
bucket instead of pushing bytes through a Dash callback.

Files upload either directly from the browser to the bucket (presigned
multipart URLs) or via a streaming relay route on the Dash server — the
server decides per upload_id. Either way, callbacks receive only the bucket
location metadata, never the file contents.

Keyword arguments:

- children (a list of or a singular dash component, string or number; optional):
    Custom drop-zone content (replaces \"Drag and Drop or Select
    Files\").

- id (string; optional):
    The ID used to identify this component in Dash callbacks.

- accept (string; optional):
    File-picker accept filter, e.g. \".csv,.parquet\" or \"image/*\".

- apiPath (string; default '/dash-bucket-upload'):
    Base path of the server routes registered by BucketUploadManager.
    Set automatically when the component is constructed with
    `manager=`.

- className (string; optional):
    CSS class of the drop zone.

- disabled (boolean; default False):
    Disable the drop zone and file picker.

- isUploading (boolean; optional):
    (Output) True while any file is uploading.

- lastError (dict; optional):
    (Output) Most recent upload error: {filename, message, phase}.

- lastUploadedBatch (list of dicts; optional):
    (Output) Files from the most recently completed drop/selection
    batch, set once when every file in the batch has finished. The
    ergonomic callback Input: fires exactly once per batch with only
    the new files.

- maxConcurrency (number; default 6):
    Maximum number of part uploads in flight across all files.

- maxFileSize (number; optional):
    Client-side maximum file size in bytes. Files over the limit are
    rejected before any upload starts (the server enforces its own
    limit regardless).

- multiple (boolean; default True):
    Allow selecting/dropping more than one file at a time.

- progress (dict; optional):
    (Output) Per-file upload progress keyed by an internal file id:
    {filename, size, loaded, percent, speedBps, status}. Throttled to
    ~4 updates/second. Intended for custom progress UI, not as a
    general callback trigger.

- resetKey (string | number; optional):
    Change this to any new value to reset the component to its initial
    state: in-flight uploads are cancelled, the file list is cleared,
    and uploadedFiles, lastUploadedBatch, progress and lastError
    return to None (isUploading to False). Objects already uploaded to
    the bucket are not touched. From Python, return
    `BucketUpload.reset()` to this prop.

- showFileList (boolean; default True):
    Show the built-in per-file progress list under the drop zone. Set
    False to build custom progress UI from the `progress` prop.

- styleActive (dict; optional):
    Additional style applied while files are dragged over the drop
    zone.

- styleDisabled (dict; optional):
    Additional style applied while the component is disabled.

- uploadId (string; default 'default'):
    Name of the server-side upload configuration to use (registered on
    the BucketUploadManager). Links this widget to a
    bucket/prefix/mode.

- uploadedFiles (list of dicts; optional):
    (Output) All files uploaded by this component instance, cumulative
    across its lifetime. List of {bucket, key, filename, size, etag,
    status}."""
    _children_props: typing.List[str] = []
    _base_nodes = ['children']
    _namespace = 'dash_bucket_upload'
    _type = 'BucketUpload'


    def __init__(
        self,
        children: typing.Optional[ComponentType] = None,
        id: typing.Optional[typing.Union[str, dict]] = None,
        apiPath: typing.Optional[str] = None,
        uploadId: typing.Optional[str] = None,
        multiple: typing.Optional[bool] = None,
        accept: typing.Optional[str] = None,
        maxFileSize: typing.Optional[NumberType] = None,
        disabled: typing.Optional[bool] = None,
        maxConcurrency: typing.Optional[NumberType] = None,
        showFileList: typing.Optional[bool] = None,
        style: typing.Optional[typing.Any] = None,
        className: typing.Optional[str] = None,
        styleActive: typing.Optional[dict] = None,
        styleDisabled: typing.Optional[dict] = None,
        resetKey: typing.Optional[typing.Union[str, NumberType]] = None,
        uploadedFiles: typing.Optional[typing.Sequence[dict]] = None,
        lastUploadedBatch: typing.Optional[typing.Sequence[dict]] = None,
        isUploading: typing.Optional[bool] = None,
        progress: typing.Optional[dict] = None,
        lastError: typing.Optional[dict] = None,
        **kwargs
    ):
        self._prop_names = ['children', 'id', 'accept', 'apiPath', 'className', 'disabled', 'isUploading', 'lastError', 'lastUploadedBatch', 'maxConcurrency', 'maxFileSize', 'multiple', 'progress', 'resetKey', 'showFileList', 'style', 'styleActive', 'styleDisabled', 'uploadId', 'uploadedFiles']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['children', 'id', 'accept', 'apiPath', 'className', 'disabled', 'isUploading', 'lastError', 'lastUploadedBatch', 'maxConcurrency', 'maxFileSize', 'multiple', 'progress', 'resetKey', 'showFileList', 'style', 'styleActive', 'styleDisabled', 'uploadId', 'uploadedFiles']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args if k != 'children'}

        super(BucketUpload, self).__init__(children=children, **args)

setattr(BucketUpload, "__init__", _explicitize_args(BucketUpload.__init__))
