"""Mathpix OCR client for PDF line-by-line extraction.

Uses the Mathpix API to extract text from PDF documents with
line-by-line granularity and rich metadata for math content.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings
from app.exceptions import MathpixError

logger = logging.getLogger(__name__)


class MathpixClient:
    """Client for extracting lines from PDFs using Mathpix API.

    Mathpix provides OCR with excellent support for mathematical notation,
    handwritten text, and multiple languages including Russian.

    Attributes:
        API_BASE_URL: Base URL for Mathpix API endpoints.
    """

    API_BASE_URL = "https://api.mathpix.com/v3"

    def __init__(self, app_id: str, app_key: str) -> None:
        """Initialize MathpixClient.

        Args:
            app_id: Mathpix application ID for authentication.
            app_key: Mathpix application key for authentication.
        """
        self._app_id = app_id
        self._app_key = app_key
        self._headers = {
            "app_id": app_id,
            "app_key": app_key,
        }
        logger.info("MathpixClient initialized")

    async def submit_pdf(self, pdf_url: str) -> str:
        """Submit PDF to Mathpix for processing.

        Args:
            pdf_url: Public URL of the PDF document to process.

        Returns:
            PDF ID for tracking the processing status.

        Raises:
            MathpixError: If PDF submission fails.
        """
        logger.info(
            "Submitting PDF to Mathpix",
            extra={"pdf_url": pdf_url},
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.API_BASE_URL}/pdf",
                    json={"url": pdf_url},
                    headers={
                        **self._headers,
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                pdf_id = data["pdf_id"]

                logger.info(
                    "PDF submitted successfully",
                    extra={"pdf_url": pdf_url, "pdf_id": pdf_id},
                )

                return pdf_id

        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to submit PDF - HTTP error",
                extra={
                    "pdf_url": pdf_url,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise MathpixError(f"Failed to submit PDF: {e}", retryable=False) from e
        except httpx.RequestError as e:
            logger.error(
                "Failed to submit PDF - network error",
                extra={"pdf_url": pdf_url, "error": str(e)},
            )
            raise MathpixError(str(e), retryable=True) from e
        except Exception as e:
            logger.error(
                "Failed to submit PDF - unexpected error",
                extra={"pdf_url": pdf_url, "error": str(e)},
            )
            raise MathpixError(str(e), retryable=True) from e

    async def poll_status(self, pdf_id: str) -> Dict[str, Any]:
        """Poll processing status of a submitted PDF.

        Args:
            pdf_id: PDF ID returned from submit_pdf.

        Returns:
            Status dictionary with keys: status, num_pages, percent_done,
            num_pages_completed.

        Raises:
            MathpixError: If status check fails.
        """
        logger.debug(
            "Polling Mathpix status",
            extra={"pdf_id": pdf_id},
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.API_BASE_URL}/pdf/{pdf_id}",
                    headers=self._headers,
                )
                response.raise_for_status()
                data = response.json()

                logger.debug(
                    "Status polled",
                    extra={"pdf_id": pdf_id, "status": data.get("status")},
                )

                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to poll status - HTTP error",
                extra={
                    "pdf_id": pdf_id,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise MathpixError(f"Failed to poll status: {e}", retryable=False) from e
        except httpx.RequestError as e:
            logger.error(
                "Failed to poll status - network error",
                extra={"pdf_id": pdf_id, "error": str(e)},
            )
            raise MathpixError(str(e), retryable=True) from e
        except Exception as e:
            logger.error(
                "Failed to poll status - unexpected error",
                extra={"pdf_id": pdf_id, "error": str(e)},
            )
            raise MathpixError(str(e), retryable=True) from e

    async def get_lines(self, pdf_id: str) -> Dict[str, Any]:
        """Get line-by-line data for a completed PDF.

        Args:
            pdf_id: PDF ID returned from submit_pdf.

        Returns:
            Lines data dictionary with page and line information.

        Raises:
            MathpixError: If fetching lines fails.
        """
        logger.info(
            "Fetching lines from Mathpix",
            extra={"pdf_id": pdf_id},
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.API_BASE_URL}/pdf/{pdf_id}.lines.json",
                    headers=self._headers,
                )
                response.raise_for_status()
                data = response.json()

                num_pages = len(data.get("pages", []))
                logger.info(
                    "Lines fetched successfully",
                    extra={"pdf_id": pdf_id, "num_pages": num_pages},
                )

                return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to get lines - HTTP error",
                extra={
                    "pdf_id": pdf_id,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise MathpixError(f"Failed to get lines: {e}", retryable=False) from e
        except httpx.RequestError as e:
            logger.error(
                "Failed to get lines - network error",
                extra={"pdf_id": pdf_id, "error": str(e)},
            )
            raise MathpixError(str(e), retryable=True) from e
        except Exception as e:
            logger.error(
                "Failed to get lines - unexpected error",
                extra={"pdf_id": pdf_id, "error": str(e)},
            )
            raise MathpixError(str(e), retryable=True) from e

    async def extract_lines(
        self,
        pdf_url: str,
        poll_interval: float = 5.0,
        max_polls: int = 120,
    ) -> Dict[str, Any]:
        """Extract line-by-line data from a PDF document.

        Orchestrates the full workflow: submit PDF, poll until completed, get lines.

        Args:
            pdf_url: Public URL of the PDF document to process.
            poll_interval: Seconds to wait between status polls (default 5.0).
            max_polls: Maximum number of status polls before timeout
                (default 120 = 10 min).

        Returns:
            Lines data dictionary with page and line information.

        Raises:
            MathpixError: If extraction fails at any stage.
        """
        logger.info(
            "Starting Mathpix line extraction",
            extra={"pdf_url": pdf_url},
        )

        # Step 1: Submit PDF
        pdf_id = await self.submit_pdf(pdf_url)

        # Step 2: Poll until completed
        for poll_count in range(max_polls):
            status_data = await self.poll_status(pdf_id)
            status = status_data.get("status")

            if status == "completed":
                logger.info(
                    "PDF processing completed",
                    extra={
                        "pdf_id": pdf_id,
                        "num_pages": status_data.get("num_pages"),
                    },
                )
                break
            elif status == "error":
                error_msg = status_data.get("error", "Unknown error")
                logger.error(
                    "PDF processing failed",
                    extra={"pdf_id": pdf_id, "error": error_msg},
                )
                raise MathpixError(
                    f"Mathpix processing error: {error_msg}",
                    retryable=False,
                )
            else:
                # Still processing (loaded, split, etc.)
                percent_done = status_data.get("percent_done", 0)
                logger.info(
                    "PDF still processing",
                    extra={
                        "pdf_id": pdf_id,
                        "status": status,
                        "percent_done": percent_done,
                        "poll_count": poll_count + 1,
                    },
                )
                await asyncio.sleep(poll_interval)
        else:
            # Max polls reached without completion
            logger.error(
                "PDF processing timeout",
                extra={"pdf_id": pdf_id, "max_polls": max_polls},
            )
            raise MathpixError(
                f"Timeout waiting for PDF processing (max_polls={max_polls})",
                retryable=True,
            )

        # Step 3: Get lines
        lines_data = await self.get_lines(pdf_id)

        logger.info(
            "Mathpix line extraction complete",
            extra={
                "pdf_url": pdf_url,
                "pdf_id": pdf_id,
                "num_pages": len(lines_data.get("pages", [])),
            },
        )

        return lines_data


class MathpixManager:
    """Manager for MathpixClient singleton instance."""

    def __init__(self) -> None:
        """Initialize MathpixManager with None client."""
        self.client: Optional[MathpixClient] = None

    def init_client(self) -> Optional[MathpixClient]:
        """Initialize MathpixClient from settings.

        Returns:
            Initialized MathpixClient instance, or None if not configured.
        """
        if self.client is not None:
            return self.client

        settings = get_settings()

        if not settings.mathpix_app_id or not settings.mathpix_app_key:
            logger.warning("Mathpix credentials not configured, Mathpix OCR disabled")
            return None

        self.client = MathpixClient(
            app_id=settings.mathpix_app_id,
            app_key=settings.mathpix_app_key,
        )
        return self.client


# Global Mathpix manager instance
mathpix_manager = MathpixManager()


def init_mathpix() -> Optional[MathpixClient]:
    """Initialize Mathpix client.

    Returns:
        Initialized MathpixClient instance, or None if not configured.
    """
    logger.info("Initializing Mathpix client...")
    client = mathpix_manager.init_client()
    if client:
        logger.info("Mathpix client initialized successfully")
    return client


def get_mathpix_client() -> Optional[MathpixClient]:
    """Get Mathpix client instance.

    Returns:
        MathpixClient instance, or None if not initialized/configured.
    """
    return mathpix_manager.client


def close_mathpix() -> None:
    """Close Mathpix client connection.

    Cleans up MathpixManager state.
    """
    logger.info("Closing Mathpix client...")
    mathpix_manager.client = None
    logger.info("Mathpix client closed")
