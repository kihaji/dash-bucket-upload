"""S3-protocol client construction for any S3-compatible object store
(AWS S3, MinIO, Ceph RGW, OpenStack Swift s3api, ...). boto3 is used purely
as the protocol implementation; nothing here assumes AWS itself."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import boto3
from botocore.config import Config

if TYPE_CHECKING:
    from botocore.client import BaseClient


def build_s3_client(
    *,
    endpoint_url: str | None = None,
    region: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    session_token: str | None = None,
    addressing_style: Literal['path', 'virtual', 'auto'] | None = None,
    signature_version: str = 's3v4',
    boto3_session: Any = None,
    botocore_config: Config | None = None,
) -> 'BaseClient':
    """Create the object-store client used for presigning and relaying.

    Presigned URLs require SigV4 on every current store. When a custom
    endpoint is set, path-style addressing is the default because
    virtual-host style needs wildcard DNS that self-hosted deployments
    rarely have; pass `addressing_style='virtual'` to override. Anything
    more exotic can go through `botocore_config` (merged last, wins).
    """
    if addressing_style is None and endpoint_url is not None:
        addressing_style = 'path'
    defaults: dict[str, Any] = {'signature_version': signature_version}
    if addressing_style is not None:
        defaults['s3'] = {'addressing_style': addressing_style}
    config = Config(**defaults)
    if botocore_config is not None:
        config = config.merge(botocore_config)

    session = boto3_session or boto3.Session(
        aws_access_key_id = access_key,
        aws_secret_access_key = secret_key,
        aws_session_token = session_token,
        region_name = region,
    )
    return session.client('s3', endpoint_url = endpoint_url, config = config)
