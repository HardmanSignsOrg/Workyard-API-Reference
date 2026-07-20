"""Cloudflare R2 object storage (S3-compatible) for Smart Form photos.

Env (all required for uploads):
  R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET
  R2_PUBLIC_BASE_URL   e.g. https://pub-….r2.dev  (no trailing slash)
"""

from __future__ import annotations

import base64
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

_DATA_URL_RE = re.compile(
    r'^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.+)$',
    re.DOTALL,
)


def r2_configured() -> bool:
    return all(os.environ.get(k) for k in (
        'R2_ACCOUNT_ID',
        'R2_ACCESS_KEY_ID',
        'R2_SECRET_ACCESS_KEY',
        'R2_BUCKET',
        'R2_PUBLIC_BASE_URL',
    ))


def _client():
    import boto3
    from botocore.config import Config

    account = os.environ['R2_ACCOUNT_ID']
    return boto3.client(
        's3',
        endpoint_url=f'https://{account}.r2.cloudflarestorage.com',
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        region_name='auto',
        config=Config(signature_version='s3v4'),
    )


def _public_base() -> str:
    return os.environ['R2_PUBLIC_BASE_URL'].rstrip('/')


def _ext_for(mime: str, filename: str = '') -> str:
    name = (filename or '').lower()
    if name.endswith(('.jpg', '.jpeg')):
        return 'jpg'
    if name.endswith('.png'):
        return 'png'
    if name.endswith('.webp'):
        return 'webp'
    if name.endswith('.gif'):
        return 'gif'
    mime = (mime or '').lower()
    if 'png' in mime:
        return 'png'
    if 'webp' in mime:
        return 'webp'
    if 'gif' in mime:
        return 'gif'
    return 'jpg'


def parse_data_url(data_url: str) -> tuple[bytes, str]:
    m = _DATA_URL_RE.match((data_url or '').strip())
    if not m:
        raise ValueError('content must be a data:…;base64,… URL')
    mime = m.group('mime')
    raw = base64.b64decode(m.group('data'), validate=False)
    if not raw:
        raise ValueError('empty file data')
    return raw, mime


def upload_bytes(
    body: bytes,
    *,
    content_type: str = 'image/jpeg',
    filename: str = '',
    prefix: str = 'final-assembly',
) -> str:
    """Upload bytes to R2; return the public HTTPS URL. Never deletes objects."""
    if not r2_configured():
        raise RuntimeError('R2 is not configured')
    if not body:
        raise ValueError('empty body')
    # Soft cap — keep abuse down; real photos are well under this.
    if len(body) > 25 * 1024 * 1024:
        raise ValueError('file too large (max 25MB)')

    ext = _ext_for(content_type, filename)
    day = datetime.now(timezone.utc).strftime('%Y/%m/%d')
    key = f'{prefix}/{day}/{uuid.uuid4().hex}.{ext}'
    _client().put_object(
        Bucket=os.environ['R2_BUCKET'],
        Key=key,
        Body=body,
        ContentType=content_type or 'application/octet-stream',
    )
    return f'{_public_base()}/{key}'


def upload_data_url(data_url: str, filename: str = '', prefix: str = 'final-assembly') -> str:
    body, mime = parse_data_url(data_url)
    return upload_bytes(body, content_type=mime, filename=filename, prefix=prefix)


def status() -> dict:
    return {
        'enabled': r2_configured(),
        'bucket': os.environ.get('R2_BUCKET') if r2_configured() else None,
        'public_base_url': _public_base() if r2_configured() else None,
    }
