"""Object-key generation and validation, plus the part-size computation shared
with the JS engine (src/lib/engine/partSize.js mirrors these constants)."""
from __future__ import annotations

import math
import re
import uuid

MiB = 1024 * 1024
DEFAULT_MIN_PART = 16 * MiB
# S3's per-part maximum. Parts are streamed from disk via Blob.slice in the
# browser and a bounded spool on the server, so a large cap costs no memory.
MAX_PART = 5 * 1024 * MiB
# S3 allows 10,000 parts; leave headroom so rounding never crosses the limit.
TARGET_MAX_PARTS = 9500

_UUID_RE = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def compute_part_size(file_size: int, override: int | None = None) -> int:
    """Part size for a multipart upload: large enough to stay under the S3
    10,000-part cap, clamped to [16 MiB, 512 MiB]."""
    if override:
        return override
    needed = math.ceil(file_size / TARGET_MAX_PARTS) if file_size > 0 else DEFAULT_MIN_PART
    rounded = math.ceil(needed / MiB) * MiB
    return min(max(rounded, DEFAULT_MIN_PART), MAX_PART)


def generate_key(prefix: str, filename: str) -> str:
    """Collision-free object key: <prefix>/<uuid4>/<filename>. The uuid folder
    guarantees uniqueness while preserving the original filename."""
    parts = [prefix.strip('/'), str(uuid.uuid4()), filename]
    return '/'.join(p for p in parts if p)


def key_matches(prefix: str, key: str) -> bool:
    """Whether `key` has the shape this widget's key_generator produces for
    `prefix`. Non-create routes use this to reject keys outside the widget's
    namespace — it is what keeps the routes stateless but bounded."""
    clean_prefix = prefix.strip('/')
    prefix_re = re.escape(clean_prefix) + '/' if clean_prefix else ''
    return re.fullmatch(f'{prefix_re}{_UUID_RE}/[^/]+', key) is not None
