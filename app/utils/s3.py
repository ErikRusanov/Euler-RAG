"""S3 storage client for file operations."""

import hashlib
import logging
import mimetypes
from datetime import UTC, datetime
from typing import BinaryIO, Optional

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings
from app.exceptions import S3ConnectionError, S3OperationError

logger = logging.getLogger(__name__)

# Maximum file size: 200 MB
MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024


class S3Storage:
    """S3 storage client for file operations.

    Provides methods for uploading, retrieving, and deleting files
    from S3-compatible storage with unique filename generation.
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region: str,
    ) -> None:
        """Initialize S3 storage client.

        Args:
            endpoint_url: S3-compatible storage endpoint URL.
            access_key: AWS access key ID.
            secret_key: AWS secret access key.
            bucket_name: S3 bucket name.
            region: AWS region.
        """
        self._bucket_name = bucket_name
        self._endpoint_url = endpoint_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        logger.info(
            "S3 storage client initialized",
            extra={"endpoint": endpoint_url, "bucket": bucket_name},
        )

    def _generate_unique_name(self, original_name: str) -> str:
        """Generate unique filename with time-based hash.

        Args:
            original_name: Original filename with extension.

        Returns:
            Unique filename in format: hash__{original_name}
        """
        timestamp = datetime.now(UTC).isoformat()
        hash_input = f"{timestamp}:{original_name}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return f"{hash_value}__{original_name}"

    def _create_key(self, filename: str, folder: str) -> str:
        """Create S3 key with folder prefix.

        Args:
            filename: Filename to use.
            folder: Folder path (can be nested, e.g., "uploads/2025/01").

        Returns:
            Full S3 key with folder prefix.
        """
        folder = folder.strip("/")
        if not folder:
            return filename
        return f"{folder}/{filename}"

    def _get_content_type(
        self, filename: str, content_type: Optional[str] = None
    ) -> str:
        """Determine Content-Type for file.

        Args:
            filename: Filename with extension.
            content_type: Optional explicit content type.

        Returns:
            MIME type string (defaults to application/octet-stream).
        """
        if content_type:
            return content_type

        # Try to guess from extension
        guessed_type, _ = mimetypes.guess_type(filename)
        if guessed_type:
            return guessed_type

        return "application/octet-stream"

    def _get_content_disposition(
        self, filename: str, content_type: str
    ) -> Optional[str]:
        """Generate Content-Disposition header for file.

        For PDF files, returns 'inline' to allow browser viewing.
        For other files, returns None (browser will decide).

        Args:
            filename: Original filename.
            content_type: File MIME type.

        Returns:
            Content-Disposition header value or None.
        """
        if content_type == "application/pdf":
            return f'inline; filename="{filename}"'
        return None

    def upload_file(
        self,
        file_data: BinaryIO,
        original_name: str,
        folder: str = "",
        content_type: Optional[str] = None,
    ) -> str:
        """Upload file to S3 storage with proper metadata.

        Args:
            file_data: File-like object with binary data.
            original_name: Original filename with extension.
            folder: Optional folder prefix.
            content_type: Optional explicit MIME type
                (guessed from extension if not provided).

        Returns:
            S3 key of uploaded file.

        Raises:
            S3OperationError: If file exceeds size limit or upload fails.
        """
        # Check file size
        file_data.seek(0, 2)  # Seek to end
        file_size = file_data.tell()
        file_data.seek(0)  # Reset to beginning

        if file_size > MAX_FILE_SIZE_BYTES:
            raise S3OperationError(
                f"File size {file_size} bytes exceeds maximum allowed 200 MB"
            )

        unique_name = self._generate_unique_name(original_name)
        key = self._create_key(unique_name, folder)

        # Determine content type and disposition
        mime_type = self._get_content_type(original_name, content_type)
        content_disposition = self._get_content_disposition(original_name, mime_type)

        # Build metadata for put_object
        put_params = {
            "Bucket": self._bucket_name,
            "Key": key,
            "Body": file_data,
            "ContentType": mime_type,
        }

        if content_disposition:
            put_params["ContentDisposition"] = content_disposition

        try:
            self._client.put_object(**put_params)
            logger.info(
                "File uploaded to S3",
                extra={
                    "key": key,
                    "size": file_size,
                    "content_type": mime_type,
                    "content_disposition": content_disposition,
                },
            )
            return key
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise S3OperationError(f"Failed to upload file: {e}") from e

    def get_file_url(self, key: str) -> str:
        """Get direct public URL for file.

        Args:
            key: S3 key of the file.

        Returns:
            Direct URL for file access.
        """
        return f"{self._endpoint_url}/{self._bucket_name}/{key}"

    def download_file(self, key: str) -> bytes:
        """Download file from S3 storage.

        Args:
            key: S3 key of the file to download.

        Returns:
            File contents as bytes.

        Raises:
            S3OperationError: If download fails or file not found.
        """
        try:
            response = self._client.get_object(
                Bucket=self._bucket_name,
                Key=key,
            )
            data = response["Body"].read()
            logger.info(
                "File downloaded from S3",
                extra={"key": key, "size": len(data)},
            )
            return data
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                logger.error(f"File not found in S3: {key}")
                raise S3OperationError(f"File not found: {key}") from e
            logger.error(f"Failed to download file from S3: {e}")
            raise S3OperationError(f"Failed to download file: {e}") from e

    def delete_file(self, key: str) -> None:
        """Delete file from S3 storage.

        Args:
            key: S3 key of the file to delete.

        Raises:
            S3OperationError: If deletion fails.
        """
        try:
            self._client.delete_object(
                Bucket=self._bucket_name,
                Key=key,
            )
            logger.info("File deleted from S3", extra={"key": key})
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            raise S3OperationError(f"Failed to delete file: {e}") from e

    def verify_connection(self) -> bool:
        """Verify S3 connection and bucket access.

        Returns:
            True if connection is successful.

        Raises:
            S3ConnectionError: If connection verification fails.
        """
        try:
            self._client.head_bucket(Bucket=self._bucket_name)
            logger.info("S3 connection verified successfully")
            return True
        except ClientError as e:
            logger.error(f"S3 connection verification failed: {e}")
            raise S3ConnectionError(f"Failed to connect to S3: {e}") from e


class S3Manager:
    """Manager for S3 storage singleton instance."""

    def __init__(self) -> None:
        """Initialize S3 manager with None storage."""
        self.storage: Optional[S3Storage] = None

    def init_storage(self) -> S3Storage:
        """Initialize S3 storage from settings.

        Returns:
            Initialized S3Storage instance.

        Raises:
            S3ConnectionError: If connection fails.
        """
        if self.storage is not None:
            return self.storage

        settings = get_settings()

        self.storage = S3Storage(
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key_id,
            secret_key=settings.s3_secret_access_key,
            bucket_name=settings.s3_bucket_name,
            region=settings.s3_region,
        )

        return self.storage


# Global S3 manager instance
s3_manager = S3Manager()


def init_s3() -> None:
    """Initialize S3 storage connection.

    Creates storage instance and verifies connection.

    Raises:
        S3ConnectionError: If S3 connection fails.
    """
    logger.info("Initializing S3 storage connection...")
    storage = s3_manager.init_storage()
    storage.verify_connection()
    logger.info("S3 storage initialized successfully")


def get_s3_storage() -> S3Storage:
    """Get S3 storage instance.

    Returns:
        Initialized S3Storage instance.

    Raises:
        S3ConnectionError: If storage is not initialized.
    """
    if s3_manager.storage is None:
        raise S3ConnectionError("S3 storage is not initialized")
    return s3_manager.storage


def close_s3() -> None:
    """Close S3 storage connection.

    Cleans up S3 manager state.
    """
    logger.info("Closing S3 storage connection...")
    s3_manager.storage = None
    logger.info("S3 storage connection closed")
