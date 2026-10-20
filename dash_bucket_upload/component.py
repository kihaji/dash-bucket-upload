"""BucketUpload component wrapper: snake_case kwargs and manager wiring."""
from __future__ import annotations

import uuid
from typing import Any, Optional, Sequence

from .BucketUpload import BucketUpload as _BucketUploadBase
from .manager import BucketUploadManager

# Re-export the base component so __init__.py doesn't need to import from
# .BucketUpload directly, which causes Pyright to shadow the class with the
# BucketUpload.py module name.
BucketUploadBase = _BucketUploadBase


def _accept_from_extensions(extensions: Sequence[str] | None) -> str | None:
    if not extensions:
        return None
    return ','.join(e if e.startswith('.') else f'.{e}' for e in extensions)


class BucketUpload(_BucketUploadBase):
    """Drop-zone upload component that stores files in an S3-compatible bucket.

    Pass the `manager` (a BucketUploadManager registered on the app) and the
    component wires itself to the server routes; `upload_id` selects which
    registered configuration (bucket/prefix/mode/limits) this widget uses.

    Callback-facing props (read-only outputs, camelCase as in any Dash
    component):

    - `lastUploadedBatch`: fires once per completed drop/selection batch with
      the new files, `[{bucket, key, filename, size, etag, status}]`.
    - `uploadedFiles`: same shape, cumulative across the component lifetime.
    - `isUploading`: `True` while any file is in flight.
    - `progress`: per-file progress for custom UI (throttled).
    - `lastError`: `{filename, message, phase}` for the latest failure.

    To clear the widget back to its initial state, return `BucketUpload.reset()`
    to its `resetKey` prop from any callback (see `reset`).

    Examples:
        >>> mgr = BucketUploadManager(app, endpoint_url='http://localhost:9000',
        ...                           bucket='uploads')
        >>> BucketUpload(id='up', manager=mgr)

    Args:
        id: Component ID for callbacks.
        manager: The app's `BucketUploadManager`. Sets `api_path` and mirrors
            the config's `max_file_size` and `allowed_extensions` client-side.
        upload_id: Name of the registered config to use.
        api_path: Base URL of the routes. Only needed without `manager=`, for
            example when the layout is built in a process that has no manager.
        multiple: Allow more than one file per drop or selection.
        accept: File-picker filter such as `'.csv,.parquet'` or `'image/*'`.
            Defaults to the config's `allowed_extensions`.
        max_file_size: Client-side size limit in bytes. Defaults to the
            config's `max_file_size`. The server enforces its own limit
            regardless.
        disabled: Disable the drop zone and file picker.
        max_concurrency: Maximum part uploads in flight across all files
            (default 6; at most 4 per file).
        show_file_list: Show the built-in progress list. Set `False` to build
            your own from the `progress` prop.
        style: Style of the drop zone.
        class_name: CSS class of the drop zone.
        style_active: Extra style while files are dragged over the drop zone.
        style_disabled: Extra style while disabled.
        children: Custom drop-zone content (replaces "Drag and Drop or Select
            Files").
        **kwargs: Passed through to the generated base component (camelCase
            prop names).

    Raises:
        ValueError: Neither `manager` nor `api_path` was given.
        KeyError: `upload_id` is not registered on `manager`.
    """

    def __init__(
        self,
        id: Optional[str] = None,  # noqa: A002 - matches Dash convention
        *,
        manager: BucketUploadManager | None = None,
        upload_id: str = 'default',
        api_path: str | None = None,
        multiple: bool = True,
        accept: str | None = None,
        max_file_size: int | None = None,
        disabled: bool = False,
        max_concurrency: int | None = None,
        show_file_list: bool = True,
        style: dict | None = None,
        class_name: str | None = None,
        style_active: dict | None = None,
        style_disabled: dict | None = None,
        children: Any = None,
        **kwargs: Any,
    ):
        if manager is not None:
            cfg = manager.get_config(upload_id)  # raises early on unknown upload_id
            api_path = api_path or manager.url_prefix
            # Mirror server limits client-side for immediate feedback; the
            # server enforces them regardless.
            if max_file_size is None:
                max_file_size = cfg.max_file_size
            if accept is None:
                accept = _accept_from_extensions(cfg.allowed_extensions)
        elif api_path is None:
            raise ValueError('provide either manager= or api_path=')

        props: dict[str, Any] = {
            'uploadId': upload_id,
            'apiPath': api_path,
            'multiple': multiple,
            'disabled': disabled,
            'showFileList': show_file_list,
        }
        if id is not None:
            props['id'] = id
        if accept is not None:
            props['accept'] = accept
        if max_file_size is not None:
            props['maxFileSize'] = max_file_size
        if max_concurrency is not None:
            props['maxConcurrency'] = max_concurrency
        if style is not None:
            props['style'] = style
        if class_name is not None:
            props['className'] = class_name
        if style_active is not None:
            props['styleActive'] = style_active
        if style_disabled is not None:
            props['styleDisabled'] = style_disabled
        if children is not None:
            props['children'] = children
        props.update(kwargs)

        super().__init__(**props)

    @staticmethod
    def reset() -> str:
        """Value that resets a `BucketUpload` when returned to its `resetKey` prop.

        The component cancels any uploads still in flight (their incomplete
        multipart uploads are aborted), clears the file list, and returns its
        outputs to their initial values: `uploadedFiles`, `lastUploadedBatch`,
        `progress` and `lastError` become `None`, `isUploading` becomes `False`.
        Objects that finished uploading stay in the bucket.

        Each call returns a new unique value, because the component only
        resets when `resetKey` changes.

        Examples:
            >>> @app.callback(Output('up', 'resetKey'), Input('clear', 'n_clicks'),
            ...               prevent_initial_call=True)
            ... def clear(_):
            ...     return BucketUpload.reset()

        Returns:
            A fresh token for `Output(<component id>, 'resetKey')`.
        """
        return uuid.uuid4().hex
