"""Nougat OCR client for PDF text extraction via Replicate API.

Uses the meta-nougat model to extract text from PDF documents with
high accuracy for mathematical notation and academic content.
"""

import logging
import os
from typing import Optional

import replicate

from app.config import get_settings

logger = logging.getLogger(__name__)


class NougatError(Exception):
    """Exception raised for Nougat API errors.

    Attributes:
        message: Error description.
        retryable: Whether the error is transient and can be retried.
    """

    def __init__(self, message: str, retryable: bool = True) -> None:
        """Initialize NougatError.

        Args:
            message: Error description.
            retryable: Whether the error is transient and can be retried.
        """
        super().__init__(message)
        self.retryable = retryable


class NougatClient:
    """Client for extracting text from PDFs using Nougat via Replicate.

    Nougat is a neural OCR model optimized for academic documents,
    particularly those containing mathematical notation.

    Attributes:
        MODEL_ID: The Replicate model identifier for meta-nougat.
    """

    MODEL_ID = (
        "awilliamson10/meta-nougat:"
        "872fa99400b0eeb8bfc82ef433aa378976b4311178ff64fed439470249902071"
    )

    def __init__(self, api_token: str) -> None:
        """Initialize NougatClient.

        Args:
            api_token: Replicate API token for authentication.
        """
        self._api_token = api_token
        # Set the API token in environment for replicate library
        os.environ["REPLICATE_API_TOKEN"] = api_token
        logger.info("NougatClient initialized")

    async def extract_text(self, pdf_url: str) -> str:
        """Extract text from a PDF document using Nougat OCR.

        Args:
            pdf_url: Public URL of the PDF document to process.

        Returns:
            Extracted text content from the PDF in Markdown format.

        Raises:
            NougatError: If text extraction fails.
        """
        logger.info(
            "Starting Nougat text extraction",
            extra={"pdf_url": pdf_url},
        )

        try:
            output = await replicate.async_run(
                self.MODEL_ID,
                input={"pdf_link": pdf_url},
            )

            # Handle different output formats
            if output is None:
                raise NougatError(
                    "Nougat returned empty response",
                    retryable=False,
                )

            # Output can be a string or list of strings (one per page)
            if isinstance(output, list):
                text = "\n\n".join(str(item) for item in output)
            else:
                text = str(output)

            if not text.strip():
                raise NougatError(
                    "Nougat returned empty text content",
                    retryable=False,
                )

            logger.info(
                "Nougat text extraction complete",
                extra={
                    "pdf_url": pdf_url,
                    "text_length": len(text),
                },
            )

            return text

        except NougatError:
            raise
        except Exception as e:
            logger.error(
                "Nougat text extraction failed",
                extra={
                    "pdf_url": pdf_url,
                    "error": str(e),
                },
            )
            raise NougatError(str(e), retryable=True) from e


class NougatManager:
    """Manager for NougatClient singleton instance."""

    def __init__(self) -> None:
        """Initialize NougatManager with None client."""
        self.client: Optional[NougatClient] = None

    def init_client(self) -> Optional[NougatClient]:
        """Initialize NougatClient from settings.

        Returns:
            Initialized NougatClient instance, or None if token not configured.
        """
        if self.client is not None:
            return self.client

        settings = get_settings()

        if not settings.replicate_api_token:
            logger.warning("REPLICATE_API_TOKEN not configured, Nougat OCR disabled")
            return None

        self.client = NougatClient(api_token=settings.replicate_api_token)
        return self.client


# Global Nougat manager instance
nougat_manager = NougatManager()


def init_nougat() -> Optional[NougatClient]:
    """Initialize Nougat client.

    Returns:
        Initialized NougatClient instance, or None if not configured.
    """
    logger.info("Initializing Nougat client...")
    client = nougat_manager.init_client()
    if client:
        logger.info("Nougat client initialized successfully")
    return client


def get_nougat_client() -> Optional[NougatClient]:
    """Get Nougat client instance.

    Returns:
        NougatClient instance, or None if not initialized/configured.
    """
    return nougat_manager.client


def close_nougat() -> None:
    """Close Nougat client connection.

    Cleans up NougatManager state.
    """
    logger.info("Closing Nougat client...")
    nougat_manager.client = None
    logger.info("Nougat client closed")
