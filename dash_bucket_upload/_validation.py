"""Server-side upload validation. The client pre-checks size and extension for
UX; these checks are the enforcement boundary."""
from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import UploadConfig

# Strip control characters and path separators; conservative but keeps most
# real-world filenames (spaces, unicode letters, dashes, dots) intact.
_CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f]')


class UploadValidationError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def sanitize_filename(filename: object) -> str:
    """Reduce a client-supplied filename to a safe basename. Raises
    UploadValidationError when nothing safe remains."""
    if not isinstance(filename, str) or not filename:
        raise UploadValidationError('filename is required')
    # Normalize both separators, then take the basename.
    name = posixpath.basename(filename.replace('\\', '/'))
    name = _CONTROL_CHARS.sub('', name).strip()
    if not name or name in ('.', '..'):
        raise UploadValidationError('invalid filename')
    if len(name.encode('utf-8')) > 512:
        raise UploadValidationError('filename too long')
    return name


def validate_upload(cfg: 'UploadConfig', filename: object, size: object, content_type: str | None) -> str:
    """Validate a /create request against the widget's config; returns the
    sanitized filename."""
    name = sanitize_filename(filename)

    if not isinstance(size, int) or size < 0:
        raise UploadValidationError('size must be a non-negative integer')
    if cfg.max_file_size is not None and size > cfg.max_file_size:
        raise UploadValidationError(
            f'file exceeds the maximum size of {cfg.max_file_size} bytes', status = 413)

    if cfg.allowed_extensions is not None:
        allowed = {e.lower() if e.startswith('.') else f'.{e.lower()}' for e in cfg.allowed_extensions}
        ext = posixpath.splitext(name)[1].lower()
        if ext not in allowed:
            raise UploadValidationError(f'file extension {ext or "(none)"} is not allowed')

    if cfg.allowed_mime_types is not None and (
        not content_type or content_type.lower() not in {m.lower() for m in cfg.allowed_mime_types}
    ):
        raise UploadValidationError(f'content type {content_type or "(none)"} is not allowed')

    return name
