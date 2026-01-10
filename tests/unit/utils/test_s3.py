"""Unit tests for S3 storage client.

Tests cover:
- Unique filename generation with time-based hash
- Key creation with folder prefix
- File upload with size validation
- File path retrieval
- File deletion
- Connection verification
"""

from datetime import datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.models.exceptions import S3ConnectionError, S3OperationError


class TestS3Storage:
    """Test suite for S3Storage class."""

    @pytest.fixture
    def mock_boto3_client(self):
        """Create a mock boto3 S3 client."""
        with patch("app.utils.s3.boto3.client") as mock_client:
            yield mock_client

    @pytest.fixture
    def s3_storage(self, mock_boto3_client):
        """Create S3Storage instance with mocked client."""
        from app.utils.s3 import S3Storage

        mock_client_instance = MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        storage = S3Storage(
            endpoint_url="http://localhost:9000",
            access_key="test-access-key",
            secret_key="test-secret-key",
            bucket_name="test-bucket",
            region="us-east-1",
        )
        return storage

    def test_init_creates_boto3_client(self, mock_boto3_client):
        """Test: S3Storage should create boto3 client with correct config."""
        from app.utils.s3 import S3Storage

        S3Storage(
            endpoint_url="http://localhost:9000",
            access_key="test-access-key",
            secret_key="test-secret-key",
            bucket_name="test-bucket",
            region="us-east-1",
        )

        mock_boto3_client.assert_called_once_with(
            "s3",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            region_name="us-east-1",
        )

    def test_generate_unique_name_format(self, s3_storage):
        """Test: Generated name should follow format hash__{original_name}.{ext}."""
        original_name = "document.pdf"

        result = s3_storage._generate_unique_name(original_name)

        # Should contain hash separator
        assert "__" in result
        # Should end with original name
        assert result.endswith("__document.pdf")
        # Hash part should be before separator
        hash_part = result.split("__")[0]
        assert len(hash_part) > 0

    def test_generate_unique_name_preserves_extension(self, s3_storage):
        """Test: Generated name should preserve original file extension."""
        test_cases = [
            ("file.pdf", ".pdf"),
            ("image.png", ".png"),
            ("data.json", ".json"),
            ("archive.tar.gz", ".gz"),
        ]

        for original_name, expected_ext in test_cases:
            result = s3_storage._generate_unique_name(original_name)
            assert result.endswith(expected_ext), f"Failed for {original_name}"

    def test_generate_unique_name_handles_no_extension(self, s3_storage):
        """Test: Generated name should handle files without extension."""
        original_name = "README"

        result = s3_storage._generate_unique_name(original_name)

        assert "__README" in result
        assert not result.endswith(".")

    def test_generate_unique_name_uniqueness(self, s3_storage):
        """Test: Same filename should generate different unique names (time-based)."""
        from datetime import UTC

        original_name = "document.pdf"

        with patch("app.utils.s3.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2025, 1, 1, 12, 0, 0, 0, tzinfo=UTC
            )
            mock_datetime.UTC = UTC
            result1 = s3_storage._generate_unique_name(original_name)

            mock_datetime.now.return_value = datetime(
                2025, 1, 1, 12, 0, 0, 1, tzinfo=UTC
            )
            result2 = s3_storage._generate_unique_name(original_name)

        assert result1 != result2

    def test_create_key_with_folder(self, s3_storage):
        """Test: Key creation should prepend folder path."""
        filename = "abc123__document.pdf"
        folder = "documents"

        result = s3_storage._create_key(filename, folder)

        assert result == "documents/abc123__document.pdf"

    def test_create_key_with_nested_folder(self, s3_storage):
        """Test: Key creation should support nested folders."""
        filename = "abc123__document.pdf"
        folder = "uploads/2025/01"

        result = s3_storage._create_key(filename, folder)

        assert result == "uploads/2025/01/abc123__document.pdf"

    def test_create_key_with_empty_folder(self, s3_storage):
        """Test: Key creation with empty folder should return just filename."""
        filename = "abc123__document.pdf"

        result = s3_storage._create_key(filename, "")

        assert result == "abc123__document.pdf"

    def test_create_key_strips_leading_trailing_slashes(self, s3_storage):
        """Test: Key creation should normalize folder path."""
        filename = "abc123__document.pdf"
        folder = "/documents/"

        result = s3_storage._create_key(filename, folder)

        assert result == "documents/abc123__document.pdf"

    def test_upload_file_success(self, s3_storage):
        """Test: Upload file should return S3 key on success."""
        file_content = b"test content"
        file_data = BytesIO(file_content)
        original_name = "document.pdf"
        folder = "documents"

        with patch.object(s3_storage, "_generate_unique_name") as mock_gen:
            mock_gen.return_value = "abc123__document.pdf"

            result = s3_storage.upload_file(file_data, original_name, folder)

        assert result == "documents/abc123__document.pdf"
        s3_storage._client.put_object.assert_called_once()

    def test_upload_file_exceeds_size_limit(self, s3_storage):
        """Test: Upload should raise error when file exceeds 200MB limit."""
        # Create file larger than 200MB
        large_content = b"x" * (201 * 1024 * 1024)
        file_data = BytesIO(large_content)
        original_name = "large_file.pdf"

        with pytest.raises(S3OperationError) as exc_info:
            s3_storage.upload_file(file_data, original_name, "documents")

        assert "200 MB" in str(exc_info.value)

    def test_upload_file_exactly_at_limit(self, s3_storage):
        """Test: Upload should succeed when file is exactly 200MB."""
        # Create file exactly 200MB
        content = b"x" * (200 * 1024 * 1024)
        file_data = BytesIO(content)
        original_name = "max_size.pdf"

        with patch.object(s3_storage, "_generate_unique_name") as mock_gen:
            mock_gen.return_value = "abc123__max_size.pdf"

            result = s3_storage.upload_file(file_data, original_name, "documents")

        assert result is not None

    def test_upload_file_client_error(self, s3_storage):
        """Test: Upload should raise S3OperationError on client error."""
        file_data = BytesIO(b"test content")
        original_name = "document.pdf"

        s3_storage._client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "PutObject",
        )

        with pytest.raises(S3OperationError):
            s3_storage.upload_file(file_data, original_name, "documents")

    def test_get_file_url_success(self, s3_storage):
        """Test: Get file URL should return presigned URL."""
        key = "documents/abc123__document.pdf"
        expected_url = (
            "http://localhost:9000/test-bucket/documents/"
            "abc123__document.pdf?signature=xxx"
        )

        s3_storage._client.generate_presigned_url.return_value = expected_url

        result = s3_storage.get_file_url(key)

        assert result == expected_url
        s3_storage._client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": key},
            ExpiresIn=3600,
        )

    def test_get_file_url_with_custom_expiry(self, s3_storage):
        """Test: Get file URL should use custom expiry time."""
        key = "documents/abc123__document.pdf"

        s3_storage.get_file_url(key, expires_in=7200)

        s3_storage._client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": key},
            ExpiresIn=7200,
        )

    def test_get_file_url_client_error(self, s3_storage):
        """Test: Get URL should raise S3OperationError on client error."""
        key = "documents/abc123__document.pdf"

        s3_storage._client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            "GeneratePresignedUrl",
        )

        with pytest.raises(S3OperationError):
            s3_storage.get_file_url(key)

    def test_delete_file_success(self, s3_storage):
        """Test: Delete file should call delete_object."""
        key = "documents/abc123__document.pdf"

        s3_storage.delete_file(key)

        s3_storage._client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=key,
        )

    def test_delete_file_client_error(self, s3_storage):
        """Test: Delete should raise S3OperationError on client error."""
        key = "documents/abc123__document.pdf"

        s3_storage._client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "DeleteObject",
        )

        with pytest.raises(S3OperationError):
            s3_storage.delete_file(key)

    def test_verify_connection_success(self, s3_storage):
        """Test: Verify connection should return True on success."""
        s3_storage._client.head_bucket.return_value = {}

        result = s3_storage.verify_connection()

        assert result is True
        s3_storage._client.head_bucket.assert_called_once_with(Bucket="test-bucket")

    def test_verify_connection_failure(self, s3_storage):
        """Test: Verify connection should raise S3ConnectionError on failure."""
        s3_storage._client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
            "HeadBucket",
        )

        with pytest.raises(S3ConnectionError):
            s3_storage.verify_connection()


