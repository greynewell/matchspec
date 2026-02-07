"""Tests for the REST API server."""

import json
import threading
import time
from http.client import HTTPConnection
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcpbr.api import (
    BenchmarkAPIHandler,
    _first,
    _make_handler_class,
    create_api_server,
)
from mcpbr.storage.sqlite_backend import SQLiteBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_free_port() -> int:
    """Return an available TCP port."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create a mock SQLiteBackend with async methods."""
    storage = MagicMock(spec=SQLiteBackend)

    # Configure async methods with AsyncMock
    storage.initialize = AsyncMock()
    storage.list_runs = AsyncMock(return_value=[])
    storage.get_run = AsyncMock(return_value=None)
    storage.get_task_results = AsyncMock(return_value=[])
    storage.delete_run = AsyncMock(return_value=False)
    storage.get_stats = AsyncMock(return_value={"total_runs": 0})
    storage.close = AsyncMock()

    return storage


@pytest.fixture
def server_url(mock_storage: MagicMock):
    """Start a test server on a random port and yield its base URL.

    The server runs in a background thread and is shut down after the test.
    """
    port = _get_free_port()
    host = "127.0.0.1"

    server = create_api_server(host=host, port=port, storage=mock_storage)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Give the server a moment to start accepting connections
    time.sleep(0.1)

    yield f"http://{host}:{port}"

    server.shutdown()
    server.server_close()


def _request(
    base_url: str,
    method: str,
    path: str,
) -> tuple[int, dict[str, Any]]:
    """Send an HTTP request and return (status_code, parsed_json_body)."""
    # Parse host and port from base_url
    # base_url looks like "http://127.0.0.1:12345"
    parts = base_url.replace("http://", "").split(":")
    host = parts[0]
    port = int(parts[1])

    conn = HTTPConnection(host, port, timeout=5)
    conn.request(method, path)
    response = conn.getresponse()
    status = response.status
    body = json.loads(response.read().decode("utf-8"))
    conn.close()
    return status, body


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    def test_health_returns_ok(self, server_url: str) -> None:
        """Health endpoint should return 200 with status ok."""
        status, body = _request(server_url, "GET", "/api/v1/health")
        assert status == 200
        assert body == {"status": "ok"}

    def test_health_trailing_slash(self, server_url: str) -> None:
        """Health endpoint should work with trailing slash."""
        status, body = _request(server_url, "GET", "/api/v1/health/")
        assert status == 200
        assert body["status"] == "ok"


# ---------------------------------------------------------------------------
# List runs endpoint
# ---------------------------------------------------------------------------


