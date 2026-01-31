"""Unit tests for EmbeddingService."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.config import Settings
from app.services.embedding_service import EmbeddingService


@pytest.fixture
def embedding_settings() -> Settings:
    """Create test settings with OpenRouter configuration."""
    return Settings(
        api_key="test-key",
        openrouter_api_key="sk-or-test-key-1234567890123456789012345678",
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_embedding_model="openai/text-embedding-3-large",
        embedding_dimensions=1024,
        embedding_batch_size=50,
        embedding_timeout=30.0,
    )


@pytest.mark.asyncio
async def test_generate_embedding_single_text(embedding_settings):
    """Test generating embedding for a single text.

    Verifies that the service makes a proper API call to OpenRouter
    and returns the expected embedding vector.
    """
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"embedding": [0.1] * 1024}]}
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        service = EmbeddingService(embedding_settings)
        embedding = await service.generate_embedding("test text")

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["input"] == "test text"
        assert call_args.kwargs["json"]["model"] == "openai/text-embedding-3-large"

        # Verify result
        assert len(embedding) == 1024
        assert all(isinstance(x, float) for x in embedding)
        assert embedding == [0.1] * 1024

        await service.close()


@pytest.mark.asyncio
async def test_generate_embeddings_batch(embedding_settings):
    """Test generating embeddings for multiple texts in batch.

    Verifies batch processing sends all texts in a single API call.
    """
    texts = ["text 1", "text 2", "text 3"]

    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [
            {"embedding": [0.1] * 1024},
            {"embedding": [0.2] * 1024},
            {"embedding": [0.3] * 1024},
        ]
    }
    mock_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        service = EmbeddingService(embedding_settings)
        embeddings = await service.generate_embeddings_batch(texts)

        # Verify single API call with all texts
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["input"] == texts

        # Verify results
        assert len(embeddings) == 3
        assert embeddings[0] == [0.1] * 1024
        assert embeddings[1] == [0.2] * 1024
        assert embeddings[2] == [0.3] * 1024

        await service.close()


@pytest.mark.asyncio
async def test_generate_embeddings_batch_splits_large_batches(embedding_settings):
    """Test that large batches are split according to batch_size setting.

    Verifies the service splits 100 texts into 2 batches of 50.
    """
    embedding_settings.embedding_batch_size = 50
    texts = [f"text {i}" for i in range(100)]

    Mock()
    # First batch response (50 items)
    mock_response_1 = Mock()
    mock_response_1.json.return_value = {
        "data": [{"embedding": [0.1] * 1024} for _ in range(50)]
    }
    mock_response_1.raise_for_status = Mock()

    # Second batch response (50 items)
    mock_response_2 = Mock()
    mock_response_2.json.return_value = {
        "data": [{"embedding": [0.2] * 1024} for _ in range(50)]
    }
    mock_response_2.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_response_1, mock_response_2]

        service = EmbeddingService(embedding_settings)
        embeddings = await service.generate_embeddings_batch(texts)

        # Verify two API calls
        assert mock_post.call_count == 2

        # Verify first call has 50 texts
        first_call_args = mock_post.call_args_list[0]
        assert len(first_call_args.kwargs["json"]["input"]) == 50

        # Verify second call has 50 texts
        second_call_args = mock_post.call_args_list[1]
        assert len(second_call_args.kwargs["json"]["input"]) == 50

        # Verify total results
        assert len(embeddings) == 100
        assert all(len(emb) == 1024 for emb in embeddings)

        await service.close()


@pytest.mark.asyncio
async def test_retry_on_transient_failure(embedding_settings):
    """Test retry logic on transient API failures.

    Verifies the service retries up to 3 times with exponential backoff.
    """
    # Mock responses: 2 failures, then success
    failure_response = Mock()
    failure_response.raise_for_status.side_effect = Exception("Network error")

    success_response = Mock()
    success_response.json.return_value = {"data": [{"embedding": [0.5] * 1024}]}
    success_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [failure_response, failure_response, success_response]

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            service = EmbeddingService(embedding_settings)
            embedding = await service.generate_embedding("test text")

            # Verify 3 attempts were made
            assert mock_post.call_count == 3

            # Verify exponential backoff: 2s, 10s
            assert mock_sleep.call_count == 2
            assert mock_sleep.call_args_list[0].args[0] == 2
            assert mock_sleep.call_args_list[1].args[0] == 10

            # Verify success
            assert embedding == [0.5] * 1024

            await service.close()


@pytest.mark.asyncio
async def test_retry_exhausted_raises_exception(embedding_settings):
    """Test that exception is raised after all retries are exhausted.

    Verifies the service raises an exception after 3 failed attempts.
    """
    failure_response = Mock()
    failure_response.raise_for_status.side_effect = Exception("Network error")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = failure_response

        with patch("asyncio.sleep", new_callable=AsyncMock):
            service = EmbeddingService(embedding_settings)

            with pytest.raises(Exception, match="Network error"):
                await service.generate_embedding("test text")

            # Verify 3 attempts were made
            assert mock_post.call_count == 3

            await service.close()


@pytest.mark.asyncio
async def test_rate_limit_handling(embedding_settings):
    """Test handling of rate limit (429) responses.

    Verifies the service retries after receiving a 429 status code.
    """
    # Mock 429 response
    rate_limit_response = Mock()
    rate_limit_error = Exception("429 Rate Limit")
    rate_limit_response.raise_for_status.side_effect = rate_limit_error

    # Success response after rate limit
    success_response = Mock()
    success_response.json.return_value = {"data": [{"embedding": [0.7] * 1024}]}
    success_response.raise_for_status = Mock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [rate_limit_response, success_response]

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            service = EmbeddingService(embedding_settings)
            embedding = await service.generate_embedding("test text")

            # Verify retry happened
            assert mock_post.call_count == 2
            assert mock_sleep.call_count == 1

            # Verify success
            assert embedding == [0.7] * 1024

            await service.close()


@pytest.mark.asyncio
async def test_close_cleans_up_client(embedding_settings):
    """Test that close() properly cleans up the HTTP client.

    Verifies the httpx client is closed when service is closed.
    """
    with patch("httpx.AsyncClient.aclose", new_callable=AsyncMock) as mock_aclose:
        service = EmbeddingService(embedding_settings)
        await service.close()

        mock_aclose.assert_called_once()


@pytest.mark.asyncio
async def test_empty_text_batch_returns_empty_list(embedding_settings):
    """Test that empty input returns empty output.

    Verifies the service handles empty input gracefully.
    """
    service = EmbeddingService(embedding_settings)
    embeddings = await service.generate_embeddings_batch([])

    assert embeddings == []

    await service.close()
