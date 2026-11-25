"""S3-compatible blob store (MinIO locally, a private bucket when deployed)."""

from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from atlas.providers.base import BlobInfo
from atlas.settings import Settings


class S3BlobStore:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def ensure_bucket(self) -> None:
        """Create the private bucket if it is missing. Used in local development."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        body: bytes = self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        return body

    def head(self, key: str) -> BlobInfo | None:
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError:
            return None
        return BlobInfo(bytes=response["ContentLength"], content_type=response.get("ContentType"))

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def download_to(self, key: str, path: Path) -> None:
        self._client.download_file(self._bucket, key, str(path))

    def upload_from(self, path: Path, key: str, content_type: str) -> None:
        self._client.upload_file(
            str(path), self._bucket, key, ExtraArgs={"ContentType": content_type}
        )

    def signed_upload_url(self, key: str, content_type: str, ttl_seconds: int) -> str:
        url: str = self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=ttl_seconds,
        )
        return url

    def signed_download_url(self, key: str, ttl_seconds: int) -> str:
        url: str = self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=ttl_seconds
        )
        return url
