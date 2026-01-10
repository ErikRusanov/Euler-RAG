"""Integration tests for S3 storage with real S3/MinIO backend.

These tests require configured S3 credentials in environment.
Tests are skipped if S3_ACCESS_KEY_ID or S3_SECRET_ACCESS_KEY are not set.
"""

from io import BytesIO
from typing import Optional

import pytest

from app.utils.s3 import S3Storage

# Test folder to use in S3 bucket
TEST_FOLDER = "_test_integration"


@pytest.fixture
def test_file_content() -> bytes:
    """Sample file content for testing."""
    return b"Test file content for S3 integration test"


class TestS3StorageIntegration:
    """Integration tests for S3Storage with real backend."""

    def test_upload_and_delete_file(
        self,
        s3_storage: Optional[S3Storage],
        test_file_content: bytes,
    ):
        """Upload file to S3 and delete it afterwards."""
        if s3_storage is None:
            pytest.skip("S3 credentials not configured")

        # Arrange
        file_data = BytesIO(test_file_content)
        original_name = "test_document.txt"

        # Act - Upload
        key = s3_storage.upload_file(file_data, original_name, TEST_FOLDER)

        # Assert - File was uploaded
        assert key is not None
        assert TEST_FOLDER in key
        assert original_name in key

        # Act - Get presigned URL (verifies file exists)
        url = s3_storage.get_file_url(key)

        # Assert - URL was generated
        assert url is not None
        assert s3_storage._bucket_name in url or key in url

        # Cleanup - Delete the file
        s3_storage.delete_file(key)

    def test_verify_connection(self, s3_storage: Optional[S3Storage]):
        """Verify S3 connection works."""
        if s3_storage is None:
            pytest.skip("S3 credentials not configured")

        result = s3_storage.verify_connection()

        assert result is True

    def test_upload_with_unique_names(
        self,
        s3_storage: Optional[S3Storage],
        test_file_content: bytes,
    ):
        """Multiple uploads with same name get different keys."""
        if s3_storage is None:
            pytest.skip("S3 credentials not configured")

        keys_to_cleanup = []

        try:
            file_data1 = BytesIO(test_file_content)
            file_data2 = BytesIO(test_file_content)

            key1 = s3_storage.upload_file(file_data1, "same_name.txt", TEST_FOLDER)
            keys_to_cleanup.append(key1)

            key2 = s3_storage.upload_file(file_data2, "same_name.txt", TEST_FOLDER)
            keys_to_cleanup.append(key2)

            # Keys should be different due to time-based hash
            assert key1 != key2
            assert "same_name.txt" in key1
            assert "same_name.txt" in key2

        finally:
            for key in keys_to_cleanup:
                try:
                    s3_storage.delete_file(key)
                except Exception:
                    pass