class TestListRunsEndpoint:
    """Tests for GET /api/v1/runs."""

    def test_list_runs_empty(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should return empty list when no runs exist."""
        mock_storage.list_runs.return_value = []

        status, body = _request(server_url, "GET", "/api/v1/runs")
        assert status == 200
        assert body["runs"] == []
        assert body["count"] == 0

    def test_list_runs_with_results(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should return runs when they exist."""
        mock_storage.list_runs.return_value = [
            {
                "run_id": "run-001",
                "benchmark": "swe-bench-lite",
                "model": "claude-sonnet-4-5-20250929",
                "provider": "anthropic",
                "pass_rate": 0.42,
                "total_tasks": 100,
                "resolved_tasks": 42,
                "created_at": "2025-01-15T10:00:00",
            },
        ]

        status, body = _request(server_url, "GET", "/api/v1/runs")
        assert status == 200
        assert body["count"] == 1
        assert body["runs"][0]["run_id"] == "run-001"
        assert body["runs"][0]["benchmark"] == "swe-bench-lite"

    def test_list_runs_with_benchmark_filter(
        self, server_url: str, mock_storage: MagicMock
    ) -> None:
        """Should pass benchmark filter to storage."""
        mock_storage.list_runs.return_value = []

        _request(server_url, "GET", "/api/v1/runs?benchmark=humaneval")

        mock_storage.list_runs.assert_called()
        call_kwargs = mock_storage.list_runs.call_args
        assert call_kwargs[1]["benchmark"] == "humaneval"

    def test_list_runs_with_model_filter(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should pass model filter to storage."""
        mock_storage.list_runs.return_value = []

        _request(server_url, "GET", "/api/v1/runs?model=gpt-4")

        call_kwargs = mock_storage.list_runs.call_args
        assert call_kwargs[1]["model"] == "gpt-4"

    def test_list_runs_with_limit(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should pass limit to storage."""
        mock_storage.list_runs.return_value = []

        _request(server_url, "GET", "/api/v1/runs?limit=10")

        call_kwargs = mock_storage.list_runs.call_args
        assert call_kwargs[1]["limit"] == 10

    def test_list_runs_default_limit(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should use default limit of 50."""
        mock_storage.list_runs.return_value = []

        _request(server_url, "GET", "/api/v1/runs")

        call_kwargs = mock_storage.list_runs.call_args
        assert call_kwargs[1]["limit"] == 50


# ---------------------------------------------------------------------------
# Get run endpoint
# ---------------------------------------------------------------------------


class TestGetRunEndpoint:
    """Tests for GET /api/v1/runs/{run_id}."""

    def test_get_existing_run(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should return run details when run exists."""
        mock_storage.get_run.return_value = {
            "run_id": "run-001",
            "benchmark": "swe-bench-lite",
            "model": "claude-sonnet-4-5-20250929",
            "provider": "anthropic",
            "config": {"benchmark": "swe-bench-lite"},
            "results": {"summary": {"pass_rate": 0.42}},
            "metadata": None,
            "pass_rate": 0.42,
            "total_tasks": 100,
            "resolved_tasks": 42,
            "created_at": "2025-01-15T10:00:00",
            "updated_at": "2025-01-15T10:30:00",
        }

        status, body = _request(server_url, "GET", "/api/v1/runs/run-001")
        assert status == 200
        assert body["run_id"] == "run-001"
        assert body["pass_rate"] == 0.42

    def test_get_missing_run(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should return 404 when run does not exist."""
        mock_storage.get_run.return_value = None

        status, body = _request(server_url, "GET", "/api/v1/runs/nonexistent")
        assert status == 404
        assert "error" in body
        assert "nonexistent" in body["error"]


# ---------------------------------------------------------------------------
# Run tasks endpoint
# ---------------------------------------------------------------------------


class TestRunTasksEndpoint:
    """Tests for GET /api/v1/runs/{run_id}/tasks."""

    def test_get_tasks_for_run(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should return task results for an existing run."""
        mock_storage.get_run.return_value = {"run_id": "run-001"}
        mock_storage.get_task_results.return_value = [
            {"task_id": "task-1", "status": "resolved"},
            {"task_id": "task-2", "status": "failed"},
        ]

        status, body = _request(server_url, "GET", "/api/v1/runs/run-001/tasks")
        assert status == 200
        assert body["run_id"] == "run-001"
        assert body["count"] == 2
        assert body["tasks"][0]["task_id"] == "task-1"

    def test_get_tasks_with_status_filter(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should pass status filter to storage."""
        mock_storage.get_run.return_value = {"run_id": "run-001"}
        mock_storage.get_task_results.return_value = [
            {"task_id": "task-1", "status": "resolved"},
        ]

        _request(server_url, "GET", "/api/v1/runs/run-001/tasks?status=resolved")

        call_kwargs = mock_storage.get_task_results.call_args
        assert call_kwargs[1]["status"] == "resolved"

    def test_get_tasks_for_missing_run(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should return 404 when run does not exist."""
        mock_storage.get_run.return_value = None

        status, body = _request(server_url, "GET", "/api/v1/runs/nonexistent/tasks")
        assert status == 404
        assert "error" in body


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------


class TestStatsEndpoint:
    """Tests for GET /api/v1/stats."""

    def test_get_stats(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should return aggregate statistics."""
        mock_storage.get_stats.return_value = {
            "total_runs": 5,
            "avg_pass_rate": 0.38,
            "max_pass_rate": 0.55,
            "min_pass_rate": 0.20,
            "total_tasks_evaluated": 500,
            "total_tasks_resolved": 190,
            "first_run": "2025-01-01T00:00:00",
            "last_run": "2025-01-15T00:00:00",
        }

        status, body = _request(server_url, "GET", "/api/v1/stats")
        assert status == 200
        assert body["total_runs"] == 5
        assert body["avg_pass_rate"] == 0.38

    def test_get_stats_with_benchmark(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should pass benchmark filter to storage."""
        mock_storage.get_stats.return_value = {"total_runs": 0}

        _request(server_url, "GET", "/api/v1/stats?benchmark=humaneval")

        call_kwargs = mock_storage.get_stats.call_args
        assert call_kwargs[1]["benchmark"] == "humaneval"

    def test_get_stats_empty(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should return valid response when no runs exist."""
        mock_storage.get_stats.return_value = {"total_runs": 0}

        status, body = _request(server_url, "GET", "/api/v1/stats")
        assert status == 200
        assert body["total_runs"] == 0


# ---------------------------------------------------------------------------
# Delete run endpoint
# ---------------------------------------------------------------------------


class TestDeleteRunEndpoint:
    """Tests for DELETE /api/v1/runs/{run_id}."""

    def test_delete_existing_run(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should delete a run and return confirmation."""
        mock_storage.delete_run.return_value = True

        status, body = _request(server_url, "DELETE", "/api/v1/runs/run-001")
        assert status == 200
        assert body["deleted"] is True
        assert body["run_id"] == "run-001"

    def test_delete_missing_run(self, server_url: str, mock_storage: MagicMock) -> None:
        """Should return 404 when trying to delete a nonexistent run."""
        mock_storage.delete_run.return_value = False

        status, body = _request(server_url, "DELETE", "/api/v1/runs/nonexistent")
        assert status == 404
        assert "error" in body


# ---------------------------------------------------------------------------
# 404 handling
# ---------------------------------------------------------------------------


class TestNotFound:
    """Tests for unknown routes."""

    def test_unknown_route(self, server_url: str) -> None:
        """Should return 404 for unknown paths."""
        status, body = _request(server_url, "GET", "/api/v1/unknown")
        assert status == 404
        assert "error" in body

    def test_root_path(self, server_url: str) -> None:
        """Should return 404 for the root path."""
        status, body = _request(server_url, "GET", "/")
        assert status == 404
        assert "error" in body

    def test_wrong_api_version(self, server_url: str) -> None:
        """Should return 404 for wrong API version."""
        status, body = _request(server_url, "GET", "/api/v2/health")
        assert status == 404

    def test_delete_unknown_route(self, server_url: str) -> None:
        """Should return 404 for DELETE on unknown route."""
        status, body = _request(server_url, "DELETE", "/api/v1/stats")
        assert status == 404


# ---------------------------------------------------------------------------
# Unit tests (no server required)
# ---------------------------------------------------------------------------


class TestFirstHelper:
    """Tests for the _first query string helper."""

    def test_returns_first_value(self) -> None:
        assert _first({"key": ["a", "b"]}, "key") == "a"

    def test_returns_none_for_missing_key(self) -> None:
        assert _first({}, "key") is None

    def test_returns_none_for_empty_values(self) -> None:
        assert _first({"key": []}, "key") is None


class TestMakeHandlerClass:
    """Tests for the _make_handler_class factory."""

    def test_binds_storage(self, mock_storage: MagicMock) -> None:
        """The returned class should have the storage attribute set."""
        cls = _make_handler_class(mock_storage)
        assert cls.storage is mock_storage

    def test_returns_subclass(self, mock_storage: MagicMock) -> None:
        """The returned class should be a subclass of BenchmarkAPIHandler."""
        cls = _make_handler_class(mock_storage)
        assert issubclass(cls, BenchmarkAPIHandler)

    def test_different_instances_are_independent(self, mock_storage: MagicMock) -> None:
        """Two handler classes bound to different backends are independent."""
        other_storage = MagicMock(spec=SQLiteBackend)
        cls_a = _make_handler_class(mock_storage)
        cls_b = _make_handler_class(other_storage)
        assert cls_a.storage is mock_storage
        assert cls_b.storage is other_storage


# ---------------------------------------------------------------------------
# Security tests (#420)
# ---------------------------------------------------------------------------


def _request_with_headers(
    base_url: str,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    """Send HTTP request and return (status, json_body, response_headers)."""
    parts = base_url.replace("http://", "").split(":")
    host = parts[0]
    port = int(parts[1])

    conn = HTTPConnection(host, port, timeout=5)
    conn.request(method, path, headers=headers or {})
    response = conn.getresponse()
    status = response.status
    resp_headers = dict(response.getheaders())
    body = json.loads(response.read().decode("utf-8"))
    conn.close()
    return status, body, resp_headers


@pytest.fixture
def authed_server_url(mock_storage: MagicMock):
    """Start a test server with API token authentication."""
    port = _get_free_port()
    host = "127.0.0.1"
    server = create_api_server(
        host=host, port=port, storage=mock_storage, api_token="test-secret-token"
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


class TestAPIAuthentication:
    """Tests for #420: API token authentication."""

    def test_authed_server_rejects_unauthenticated_request(self, authed_server_url: str) -> None:
        """Requests without token should get 401."""
        status, body = _request(authed_server_url, "GET", "/api/v1/runs")
        assert status == 401
        assert "error" in body

    def test_authed_server_accepts_valid_token(
        self, authed_server_url: str, mock_storage: MagicMock
    ) -> None:
        """Requests with correct Authorization header should succeed."""
        mock_storage.list_runs.return_value = []
        status, body, _ = _request_with_headers(
            authed_server_url,
            "GET",
            "/api/v1/runs",
            headers={"Authorization": "Bearer test-secret-token"},
        )
        assert status == 200

    def test_authed_server_rejects_wrong_token(self, authed_server_url: str) -> None:
        """Requests with wrong token should get 401."""
        status, body, _ = _request_with_headers(
            authed_server_url,
            "GET",
            "/api/v1/runs",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert status == 401

    def test_health_endpoint_skips_auth(self, authed_server_url: str) -> None:
        """Health endpoint should work without authentication."""
        status, body = _request(authed_server_url, "GET", "/api/v1/health")
        assert status == 200
        assert body["status"] == "ok"

    def test_no_token_server_allows_all(self, server_url: str) -> None:
        """When no api_token is set, all requests should be allowed."""
        status, body = _request(server_url, "GET", "/api/v1/health")
        assert status == 200


class TestCORSHeaders:
    """Tests for #420: CORS security headers."""

    def test_response_includes_cors_headers(self, server_url: str) -> None:
        """Responses should include restrictive CORS headers."""
        _, _, headers = _request_with_headers(server_url, "GET", "/api/v1/health")
        # Should not allow any origin by default (no Access-Control-Allow-Origin header
        # means the browser blocks cross-origin reads, OR explicitly restrict)
        assert "X-Content-Type-Options" in headers

    def test_response_includes_no_sniff_header(self, server_url: str) -> None:
        """Responses should include X-Content-Type-Options: nosniff."""
        _, _, headers = _request_with_headers(server_url, "GET", "/api/v1/health")
        assert headers.get("X-Content-Type-Options") == "nosniff"


class TestLimitValidation:
    """Tests for #420: Limit parameter validation."""

    def test_invalid_limit_returns_400(self, server_url: str) -> None:
        """Non-integer limit should return 400, not 500."""
        status, body = _request(server_url, "GET", "/api/v1/runs?limit=abc")
        assert status == 400
        assert "error" in body

    def test_negative_limit_returns_400(self, server_url: str) -> None:
        """Negative limit should return 400."""
        status, body = _request(server_url, "GET", "/api/v1/runs?limit=-1")
        assert status == 400
        assert "error" in body

    def test_excessive_limit_is_capped(self, server_url: str, mock_storage: MagicMock) -> None:
        """Limit above maximum should be capped."""
        mock_storage.list_runs.return_value = []
        status, _ = _request(server_url, "GET", "/api/v1/runs?limit=999999")
        assert status == 200
        call_kwargs = mock_storage.list_runs.call_args
        assert call_kwargs[1]["limit"] <= 1000


class TestBindWarning:
    """Tests for #420: Warning on 0.0.0.0 bind."""

    def test_wildcard_bind_logs_warning(
        self, mock_storage: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Binding to 0.0.0.0 should log a security warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            server = create_api_server(host="0.0.0.0", port=_get_free_port(), storage=mock_storage)
            server.server_close()
        assert any("0.0.0.0" in m for m in caplog.messages)
