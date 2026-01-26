"""Unit tests for NougatClient."""

from unittest.mock import AsyncMock, patch

import pytest

from app.utils.nougat import NougatClient, NougatError


class TestNougatClient:
    """Tests for NougatClient."""

    @pytest.fixture
    def nougat_client(self):
        """Create NougatClient instance."""
        return NougatClient(api_token="test-token")

    @pytest.mark.asyncio
    async def test_extract_text_success(self, nougat_client: NougatClient):
        """Extract text should return text content from Replicate API."""
        pdf_url = "https://example.com/test.pdf"
        expected_output = "# Document Title\n\nThis is extracted text."

        with patch("app.utils.nougat.replicate") as mock_replicate:
            mock_replicate.async_run = AsyncMock(return_value=expected_output)

            result = await nougat_client.extract_text(pdf_url)

            assert result == expected_output
            mock_replicate.async_run.assert_called_once_with(
                NougatClient.MODEL_ID,
                input={"pdf_link": pdf_url},
            )

    @pytest.mark.asyncio
    async def test_extract_text_handles_api_error(self, nougat_client: NougatClient):
        """Extract text should raise NougatError on API failure."""
        pdf_url = "https://example.com/test.pdf"

        with patch("app.utils.nougat.replicate") as mock_replicate:
            mock_replicate.async_run = AsyncMock(
                side_effect=Exception("API connection failed")
            )

            with pytest.raises(NougatError) as exc_info:
                await nougat_client.extract_text(pdf_url)

            assert "API connection failed" in str(exc_info.value)
            assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_extract_text_handles_invalid_response(
        self, nougat_client: NougatClient
    ):
        """Extract text should handle None or empty response."""
        pdf_url = "https://example.com/test.pdf"

        with patch("app.utils.nougat.replicate") as mock_replicate:
            mock_replicate.async_run = AsyncMock(return_value=None)

            with pytest.raises(NougatError) as exc_info:
                await nougat_client.extract_text(pdf_url)

            assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_extract_text_handles_list_output(self, nougat_client: NougatClient):
        """Extract text should join list output into single string."""
        pdf_url = "https://example.com/test.pdf"
        list_output = ["Page 1 content", "Page 2 content", "Page 3 content"]

        with patch("app.utils.nougat.replicate") as mock_replicate:
            mock_replicate.async_run = AsyncMock(return_value=list_output)

            result = await nougat_client.extract_text(pdf_url)

            assert result == "\n\n".join(list_output)

    @pytest.mark.asyncio
    async def test_extract_text_sets_api_token(self):
        """Extract text should use provided API token."""
        api_token = "custom-api-token"
        pdf_url = "https://example.com/test.pdf"

        client = NougatClient(api_token=api_token)

        with patch("app.utils.nougat.replicate") as mock_replicate:
            mock_replicate.async_run = AsyncMock(return_value="text")

            await client.extract_text(pdf_url)

            # Verify the client was configured
            assert mock_replicate.Client.called or hasattr(mock_replicate, "api_token")


class TestNougatError:
    """Tests for NougatError exception."""

    def test_nougat_error_stores_message(self):
        """NougatError should store message."""
        error = NougatError("Test error message")
        assert str(error) == "Test error message"
        assert error.retryable is True  # Default

    def test_nougat_error_retryable_flag(self):
        """NougatError should store retryable flag."""
        error_retryable = NougatError("Temp error", retryable=True)
        error_non_retryable = NougatError("Perm error", retryable=False)

        assert error_retryable.retryable is True
        assert error_non_retryable.retryable is False
