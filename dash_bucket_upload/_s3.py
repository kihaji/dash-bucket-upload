"""boto3 client construction for S3-compatible endpoints (AWS, MinIO, Ceph)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config

if TYPE_CHECKING:
    from botocore.client import BaseClient


def build_s3_client(
    *,
    endpoint_url: str | None = None,
    region_name: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
    boto3_session: Any = None,
    botocore_config: Config | None = None,
) -> 'BaseClient':
    """Create the S3 client used for presigning and relaying.

    Presigned URLs require SigV4. When a custom endpoint is set (MinIO/Ceph),
    path-style addressing is the default because virtual-host style needs
    wildcard DNS that self-hosted deployments rarely have; pass a
    `botocore_config` with `s3={'addressing_style': 'virtual'}` to override.
    """
    defaults: dict[str, Any] = {'signature_version': 's3v4'}
    if endpoint_url is not None:
        defaults['s3'] = {'addressing_style': 'path'}
    config = Config(**defaults)
    if botocore_config is not None:
        config = config.merge(botocore_config)

    session = boto3_session or boto3.Session(
        aws_access_key_id = aws_access_key_id,
        aws_secret_access_key = aws_secret_access_key,
        aws_session_token = aws_session_token,
        region_name = region_name,
    )
    return session.client('s3', endpoint_url = endpoint_url, config = config)
