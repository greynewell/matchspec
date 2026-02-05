"""Result streaming to external storage backends.

Streams evaluation results to external storage as each task completes,
rather than waiting for the full evaluation to finish. Supports multiple
backends (local file, S3-compatible, webhook/HTTP POST) with buffering
and retry logic. Failures in streaming never block the evaluation.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class StreamBackend(Protocol):
    """Protocol for result streaming backends.

    All backends must implement async send, flush, and close methods.
    Implementations should be fault-tolerant and never raise exceptions
    that would block the evaluation pipeline.
    """

    async def send(self, result: dict) -> bool:
        """Send a single result to the backend.

        Args:
            result: Evaluation result dictionary to stream.

        Returns:
            True if the result was successfully sent, False otherwise.
        """
        ...

    async def flush(self) -> None:
        """Flush any buffered results to the backend."""
        ...

    async def close(self) -> None:
        """Close the backend and release any resources."""
        ...


class LocalFileStream:
    """Streams results to a local JSONL file.

    Appends each result as a JSON line to the specified file path.
    Automatically creates parent directories if they do not exist.
    """

    def __init__(self, path: str | Path) -> None:
        """Initialize local file stream backend.

        Args:
            path: File path for JSONL output. Parent directories are
                created automatically.
        """
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def send(self, result: dict) -> bool:
        """Append a result as a JSON line to the file.

        Args:
            result: Evaluation result dictionary.

        Returns:
            True if the write succeeded, False otherwise.
        """
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._write_line, result)
            return True
        except Exception:
            logger.exception("Failed to write result to %s", self._path)
            return False

    def _write_line(self, result: dict) -> None:
        """Write a single JSON line to the file (sync, for executor).

        Args:
            result: Evaluation result dictionary.
        """
        with open(self._path, "a") as f:
            f.write(json.dumps(result, default=str) + "\n")
            f.flush()

    async def flush(self) -> None:
        """Flush is a no-op for local file; each write already flushes."""

    async def close(self) -> None:
        """Close is a no-op for local file stream."""


class S3Stream:
    """Streams results to an S3-compatible object store.

    Each result is uploaded as an individual JSON object at
    ``s3://<bucket>/<prefix>/<task_id>.json``. Requires the ``boto3``
    package; gracefully degrades if it is not installed.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        region_name: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        """Initialize S3 stream backend.

        Args:
            bucket: S3 bucket name.
            prefix: Key prefix for uploaded objects (e.g. ``"results/run-1"``).
            region_name: AWS region name (optional).
            endpoint_url: Custom endpoint URL for S3-compatible services
                (e.g. MinIO). Optional.
        """
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._client: Any = None
        self._region_name = region_name
        self._endpoint_url = endpoint_url
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the boto3 S3 client if boto3 is available."""
        try:
            import boto3

            kwargs: dict[str, Any] = {}
            if self._region_name:
                kwargs["region_name"] = self._region_name
            if self._endpoint_url:
                kwargs["endpoint_url"] = self._endpoint_url
            self._client = boto3.client("s3", **kwargs)
            self._available = True
        except ImportError:
            logger.warning("boto3 is not installed; S3 streaming backend is disabled")
            self._available = False
        except Exception:
            logger.exception("Failed to initialize S3 client")
            self._available = False

    async def send(self, result: dict) -> bool:
        """Upload a result as a JSON object to S3.

        The object key is derived from the ``instance_id`` field in the
        result dict, falling back to a timestamp-based key.

        Args:
            result: Evaluation result dictionary.

        Returns:
            True if the upload succeeded, False otherwise.
        """
        if not self._available or self._client is None:
            return False

        try:
            task_id = result.get("instance_id", f"result-{time.time()}")
            key = f"{self._prefix}/{task_id}.json" if self._prefix else f"{task_id}.json"
            body = json.dumps(result, default=str)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=body.encode("utf-8"),
                    ContentType="application/json",
                ),
            )
            return True
        except Exception:
            logger.exception("Failed to upload result to S3 bucket %s", self._bucket)
            return False

    async def flush(self) -> None:
        """Flush is a no-op for S3; each send is an individual upload."""

    async def close(self) -> None:
        """Close the S3 client (release resources)."""
        self._client = None
        self._available = False


class WebhookStream:
    """Streams results via HTTP POST to a webhook URL.

    Sends each result as a JSON payload. Supports configurable headers
    and timeout.
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize webhook stream backend.

        Args:
            url: Webhook URL to POST results to.
            headers: Optional HTTP headers to include in requests.
            timeout: Request timeout in seconds.
        """
        self._url = url
        self._headers = headers or {}
        self._timeout = timeout
        self._session: Any = None

    def _get_session(self) -> Any:
        """Get or create a requests Session (lazy init).

        Returns:
            A ``requests.Session`` instance.
        """
        if self._session is None:
            import requests

            self._session = requests.Session()
            self._session.headers.update({"Content-Type": "application/json"})
            self._session.headers.update(self._headers)
        return self._session

    async def send(self, result: dict) -> bool:
        """POST a result as JSON to the webhook URL.

        Args:
            result: Evaluation result dictionary.

        Returns:
            True if the request returned a 2xx status, False otherwise.
        """
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, self._post, result)
            success = 200 <= response.status_code < 300
            if not success:
                logger.warning(
                    "Webhook returned status %d for %s",
                    response.status_code,
                    self._url,
                )
            return success
        except Exception:
            logger.exception("Failed to POST result to webhook %s", self._url)
            return False

    def _post(self, result: dict) -> Any:
        """Perform the synchronous HTTP POST (for executor).

        Args:
            result: Evaluation result dictionary.

        Returns:
            The ``requests.Response`` object.
        """
        session = self._get_session()
        return session.post(
            self._url,
            data=json.dumps(result, default=str),
            timeout=self._timeout,
        )

    async def flush(self) -> None:
        """Flush is a no-op for webhook; each send is an individual POST."""

    async def close(self) -> None:
        """Close the HTTP session and release resources."""
        if self._session is not None:
            self._session.close()
            self._session = None


class ResultStreamer:
    """Orchestrates streaming of results to multiple backends.

    Sends each result to all configured backends with optional buffering
    and retry logic. Streaming failures are logged but never propagated
    to the caller, ensuring the evaluation pipeline is not blocked.

    Args:
        backends: List of stream backends to send results to.
        buffer_size: Number of results to buffer before flushing.
            A value of 1 means results are sent immediately.
        max_retries: Maximum number of retry attempts per backend
            on failure.
        retry_delay: Base delay in seconds between retries
            (doubles on each retry).
    """

    def __init__(
        self,
        backends: list[StreamBackend],
        buffer_size: int = 1,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self._backends = list(backends)
        self._buffer_size = max(1, buffer_size)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._buffer: list[dict] = []
        self._sent_count = 0
        self._failed_count = 0

    @property
    def sent_count(self) -> int:
        """Number of results successfully sent to at least one backend."""
        return self._sent_count

    @property
    def failed_count(self) -> int:
        """Number of individual backend send failures (after retries)."""
        return self._failed_count

    async def send(self, result: dict) -> None:
        """Buffer a result and flush if the buffer is full.

        Args:
            result: Evaluation result dictionary to stream.
        """
        self._buffer.append(result)
        if len(self._buffer) >= self._buffer_size:
            await self.flush()

    async def flush(self) -> None:
        """Flush all buffered results to every backend.

        Each result is sent to each backend with retry logic. Failures
        are logged but do not raise exceptions.
        """
        if not self._buffer:
            return

        results_to_send = list(self._buffer)
        self._buffer.clear()

        for result in results_to_send:
            any_success = False
            for backend in self._backends:
                success = await self._send_with_retry(backend, result)
                if success:
                    any_success = True
            if any_success:
                self._sent_count += 1

        # Flush all backends
        for backend in self._backends:
            try:
                await backend.flush()
            except Exception:
                logger.exception("Failed to flush backend %s", type(backend).__name__)

    async def _send_with_retry(self, backend: StreamBackend, result: dict) -> bool:
        """Send a result to a single backend with retry logic.

        Uses exponential backoff between retries.

        Args:
            backend: The stream backend to send to.
            result: Evaluation result dictionary.

        Returns:
            True if the send eventually succeeded, False after all
            retries are exhausted.
        """
        delay = self._retry_delay
        for attempt in range(self._max_retries):
            try:
                success = await backend.send(result)
                if success:
                    return True
            except Exception:
                logger.exception(
                    "Exception sending to %s (attempt %d/%d)",
                    type(backend).__name__,
                    attempt + 1,
                    self._max_retries,
                )
            if attempt < self._max_retries - 1:
                await asyncio.sleep(delay)
                delay *= 2

        self._failed_count += 1
        logger.warning(
            "All %d retries exhausted for %s",
            self._max_retries,
            type(backend).__name__,
        )
        return False

    async def close(self) -> None:
        """Flush remaining buffer and close all backends."""
        await self.flush()
        for backend in self._backends:
            try:
                await backend.close()
            except Exception:
                logger.exception("Failed to close backend %s", type(backend).__name__)


@dataclass
class StreamConfig:
    """Configuration for a single stream backend.

    Attributes:
        backend_type: Type of backend (``"local"``, ``"s3"``, ``"webhook"``).
        path: File path for local backend.
        url: URL for webhook backend.
        bucket: S3 bucket name.
        prefix: S3 key prefix.
        headers: HTTP headers for webhook backend.
        region_name: AWS region for S3 backend.
        endpoint_url: Custom endpoint URL for S3-compatible services.
        timeout: Request timeout for webhook backend (seconds).
    """

    backend_type: str
    path: str | None = None
    url: str | None = None
    bucket: str | None = None
    prefix: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    region_name: str | None = None
    endpoint_url: str | None = None
    timeout: float = 30.0


def create_backend(config: StreamConfig) -> StreamBackend | None:
    """Create a single stream backend from configuration.

    Args:
        config: Stream backend configuration.

    Returns:
        A stream backend instance, or None if the configuration is
        invalid or the backend cannot be initialized.
    """
    backend_type = config.backend_type.lower()

    if backend_type == "local":
        if not config.path:
            logger.error("Local stream backend requires a 'path'")
            return None
        return LocalFileStream(path=config.path)

    elif backend_type == "s3":
        if not config.bucket:
            logger.error("S3 stream backend requires a 'bucket'")
            return None
        return S3Stream(
            bucket=config.bucket,
            prefix=config.prefix or "",
            region_name=config.region_name,
            endpoint_url=config.endpoint_url,
        )

    elif backend_type == "webhook":
        if not config.url:
            logger.error("Webhook stream backend requires a 'url'")
            return None
        return WebhookStream(
            url=config.url,
            headers=config.headers,
            timeout=config.timeout,
        )

    else:
        logger.error("Unknown stream backend type: %s", config.backend_type)
        return None


def create_streamer(
    configs: list[StreamConfig],
    buffer_size: int = 1,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> ResultStreamer:
    """Factory function to create a ResultStreamer from configuration.

    Creates backends for each valid configuration entry and returns
    a ``ResultStreamer`` that dispatches to all of them.

    Args:
        configs: List of stream backend configurations.
        buffer_size: Number of results to buffer before flushing.
        max_retries: Maximum retry attempts per backend on failure.
        retry_delay: Base delay in seconds between retries.

    Returns:
        Configured ResultStreamer instance. If no valid backends could
        be created, the streamer will have an empty backend list and
        all send operations will be no-ops.
    """
    backends: list[StreamBackend] = []
    for config in configs:
        backend = create_backend(config)
        if backend is not None:
            backends.append(backend)

    if not backends:
        logger.warning("No valid stream backends configured; streaming will be a no-op")

    return ResultStreamer(
        backends=backends,
        buffer_size=buffer_size,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )
