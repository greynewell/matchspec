"""Tests for result streaming to external storage backends."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcpbr.result_streaming import (
    LocalFileStream,
    ResultStreamer,
    S3Stream,
    StreamConfig,
    WebhookStream,
    create_backend,
    create_streamer,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_result() -> dict:
    """A minimal evaluation result dictionary."""
    return {
        "instance_id": "django__django-12345",
        "resolved": True,
        "cost": 0.05,
        "tokens": {"input": 1000, "output": 500},
    }


@pytest.fixture
def sample_results() -> list[dict]:
    """Multiple evaluation result dictionaries."""
    return [
        {"instance_id": f"task-{i}", "resolved": i % 2 == 0, "cost": 0.01 * i} for i in range(5)
    ]


# ---------------------------------------------------------------------------
# LocalFileStream tests
# ---------------------------------------------------------------------------


class TestLocalFileStream:
    """Tests for the local JSONL file streaming backend."""

    async def test_send_creates_file(self, tmp_path: Path, sample_result: dict):
        """Test that send creates the JSONL file if it does not exist."""
        path = tmp_path / "results.jsonl"
        stream = LocalFileStream(path=path)

        success = await stream.send(sample_result)

        assert success is True
        assert path.exists()

    async def test_send_appends_jsonl(self, tmp_path: Path, sample_result: dict):
        """Test that each send appends a JSON line."""
        path = tmp_path / "results.jsonl"
        stream = LocalFileStream(path=path)

        await stream.send(sample_result)
        await stream.send({"instance_id": "task-2", "resolved": False})

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["instance_id"] == "django__django-12345"
        assert json.loads(lines[1])["instance_id"] == "task-2"

    async def test_send_creates_parent_directories(self, tmp_path: Path, sample_result: dict):
        """Test that parent directories are created automatically."""
        path = tmp_path / "deep" / "nested" / "dir" / "results.jsonl"
        stream = LocalFileStream(path=path)

        success = await stream.send(sample_result)

        assert success is True
        assert path.exists()

    async def test_send_handles_write_error(self, tmp_path: Path, sample_result: dict):
        """Test that write errors return False without raising."""
        path = tmp_path / "results.jsonl"
        stream = LocalFileStream(path=path)

        with patch("builtins.open", side_effect=OSError("disk full")):
            success = await stream.send(sample_result)

        assert success is False

    async def test_flush_is_noop(self, tmp_path: Path):
        """Test that flush completes without error."""
        stream = LocalFileStream(path=tmp_path / "results.jsonl")
        await stream.flush()  # Should not raise

    async def test_close_is_noop(self, tmp_path: Path):
        """Test that close completes without error."""
        stream = LocalFileStream(path=tmp_path / "results.jsonl")
        await stream.close()  # Should not raise

    async def test_send_serialises_non_json_types(self, tmp_path: Path):
        """Test that non-standard types are serialised via default=str."""
        path = tmp_path / "results.jsonl"
        stream = LocalFileStream(path=path)

        result = {"instance_id": "task-1", "path": Path("/some/path")}
        success = await stream.send(result)

        assert success is True
        line = json.loads(path.read_text().strip())
        assert line["path"] == "/some/path"


# ---------------------------------------------------------------------------
# S3Stream tests
# ---------------------------------------------------------------------------


class TestS3Stream:
    """Tests for the S3-compatible object store streaming backend."""

    def test_init_without_boto3(self):
        """Test graceful degradation when boto3 is not installed."""
        with patch.dict("sys.modules", {"boto3": None}):
            with patch("mcpbr.result_streaming.logger") as mock_logger:
                stream = S3Stream(bucket="test-bucket")

                assert stream._available is False
                mock_logger.warning.assert_called_once()

    def test_init_with_boto3(self):
        """Test successful initialization with a mocked boto3."""
        mock_boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            stream = S3Stream(bucket="test-bucket", prefix="results")

            assert stream._available is True
            assert stream._bucket == "test-bucket"
            assert stream._prefix == "results"

    async def test_send_returns_false_when_unavailable(self, sample_result: dict):
        """Test that send returns False if boto3 is not available."""
        stream = S3Stream.__new__(S3Stream)
        stream._available = False
        stream._client = None
        stream._bucket = "test"
        stream._prefix = ""

        success = await stream.send(sample_result)
        assert success is False

    async def test_send_success(self, sample_result: dict):
        """Test successful upload to S3."""
        stream = S3Stream.__new__(S3Stream)
        stream._available = True
        stream._bucket = "test-bucket"
        stream._prefix = "runs/1"

        mock_client = MagicMock()
        mock_client.put_object = MagicMock(return_value=None)
        stream._client = mock_client

        success = await stream.send(sample_result)

        assert success is True
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args
        assert call_kwargs[1]["Bucket"] == "test-bucket"
        assert call_kwargs[1]["Key"] == "runs/1/django__django-12345.json"
        assert call_kwargs[1]["ContentType"] == "application/json"

    async def test_send_uses_timestamp_key_when_no_instance_id(self):
        """Test fallback key when instance_id is missing."""
        stream = S3Stream.__new__(S3Stream)
        stream._available = True
        stream._bucket = "test-bucket"
        stream._prefix = ""

        mock_client = MagicMock()
        stream._client = mock_client

        result = {"resolved": True}
        success = await stream.send(result)

        assert success is True
        call_kwargs = mock_client.put_object.call_args
        key = call_kwargs[1]["Key"]
        assert key.startswith("result-")
        assert key.endswith(".json")

    async def test_send_handles_upload_error(self, sample_result: dict):
        """Test that upload errors return False without raising."""
        stream = S3Stream.__new__(S3Stream)
        stream._available = True
        stream._bucket = "test-bucket"
        stream._prefix = ""

        mock_client = MagicMock()
        mock_client.put_object = MagicMock(side_effect=Exception("access denied"))
        stream._client = mock_client

        success = await stream.send(sample_result)
        assert success is False

    async def test_close_releases_client(self):
        """Test that close sets client to None."""
        stream = S3Stream.__new__(S3Stream)
        stream._available = True
        stream._client = MagicMock()

        await stream.close()

        assert stream._client is None
        assert stream._available is False

    async def test_flush_is_noop(self):
        """Test that flush completes without error."""
        stream = S3Stream.__new__(S3Stream)
        stream._available = True
        stream._client = MagicMock()

        await stream.flush()  # Should not raise

    async def test_send_with_no_prefix(self, sample_result: dict):
        """Test S3 key generation when prefix is empty."""
        stream = S3Stream.__new__(S3Stream)
        stream._available = True
        stream._bucket = "test-bucket"
        stream._prefix = ""

        mock_client = MagicMock()
        stream._client = mock_client

        await stream.send(sample_result)

        call_kwargs = mock_client.put_object.call_args
        assert call_kwargs[1]["Key"] == "django__django-12345.json"


# ---------------------------------------------------------------------------
# WebhookStream tests
# ---------------------------------------------------------------------------


class TestWebhookStream:
    """Tests for the HTTP POST webhook streaming backend."""

    async def test_send_success(self, sample_result: dict):
        """Test successful POST to webhook URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        stream = WebhookStream(url="https://example.com/webhook")
        stream._session = mock_session

        success = await stream.send(sample_result)

        assert success is True
        mock_session.post.assert_called_once()

    async def test_send_non_2xx_returns_false(self, sample_result: dict):
        """Test that non-2xx responses are treated as failures."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        stream = WebhookStream(url="https://example.com/webhook")
        stream._session = mock_session

        success = await stream.send(sample_result)

        assert success is False

    async def test_send_handles_network_error(self, sample_result: dict):
        """Test that network errors return False without raising."""
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=ConnectionError("refused"))

        stream = WebhookStream(url="https://example.com/webhook")
        stream._session = mock_session

        success = await stream.send(sample_result)

        assert success is False

    async def test_send_with_custom_headers(self, sample_result: dict):
        """Test that custom headers are applied to the session."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        mock_session.headers = MagicMock()

        stream = WebhookStream(
            url="https://example.com/webhook",
            headers={"Authorization": "Bearer token123"},
        )
        stream._session = mock_session

        success = await stream.send(sample_result)

        assert success is True

    async def test_send_uses_configured_timeout(self, sample_result: dict):
        """Test that the configured timeout is passed to post()."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        stream = WebhookStream(url="https://example.com/webhook", timeout=10.0)
        stream._session = mock_session

        await stream.send(sample_result)

        call_kwargs = mock_session.post.call_args
        assert call_kwargs[1]["timeout"] == 10.0

    async def test_close_releases_session(self):
        """Test that close properly closes and releases the session."""
        mock_session = MagicMock()
        stream = WebhookStream(url="https://example.com/webhook")
        stream._session = mock_session

        await stream.close()

        mock_session.close.assert_called_once()
        assert stream._session is None

    async def test_close_when_no_session(self):
        """Test that close is safe when no session exists."""
        stream = WebhookStream(url="https://example.com/webhook")
        await stream.close()  # Should not raise

    async def test_flush_is_noop(self):
        """Test that flush completes without error."""
        stream = WebhookStream(url="https://example.com/webhook")
        await stream.flush()  # Should not raise

    async def test_lazy_session_creation(self, sample_result: dict):
        """Test that the requests session is created lazily on first send."""
        stream = WebhookStream(url="https://example.com/webhook")
        assert stream._session is None

        # Mock requests module to avoid real HTTP calls
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_session_instance = MagicMock()
        mock_session_instance.post = MagicMock(return_value=mock_response)
        mock_session_instance.headers = MagicMock()

        # Patch _get_session to return our mock and verify lazy init
        with patch.object(stream, "_get_session", return_value=mock_session_instance):
            success = await stream.send(sample_result)

        assert success is True
        mock_session_instance.post.assert_called_once()


# ---------------------------------------------------------------------------
# ResultStreamer tests
# ---------------------------------------------------------------------------


class TestResultStreamer:
    """Tests for the ResultStreamer orchestrator."""

    def _make_backend(self, send_return: bool = True) -> MagicMock:
        """Create a mock StreamBackend.

        Args:
            send_return: Value for send() to return.

        Returns:
            A MagicMock configured as a StreamBackend.
        """
        backend = MagicMock()
        backend.send = AsyncMock(return_value=send_return)
        backend.flush = AsyncMock()
        backend.close = AsyncMock()
        return backend

    async def test_send_dispatches_to_all_backends(self, sample_result: dict):
        """Test that send dispatches to every configured backend."""
        b1 = self._make_backend()
        b2 = self._make_backend()

        streamer = ResultStreamer(backends=[b1, b2], buffer_size=1)
        await streamer.send(sample_result)

        b1.send.assert_awaited_once_with(sample_result)
        b2.send.assert_awaited_once_with(sample_result)

    async def test_send_increments_sent_count(self, sample_result: dict):
        """Test that sent_count tracks successful sends."""
        backend = self._make_backend()
        streamer = ResultStreamer(backends=[backend], buffer_size=1)

        await streamer.send(sample_result)

        assert streamer.sent_count == 1

    async def test_buffering(self, sample_results: list[dict]):
        """Test that results are buffered until buffer_size is reached."""
        backend = self._make_backend()
        streamer = ResultStreamer(backends=[backend], buffer_size=3)

        # Send two results (below buffer size)
        await streamer.send(sample_results[0])
        await streamer.send(sample_results[1])

        # Backend should not have been called yet
        backend.send.assert_not_awaited()

        # Send third result to trigger flush
        await streamer.send(sample_results[2])

        assert backend.send.await_count == 3

    async def test_flush_sends_buffered_results(self, sample_result: dict):
        """Test that flush sends all buffered results."""
        backend = self._make_backend()
        streamer = ResultStreamer(backends=[backend], buffer_size=10)

        await streamer.send(sample_result)
        backend.send.assert_not_awaited()

        await streamer.flush()
        backend.send.assert_awaited_once_with(sample_result)

    async def test_flush_clears_buffer(self, sample_result: dict):
        """Test that flush empties the internal buffer."""
        backend = self._make_backend()
        streamer = ResultStreamer(backends=[backend], buffer_size=10)

        await streamer.send(sample_result)
        await streamer.flush()

        # Second flush should be a no-op
        backend.send.reset_mock()
        await streamer.flush()
        backend.send.assert_not_awaited()

    async def test_retry_on_failure(self, sample_result: dict):
        """Test that failed sends are retried up to max_retries times."""
        backend = self._make_backend(send_return=False)
        streamer = ResultStreamer(
            backends=[backend],
            buffer_size=1,
            max_retries=3,
            retry_delay=0.01,
        )

        await streamer.send(sample_result)

        assert backend.send.await_count == 3
        assert streamer.failed_count == 1
        assert streamer.sent_count == 0

    async def test_retry_succeeds_on_later_attempt(self, sample_result: dict):
        """Test that a send succeeds if a later retry works."""
        backend = self._make_backend()
        backend.send = AsyncMock(side_effect=[False, False, True])

        streamer = ResultStreamer(
            backends=[backend],
            buffer_size=1,
            max_retries=3,
            retry_delay=0.01,
        )

        await streamer.send(sample_result)

        assert backend.send.await_count == 3
        assert streamer.sent_count == 1
        assert streamer.failed_count == 0

    async def test_retry_on_exception(self, sample_result: dict):
        """Test retry when send raises an exception."""
        backend = self._make_backend()
        backend.send = AsyncMock(
            side_effect=[Exception("network error"), Exception("timeout"), True]
        )

        streamer = ResultStreamer(
            backends=[backend],
            buffer_size=1,
            max_retries=3,
            retry_delay=0.01,
        )

        await streamer.send(sample_result)

        assert backend.send.await_count == 3
        assert streamer.sent_count == 1

    async def test_partial_backend_failure(self, sample_result: dict):
        """Test that success on one backend counts even if another fails."""
        good = self._make_backend(send_return=True)
        bad = self._make_backend(send_return=False)

        streamer = ResultStreamer(
            backends=[good, bad],
            buffer_size=1,
            max_retries=1,
            retry_delay=0.01,
        )

        await streamer.send(sample_result)

        assert streamer.sent_count == 1  # At least one backend succeeded
        assert streamer.failed_count == 1  # One backend failed

    async def test_close_flushes_and_closes(self, sample_result: dict):
        """Test that close flushes the buffer and closes all backends."""
        backend = self._make_backend()
        streamer = ResultStreamer(backends=[backend], buffer_size=10)

        await streamer.send(sample_result)
        await streamer.close()

        # Should have flushed the buffered result
        backend.send.assert_awaited_once_with(sample_result)
        backend.close.assert_awaited_once()

    async def test_close_handles_backend_error(self, sample_result: dict):
        """Test that close does not raise even if a backend fails to close."""
        backend = self._make_backend()
        backend.close = AsyncMock(side_effect=Exception("cleanup error"))

        streamer = ResultStreamer(backends=[backend], buffer_size=1)
        await streamer.send(sample_result)

        # Should not raise
        await streamer.close()

    async def test_no_backends(self, sample_result: dict):
        """Test that a streamer with no backends is a safe no-op."""
        streamer = ResultStreamer(backends=[], buffer_size=1)

        await streamer.send(sample_result)
        await streamer.flush()
        await streamer.close()

        assert streamer.sent_count == 0
        assert streamer.failed_count == 0

    async def test_multiple_results_sequential(self, sample_results: list[dict]):
        """Test sending multiple results in sequence."""
        backend = self._make_backend()
        streamer = ResultStreamer(backends=[backend], buffer_size=1)

        for result in sample_results:
            await streamer.send(result)

        assert streamer.sent_count == len(sample_results)
        assert backend.send.await_count == len(sample_results)

    async def test_buffer_size_one_sends_immediately(self, sample_result: dict):
        """Test that buffer_size=1 sends results immediately."""
        backend = self._make_backend()
        streamer = ResultStreamer(backends=[backend], buffer_size=1)

        await streamer.send(sample_result)

        backend.send.assert_awaited_once()

    async def test_exponential_backoff(self, sample_result: dict):
        """Test that retry delay doubles on each attempt."""
        backend = self._make_backend(send_return=False)
        delays_observed: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays_observed.append(delay)

        streamer = ResultStreamer(
            backends=[backend],
            buffer_size=1,
            max_retries=4,
            retry_delay=0.1,
        )

        with patch("mcpbr.result_streaming.asyncio.sleep", side_effect=mock_sleep):
            await streamer.send(sample_result)

        # Should have 3 delays (between 4 attempts)
        assert len(delays_observed) == 3
        assert abs(delays_observed[0] - 0.1) < 0.001
        assert abs(delays_observed[1] - 0.2) < 0.001
        assert abs(delays_observed[2] - 0.4) < 0.001


# ---------------------------------------------------------------------------
# StreamConfig and factory tests
# ---------------------------------------------------------------------------


class TestStreamConfig:
    """Tests for the StreamConfig dataclass."""

    def test_local_config(self):
        """Test creating a local file stream config."""
        config = StreamConfig(backend_type="local", path="/tmp/results.jsonl")

        assert config.backend_type == "local"
        assert config.path == "/tmp/results.jsonl"

    def test_s3_config(self):
        """Test creating an S3 stream config."""
        config = StreamConfig(
            backend_type="s3",
            bucket="my-bucket",
            prefix="results/run-42",
            region_name="us-east-1",
        )

        assert config.backend_type == "s3"
        assert config.bucket == "my-bucket"
        assert config.prefix == "results/run-42"
        assert config.region_name == "us-east-1"

    def test_webhook_config(self):
        """Test creating a webhook stream config."""
        config = StreamConfig(
            backend_type="webhook",
            url="https://example.com/hook",
            headers={"Authorization": "Bearer abc"},
            timeout=15.0,
        )

        assert config.backend_type == "webhook"
        assert config.url == "https://example.com/hook"
        assert config.headers == {"Authorization": "Bearer abc"}
        assert config.timeout == 15.0

    def test_defaults(self):
        """Test default values for optional fields."""
        config = StreamConfig(backend_type="local")

        assert config.path is None
        assert config.url is None
        assert config.bucket is None
        assert config.prefix is None
        assert config.headers == {}
        assert config.region_name is None
        assert config.endpoint_url is None
        assert config.timeout == 30.0


class TestCreateBackend:
    """Tests for the create_backend factory function."""

    def test_create_local_backend(self, tmp_path: Path):
        """Test creating a local file stream backend."""
        config = StreamConfig(backend_type="local", path=str(tmp_path / "results.jsonl"))
        backend = create_backend(config)

        assert isinstance(backend, LocalFileStream)

    def test_create_local_backend_without_path(self):
        """Test that local backend creation fails without a path."""
        config = StreamConfig(backend_type="local")
        backend = create_backend(config)

        assert backend is None

    def test_create_s3_backend(self):
        """Test creating an S3 stream backend with mocked boto3."""
        mock_boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            config = StreamConfig(backend_type="s3", bucket="test-bucket")
            backend = create_backend(config)

            assert isinstance(backend, S3Stream)

    def test_create_s3_backend_without_bucket(self):
        """Test that S3 backend creation fails without a bucket."""
        config = StreamConfig(backend_type="s3")
        backend = create_backend(config)

        assert backend is None

    def test_create_webhook_backend(self):
        """Test creating a webhook stream backend."""
        config = StreamConfig(backend_type="webhook", url="https://example.com/hook")
        backend = create_backend(config)

        assert isinstance(backend, WebhookStream)

    def test_create_webhook_backend_without_url(self):
        """Test that webhook backend creation fails without a URL."""
        config = StreamConfig(backend_type="webhook")
        backend = create_backend(config)

        assert backend is None

    def test_create_unknown_backend(self):
        """Test that unknown backend types return None."""
        config = StreamConfig(backend_type="redis")
        backend = create_backend(config)

        assert backend is None

    def test_case_insensitive_backend_type(self, tmp_path: Path):
        """Test that backend_type matching is case-insensitive."""
        config = StreamConfig(backend_type="LOCAL", path=str(tmp_path / "results.jsonl"))
        backend = create_backend(config)

        assert isinstance(backend, LocalFileStream)


class TestCreateStreamer:
    """Tests for the create_streamer factory function."""

    def test_create_with_valid_configs(self, tmp_path: Path):
        """Test creating a streamer with valid configurations."""
        configs = [
            StreamConfig(backend_type="local", path=str(tmp_path / "a.jsonl")),
            StreamConfig(backend_type="local", path=str(tmp_path / "b.jsonl")),
        ]

        streamer = create_streamer(configs)

        assert len(streamer._backends) == 2

    def test_create_with_invalid_configs(self):
        """Test creating a streamer when all configs are invalid."""
        configs = [
            StreamConfig(backend_type="local"),  # Missing path
            StreamConfig(backend_type="webhook"),  # Missing url
        ]

        streamer = create_streamer(configs)

        assert len(streamer._backends) == 0

    def test_create_with_mixed_configs(self, tmp_path: Path):
        """Test creating a streamer with a mix of valid and invalid configs."""
        configs = [
            StreamConfig(backend_type="local", path=str(tmp_path / "results.jsonl")),
            StreamConfig(backend_type="webhook"),  # Invalid: no url
        ]

        streamer = create_streamer(configs)

        assert len(streamer._backends) == 1

    def test_create_with_custom_parameters(self, tmp_path: Path):
        """Test that custom buffer_size, max_retries, retry_delay are passed."""
        configs = [StreamConfig(backend_type="local", path=str(tmp_path / "results.jsonl"))]

        streamer = create_streamer(configs, buffer_size=5, max_retries=10, retry_delay=2.0)

        assert streamer._buffer_size == 5
        assert streamer._max_retries == 10
        assert streamer._retry_delay == 2.0

    def test_create_empty_configs(self):
        """Test creating a streamer with an empty config list."""
        streamer = create_streamer([])

        assert len(streamer._backends) == 0

    async def test_end_to_end_local_streaming(self, tmp_path: Path):
        """Integration test: stream results to a local JSONL file end-to-end."""
        path = tmp_path / "e2e_results.jsonl"
        configs = [StreamConfig(backend_type="local", path=str(path))]

        streamer = create_streamer(configs, buffer_size=2)

        await streamer.send({"instance_id": "task-1", "resolved": True})
        # Buffer not full yet, file should not have content
        assert not path.exists() or path.read_text() == ""

        await streamer.send({"instance_id": "task-2", "resolved": False})
        # Buffer full, file should now have two lines
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

        await streamer.send({"instance_id": "task-3", "resolved": True})
        await streamer.close()

        # After close, all three results should be flushed
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 3

        for line in lines:
            data = json.loads(line)
            assert "instance_id" in data


# ---------------------------------------------------------------------------
# Protocol compliance tests
# ---------------------------------------------------------------------------


class TestStreamBackendProtocol:
    """Tests that all backends satisfy the StreamBackend protocol."""

    def test_local_file_stream_is_stream_backend(self, tmp_path: Path):
        """Test that LocalFileStream satisfies the StreamBackend protocol."""
        from mcpbr.result_streaming import StreamBackend

        stream = LocalFileStream(path=tmp_path / "test.jsonl")
        assert isinstance(stream, StreamBackend)

    def test_s3_stream_is_stream_backend(self):
        """Test that S3Stream satisfies the StreamBackend protocol."""
        from mcpbr.result_streaming import StreamBackend

        stream = S3Stream.__new__(S3Stream)
        stream._available = False
        stream._client = None
        stream._bucket = "test"
        stream._prefix = ""
        assert isinstance(stream, StreamBackend)

    def test_webhook_stream_is_stream_backend(self):
        """Test that WebhookStream satisfies the StreamBackend protocol."""
        from mcpbr.result_streaming import StreamBackend

        stream = WebhookStream(url="https://example.com/hook")
        assert isinstance(stream, StreamBackend)
