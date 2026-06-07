"""Cloudflare R2 storage — S3-compatible asset backend."""
from __future__ import annotations

from app.core.config import get_settings


def get_r2_client():
    settings = get_settings()
    if not settings.r2_configured:
        return None

    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def build_public_url(storage_key: str) -> str:
    settings = get_settings()
    base = settings.r2_public_url.rstrip("/")
    if base:
        return f"{base}/{storage_key}"
    return storage_key


def upload_bytes(storage_key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    client = get_r2_client()
    if not client:
        raise RuntimeError("R2 not configured")

    settings = get_settings()
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=storage_key,
        Body=data,
        ContentType=content_type,
    )
    return build_public_url(storage_key)


def list_objects(prefix: str, max_keys: int = 50) -> list[dict]:
    client = get_r2_client()
    if not client:
        return []

    settings = get_settings()
    resp = client.list_objects_v2(
        Bucket=settings.r2_bucket_name,
        Prefix=prefix,
        MaxKeys=max_keys,
    )
    return [
        {
            "key": obj["Key"],
            "size_bytes": obj.get("Size", 0),
            "public_url": build_public_url(obj["Key"]),
        }
        for obj in resp.get("Contents", [])
    ]
