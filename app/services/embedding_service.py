"""Service for generating text embeddings via OpenRouter API."""

import asyncio
import logging
from typing import List

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings via OpenRouter API.

    This service handles communication with the OpenRouter API to generate
    vector embeddings for text content. It includes retry logic, rate limit
    handling, and batch processing capabilities.

    Attributes:
        settings: Application settings containing OpenRouter configuration.
        client: Async HTTP client for making API requests.
    """

    def __init__(self, settings: Settings):
        """Initialize the embedding service.

        Args:
            settings: Application settings with OpenRouter API configuration.
        """
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.openrouter_base_url,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.embedding_timeout,
        )

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to generate embedding for.

        Returns:
            List of floats representing the embedding vector.

        Raises:
            Exception: If API call fails after all retries.
        """
        embeddings = await self.generate_embeddings_batch([text])
        return embeddings[0]

    async def generate_embeddings_batch(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently.

        This method handles batching, retries, and rate limiting automatically.
        Large batches are split according to the embedding_batch_size setting.

        Args:
            texts: List of texts to generate embeddings for.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            Exception: If API call fails after all retries.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []

        # Split into batches based on configured batch size
        batch_size = self.settings.embedding_batch_size
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self._generate_batch_with_retry(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _generate_batch_with_retry(
        self,
        texts: List[str],
        max_retries: int = 3,
    ) -> List[List[float]]:
        """Generate embeddings with retry logic.

        Implements exponential backoff: 2s, 10s, 30s between retries.

        Args:
            texts: Batch of texts to embed.
            max_retries: Maximum number of retry attempts.

        Returns:
            List of embedding vectors.

        Raises:
            Exception: If all retries are exhausted.
        """
        retry_delays = [2, 10, 30]  # Exponential backoff in seconds

        for attempt in range(max_retries):
            try:
                return await self._call_embedding_api(texts)
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.warning(
                        f"Embedding API call failed "
                        f"(attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Embedding API call failed after {max_retries} attempts: {e}"
                    )
                    raise

        # This line should never be reached, but added for type checker
        raise Exception("Retry logic error")

    async def _call_embedding_api(self, texts: List[str]) -> List[List[float]]:
        """Make API call to OpenRouter to generate embeddings.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.

        Raises:
            Exception: If API call fails.
        """
        response = await self.client.post(
            "/embeddings",
            json={
                "model": self.settings.openrouter_embedding_model,
                "input": texts if len(texts) > 1 else texts[0],
            },
        )

        response.raise_for_status()
        data = response.json()

        # Extract embeddings from response
        embeddings = [item["embedding"] for item in data["data"]]

        logger.debug(
            f"Generated {len(embeddings)} embeddings using model "
            f"{self.settings.openrouter_embedding_model}"
        )

        return embeddings

    async def close(self):
        """Clean up HTTP client resources.

        Should be called when the service is no longer needed to properly
        close the HTTP connection pool.
        """
        await self.client.aclose()
