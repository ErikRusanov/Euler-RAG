"""Unit tests for MathpixClient."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import HTTPStatusError, RequestError, Response

from app.utils.mathpix import MathpixClient, MathpixError


class TestMathpixClient:
    """Tests for MathpixClient."""

    @pytest.fixture
    def mathpix_client(self):
        """Create MathpixClient instance."""
        return MathpixClient(app_id="test-app-id", app_key="test-app-key")

    @pytest.mark.asyncio
    async def test_submit_pdf_success(self, mathpix_client: MathpixClient):
        """Submit PDF should return pdf_id from Mathpix API."""
        pdf_url = "https://example.com/test.pdf"
        expected_pdf_id = "5049b56d6cf916e713be03206f306f1a"

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock(spec=Response)
            mock_response.json.return_value = {"pdf_id": expected_pdf_id}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            result = await mathpix_client.submit_pdf(pdf_url)

            assert result == expected_pdf_id
            mock_post.assert_called_once_with(
                "https://api.mathpix.com/v3/pdf",
                json={"url": pdf_url},
                headers={
                    "app_id": "test-app-id",
                    "app_key": "test-app-key",
                    "Content-Type": "application/json",
                },
            )

    @pytest.mark.asyncio
    async def test_submit_pdf_handles_http_error(self, mathpix_client: MathpixClient):
        """Submit PDF should raise MathpixError on HTTP error."""
        pdf_url = "https://example.com/test.pdf"

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock(spec=Response)
            mock_response.status_code = 401
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Unauthorized", request=Mock(), response=mock_response
            )
            mock_post.return_value = mock_response

            with pytest.raises(MathpixError) as exc_info:
                await mathpix_client.submit_pdf(pdf_url)

            assert "Failed to submit PDF" in str(exc_info.value)
            assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_submit_pdf_handles_network_error(
        self, mathpix_client: MathpixClient
    ):
        """Submit PDF should raise MathpixError on network error."""
        pdf_url = "https://example.com/test.pdf"

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = RequestError("Connection timeout")

            with pytest.raises(MathpixError) as exc_info:
                await mathpix_client.submit_pdf(pdf_url)

            assert "Connection timeout" in str(exc_info.value)
            assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_poll_status_returns_completed(self, mathpix_client: MathpixClient):
        """Poll status should return status data when completed."""
        pdf_id = "test-pdf-id"
        expected_status = {
            "status": "completed",
            "num_pages": 9,
            "percent_done": 100,
            "num_pages_completed": 9,
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock(spec=Response)
            mock_response.json.return_value = expected_status
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await mathpix_client.poll_status(pdf_id)

            assert result == expected_status
            mock_get.assert_called_once_with(
                f"https://api.mathpix.com/v3/pdf/{pdf_id}",
                headers={
                    "app_id": "test-app-id",
                    "app_key": "test-app-key",
                },
            )

    @pytest.mark.asyncio
    async def test_poll_status_returns_processing(self, mathpix_client: MathpixClient):
        """Poll status should return processing status."""
        pdf_id = "test-pdf-id"
        expected_status = {
            "status": "split",
            "num_pages": 9,
            "percent_done": 33.33,
            "num_pages_completed": 3,
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock(spec=Response)
            mock_response.json.return_value = expected_status
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await mathpix_client.poll_status(pdf_id)

            assert result == expected_status
            assert result["status"] == "split"

    @pytest.mark.asyncio
    async def test_poll_status_handles_error(self, mathpix_client: MathpixClient):
        """Poll status should raise MathpixError on API error."""
        pdf_id = "test-pdf-id"

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock(spec=Response)
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Not found", request=Mock(), response=mock_response
            )
            mock_get.return_value = mock_response

            with pytest.raises(MathpixError) as exc_info:
                await mathpix_client.poll_status(pdf_id)

            assert "Failed to poll status" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_lines_success(self, mathpix_client: MathpixClient):
        """Get lines should return parsed lines data."""
        pdf_id = "test-pdf-id"
        expected_lines = {
            "pages": [
                {
                    "image_id": "2025_04_16_test-01",
                    "page": 1,
                    "lines": [
                        {
                            "id": "line-1",
                            "text": "Test line",
                            "type": "text",
                            "line": 1,
                            "is_printed": True,
                            "is_handwritten": False,
                        }
                    ],
                }
            ]
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock(spec=Response)
            mock_response.json.return_value = expected_lines
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await mathpix_client.get_lines(pdf_id)

            assert result == expected_lines
            mock_get.assert_called_once_with(
                f"https://api.mathpix.com/v3/pdf/{pdf_id}.lines.json",
                headers={
                    "app_id": "test-app-id",
                    "app_key": "test-app-key",
                },
            )

    @pytest.mark.asyncio
    async def test_get_lines_handles_error(self, mathpix_client: MathpixClient):
        """Get lines should raise MathpixError on API error."""
        pdf_id = "test-pdf-id"

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock(spec=Response)
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Server error", request=Mock(), response=mock_response
            )
            mock_get.return_value = mock_response

            with pytest.raises(MathpixError) as exc_info:
                await mathpix_client.get_lines(pdf_id)

            assert "Failed to get lines" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_lines_success(self, mathpix_client: MathpixClient):
        """Extract lines should orchestrate submit, poll, and get_lines."""
        pdf_url = "https://example.com/test.pdf"
        pdf_id = "test-pdf-id"
        expected_lines = {
            "pages": [
                {
                    "image_id": "test-01",
                    "page": 1,
                    "lines": [{"id": "line-1", "text": "Test"}],
                }
            ]
        }

        with patch.object(
            mathpix_client, "submit_pdf", new_callable=AsyncMock
        ) as mock_submit:
            with patch.object(
                mathpix_client, "poll_status", new_callable=AsyncMock
            ) as mock_poll:
                with patch.object(
                    mathpix_client, "get_lines", new_callable=AsyncMock
                ) as mock_get_lines:
                    mock_submit.return_value = pdf_id
                    mock_poll.return_value = {"status": "completed"}
                    mock_get_lines.return_value = expected_lines

                    result = await mathpix_client.extract_lines(pdf_url)

                    assert result == expected_lines
                    mock_submit.assert_called_once_with(pdf_url)
                    mock_poll.assert_called_once_with(pdf_id)
                    mock_get_lines.assert_called_once_with(pdf_id)

    @pytest.mark.asyncio
    async def test_extract_lines_polls_until_completed(
        self, mathpix_client: MathpixClient
    ):
        """Extract lines should poll multiple times until status is completed."""
        pdf_url = "https://example.com/test.pdf"
        pdf_id = "test-pdf-id"
        expected_lines = {"pages": []}

        with patch.object(
            mathpix_client, "submit_pdf", new_callable=AsyncMock
        ) as mock_submit:
            with patch.object(
                mathpix_client, "poll_status", new_callable=AsyncMock
            ) as mock_poll:
                with patch.object(
                    mathpix_client, "get_lines", new_callable=AsyncMock
                ) as mock_get_lines:
                    mock_submit.return_value = pdf_id
                    # First two calls return processing, third returns completed
                    mock_poll.side_effect = [
                        {"status": "split", "percent_done": 33},
                        {"status": "split", "percent_done": 66},
                        {"status": "completed", "percent_done": 100},
                    ]
                    mock_get_lines.return_value = expected_lines

                    result = await mathpix_client.extract_lines(
                        pdf_url, poll_interval=0.1
                    )

                    assert result == expected_lines
                    assert mock_poll.call_count == 3

    @pytest.mark.asyncio
    async def test_extract_lines_handles_error_status(
        self, mathpix_client: MathpixClient
    ):
        """Extract lines should raise MathpixError if status is error."""
        pdf_url = "https://example.com/test.pdf"
        pdf_id = "test-pdf-id"

        with patch.object(
            mathpix_client, "submit_pdf", new_callable=AsyncMock
        ) as mock_submit:
            with patch.object(
                mathpix_client, "poll_status", new_callable=AsyncMock
            ) as mock_poll:
                mock_submit.return_value = pdf_id
                mock_poll.return_value = {
                    "status": "error",
                    "error": "Processing failed",
                }

                with pytest.raises(MathpixError) as exc_info:
                    await mathpix_client.extract_lines(pdf_url)

                assert "Processing failed" in str(exc_info.value)
                assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_extract_lines_timeout(self, mathpix_client: MathpixClient):
        """Extract lines should timeout after max_polls."""
        pdf_url = "https://example.com/test.pdf"
        pdf_id = "test-pdf-id"

        with patch.object(
            mathpix_client, "submit_pdf", new_callable=AsyncMock
        ) as mock_submit:
            with patch.object(
                mathpix_client, "poll_status", new_callable=AsyncMock
            ) as mock_poll:
                mock_submit.return_value = pdf_id
                # Always return processing status
                mock_poll.return_value = {"status": "split", "percent_done": 50}

                with pytest.raises(MathpixError) as exc_info:
                    await mathpix_client.extract_lines(
                        pdf_url, poll_interval=0.1, max_polls=3
                    )

                assert "Timeout" in str(exc_info.value)
                assert exc_info.value.retryable is True
                assert mock_poll.call_count == 3


class TestMathpixError:
    """Tests for MathpixError exception."""

    def test_mathpix_error_stores_message(self):
        """MathpixError should store message."""
        error = MathpixError("Test error message")
        assert str(error) == "Test error message"
        assert error.retryable is True

    def test_mathpix_error_retryable_flag(self):
        """MathpixError should store retryable flag."""
        error_retryable = MathpixError("Temp error", retryable=True)
        error_non_retryable = MathpixError("Perm error", retryable=False)

        assert error_retryable.retryable is True
        assert error_non_retryable.retryable is False
