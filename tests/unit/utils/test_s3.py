"""Unit tests for S3 storage client."""

from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.exceptions import S3ConnectionError, S3OperationError


class TestS3Storage:
    """Tests for S3Storage class."""

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
        """S3Storage creates boto3 client with correct configuration."""
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
        """Generated name follows hash__original.ext format."""
        result = s3_storage._generate_unique_name("document.pdf")

        assert "__" in result
        assert result.endswith("__document.pdf")

    def test_generate_unique_name_uniqueness(self, s3_storage):
        """Same filename generates different names at different times."""
        with patch("app.utils.s3.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(
                2025, 1, 1, 12, 0, 0, 0, tzinfo=UTC
            )
            mock_datetime.UTC = UTC
            result1 = s3_storage._generate_unique_name("document.pdf")

            mock_datetime.now.return_value = datetime(
                2025, 1, 1, 12, 0, 0, 1, tzinfo=UTC
            )
            result2 = s3_storage._generate_unique_name("document.pdf")

        assert result1 != result2

    def test_create_key_with_folder(self, s3_storage):
        """Key creation prepends folder path."""
        result = s3_storage._create_key("abc123__document.pdf", "documents")

        assert result == "documents/abc123__document.pdf"

    def test_upload_file_success(self, s3_storage):
        """Upload returns S3 key on success."""
        file_data = BytesIO(b"test content")

        with patch.object(s3_storage, "_generate_unique_name") as mock_gen:
            mock_gen.return_value = "abc123__document.pdf"
            result = s3_storage.upload_file(file_data, "document.pdf", "documents")

        assert result == "documents/abc123__document.pdf"
        s3_storage._client.put_object.assert_called_once()

    def test_upload_file_exceeds_size_limit(self, s3_storage):
        """Upload raises error when file exceeds 200MB limit."""
        large_content = b"x" * (201 * 1024 * 1024)
        file_data = BytesIO(large_content)

        with pytest.raises(S3OperationError) as exc_info:
            s3_storage.upload_file(file_data, "large_file.pdf", "documents")

        assert "200 MB" in str(exc_info.value)

    def test_upload_file_client_error(self, s3_storage):
        """Upload raises S3OperationError on client error."""
        file_data = BytesIO(b"test content")
        s3_storage._client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "PutObject",
        )

        with pytest.raises(S3OperationError):
            s3_storage.upload_file(file_data, "document.pdf", "documents")

    def test_get_file_url_success(self, s3_storage):
        """Get file URL returns direct URL (not presigned)."""
        result = s3_storage.get_file_url("documents/doc.pdf")

        # get_file_url returns a direct URL without signature
        assert result == "http://localhost:9000/test-bucket/documents/doc.pdf"

    def test_get_presigned_url_success(self, s3_storage):
        """Get presigned URL returns URL with signature."""
        expected_url = "http://localhost:9000/test-bucket/documents/doc.pdf?sig=xxx"
        s3_storage._client.generate_presigned_url.return_value = expected_url

        result = s3_storage.get_presigned_url("documents/doc.pdf")

        assert result == expected_url
        s3_storage._client.generate_presigned_url.assert_called_once()

    def test_delete_file_success(self, s3_storage):
        """Delete calls delete_object."""
        s3_storage.delete_file("documents/abc123__document.pdf")

        s3_storage._client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="documents/abc123__document.pdf",
        )

    def test_verify_connection_success(self, s3_storage):
        """Verify connection returns True on success."""
        s3_storage._client.head_bucket.return_value = {}

        result = s3_storage.verify_connection()

        assert result is True

    def test_verify_connection_failure(self, s3_storage):
        """Verify connection raises S3ConnectionError on failure."""
        s3_storage._client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
            "HeadBucket",
        )

        with pytest.raises(S3ConnectionError):
            s3_storage.verify_connection()


class TestS3StorageManager:
    """Tests for S3 storage manager singleton."""

    def test_init_s3_creates_and_verifies_storage(self):
        """init_s3 creates and verifies S3Storage instance."""
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

    def test_get_s3_storage_raises_if_not_initialized(self):
        """get_s3_storage raises if storage not initialized."""
        with patch("app.utils.s3.s3_manager") as mock_manager:
            from app.utils.s3 import get_s3_storage

            mock_manager.storage = None

            with pytest.raises(S3ConnectionError):
                get_s3_storage()