class TestS3StorageManager:
    """Test suite for S3 storage manager singleton."""

    def test_init_s3_creates_storage_instance(self):
        """Test: init_s3 should create and verify S3Storage instance."""
        with patch("app.utils.s3.S3Storage") as MockStorage:
            from app.utils.s3 import init_s3

            mock_instance = MagicMock()
            MockStorage.return_value = mock_instance

            with patch("app.utils.s3.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    s3_endpoint_url="http://localhost:9000",
                    s3_access_key_id="test-key",
                    s3_secret_access_key="test-secret",
                    s3_bucket_name="test-bucket",
                    s3_region="us-east-1",
                )

                init_s3()

            mock_instance.verify_connection.assert_called_once()

    def test_get_s3_storage_returns_instance(self):
        """Test: get_s3_storage should return initialized instance."""
        with patch("app.utils.s3.s3_manager") as mock_manager:
            from app.utils.s3 import get_s3_storage

            mock_storage = MagicMock()
            mock_manager.storage = mock_storage

            result = get_s3_storage()

            assert result == mock_storage

    def test_get_s3_storage_raises_if_not_initialized(self):
        """Test: get_s3_storage should raise if storage not initialized."""
        with patch("app.utils.s3.s3_manager") as mock_manager:
            from app.utils.s3 import get_s3_storage

            mock_manager.storage = None

            with pytest.raises(S3ConnectionError):
                get_s3_storage()
