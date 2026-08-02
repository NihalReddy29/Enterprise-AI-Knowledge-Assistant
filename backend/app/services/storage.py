"""Abstract storage backend for document files."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings

settings = get_settings()


class StorageBackend(ABC):
    """Interface for file storage operations."""

    @abstractmethod
    def save(self, file_data: bytes, relative_path: str) -> str:
        """Save file and return storage path."""

    @abstractmethod
    def read(self, storage_path: str) -> bytes:
        """Read file contents."""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """Delete a stored file."""

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        """Check if file exists."""

    def generate_path(self, owner_id: int, filename: str, prefix: str = "documents") -> str:
        """Generate a unique storage path for a file."""
        safe_name = Path(filename).name
        return f"{prefix}/{owner_id}/{uuid4().hex}_{safe_name}"


class LocalStorageBackend(StorageBackend):
    """Store files on local filesystem."""

    def __init__(self, base_path: str | None = None) -> None:
        self.base_path = Path(base_path or settings.local_storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _full_path(self, storage_path: str) -> Path:
        return self.base_path / storage_path

    def save(self, file_data: bytes, relative_path: str) -> str:
        full_path = self._full_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(file_data)
        return relative_path

    def read(self, storage_path: str) -> bytes:
        return self._full_path(storage_path).read_bytes()

    def delete(self, storage_path: str) -> None:
        full_path = self._full_path(storage_path)
        if full_path.exists():
            full_path.unlink()

    def exists(self, storage_path: str) -> bool:
        return self._full_path(storage_path).exists()


class S3StorageBackend(StorageBackend):
    """Store files in AWS S3."""

    def __init__(self) -> None:
        self.bucket = settings.aws_s3_bucket
        if not self.bucket:
            raise ValueError("AWS_S3_BUCKET must be set for S3 storage backend")

        client_kwargs: dict = {"region_name": settings.aws_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self.client = boto3.client("s3", **client_kwargs)

    def save(self, file_data: bytes, relative_path: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=relative_path, Body=file_data)
        return relative_path

    def read(self, storage_path: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=storage_path)
        return response["Body"].read()

    def delete(self, storage_path: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=storage_path)
        except ClientError:
            pass

    def exists(self, storage_path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=storage_path)
            return True
        except ClientError:
            return False


def get_storage_backend() -> StorageBackend:
    """Factory for configured storage backend."""
    if settings.storage_backend.lower() == "s3":
        return S3StorageBackend()
    return LocalStorageBackend()
