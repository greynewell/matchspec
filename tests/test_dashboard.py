"""Tests for the real-time evaluation dashboard."""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from mcpbr.dashboard import (
    DASHBOARD_HTML,
    DashboardServer,
    DashboardState,
    TaskStatus,
    _broadcast,
    _check_dependencies,
    create_app,
)

# ---------------------------------------------------------------------------
# TaskStatus tests
# ---------------------------------------------------------------------------


class TestTaskStatus:
    """Tests for the TaskStatus dataclass."""

    def test_defaults(self) -> None:
        """Test default values are set correctly."""
        task = TaskStatus(instance_id="django__django-12345")
        assert task.instance_id == "django__django-12345"
        assert task.status == "pending"
        assert task.started_at is None
        assert task.finished_at is None
        assert task.error is None

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        task = TaskStatus(
            instance_id="task-1",
            status="resolved",
            started_at=1000.0,
            finished_at=1060.0,
            error=None,
        )
        result = task.to_dict()

        assert result == {
            "instance_id": "task-1",
            "status": "resolved",
            "started_at": 1000.0,
            "finished_at": 1060.0,
            "error": None,
        }

    def test_to_dict_with_error(self) -> None:
        """Test serialization includes error message."""
        task = TaskStatus(
            instance_id="task-2",
            status="failed",
            started_at=1000.0,
            finished_at=1010.0,
            error="Timeout exceeded",
        )
        result = task.to_dict()

        assert result["error"] == "Timeout exceeded"
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# DashboardState tests
# ---------------------------------------------------------------------------


class TestDashboardState:
    """Tests for the DashboardState dataclass."""

    def test_defaults(self) -> None:
        """Test default values are sensible."""
        state = DashboardState()
        assert state.total_tasks == 0
        assert state.completed_tasks == 0
        assert state.resolved_tasks == 0
        assert state.failed_tasks == 0
        assert state.current_task_id is None
        assert state.is_paused is False
        assert state.is_cancelled is False
        assert isinstance(state.task_results, list)
        assert len(state.task_results) == 0

    def test_start_task(self) -> None:
        """Test marking a task as running."""
        state = DashboardState(total_tasks=5)
        state.start_task("task-1")

        assert state.current_task_id == "task-1"
        assert len(state.task_results) == 1
        assert state.task_results[0].status == "running"
        assert state.task_results[0].started_at is not None

    def test_start_task_creates_task_status(self) -> None:
        """Test that start_task creates a TaskStatus entry."""
        state = DashboardState(total_tasks=3)
        state.start_task("instance-abc")

        task = state.task_results[0]
        assert task.instance_id == "instance-abc"
        assert task.status == "running"

    def test_update_task_resolved(self) -> None:
        """Test updating a task as resolved."""
        state = DashboardState(total_tasks=5)
        state.start_task("task-1")
        state.update_task("task-1", resolved=True)

        assert state.completed_tasks == 1
        assert state.resolved_tasks == 1
        assert state.failed_tasks == 0
        assert state.current_task_id is None  # cleared after completion
        assert state.task_results[0].status == "resolved"
        assert state.task_results[0].finished_at is not None

    def test_update_task_failed(self) -> None:
        """Test updating a task as failed (not resolved)."""
        state = DashboardState(total_tasks=5)
        state.start_task("task-1")
        state.update_task("task-1", resolved=False)

        assert state.completed_tasks == 1
        assert state.resolved_tasks == 0
        assert state.failed_tasks == 1
        assert state.task_results[0].status == "failed"

    def test_update_task_with_error(self) -> None:
        """Test updating a task with an error message."""
        state = DashboardState(total_tasks=5)
        state.start_task("task-1")
        state.update_task("task-1", error="Docker container crashed")

        assert state.completed_tasks == 1
        assert state.failed_tasks == 1
        assert state.resolved_tasks == 0
        assert state.task_results[0].status == "failed"
        assert state.task_results[0].error == "Docker container crashed"

    def test_update_task_clears_current_task(self) -> None:
        """Test that completing the current task clears current_task_id."""
        state = DashboardState(total_tasks=5)
        state.start_task("task-1")
        assert state.current_task_id == "task-1"

        state.update_task("task-1", resolved=True)
        assert state.current_task_id is None

    def test_update_task_does_not_clear_different_current_task(self) -> None:
        """Test that completing a non-current task does not clear current_task_id."""
        state = DashboardState(total_tasks=5)
        state.start_task("task-1")
        state.start_task("task-2")  # overwrites current
        assert state.current_task_id == "task-2"

        state.update_task("task-1", resolved=True)
        assert state.current_task_id == "task-2"  # unchanged

    def test_multiple_tasks_workflow(self) -> None:
        """Test a realistic multi-task workflow."""
        state = DashboardState(total_tasks=4)

        state.start_task("task-1")
        state.update_task("task-1", resolved=True)

        state.start_task("task-2")
        state.update_task("task-2", resolved=False)

        state.start_task("task-3")
        state.update_task("task-3", error="Timeout")

        state.start_task("task-4")
        state.update_task("task-4", resolved=True)

        assert state.completed_tasks == 4
        assert state.resolved_tasks == 2
        assert state.failed_tasks == 2
        assert len(state.task_results) == 4

    def test_get_resolution_rate_no_tasks(self) -> None:
        """Test resolution rate is 0.0 when no tasks completed."""
        state = DashboardState(total_tasks=5)
        assert state.get_resolution_rate() == 0.0

    def test_get_resolution_rate(self) -> None:
        """Test resolution rate calculation."""
        state = DashboardState(total_tasks=10)
        for i in range(10):
            state.start_task(f"task-{i}")
            state.update_task(f"task-{i}", resolved=(i < 7))

        rate = state.get_resolution_rate()
        assert abs(rate - 0.7) < 1e-9

    def test_get_eta_seconds_no_tasks(self) -> None:
        """Test ETA is None when no tasks completed."""
        state = DashboardState(total_tasks=10)
        assert state.get_eta_seconds() is None

    def test_get_eta_seconds(self) -> None:
        """Test ETA calculation based on average completion time."""
        state = DashboardState(total_tasks=10)
        # Simulate: started 10 seconds ago, 5 tasks done => avg 2s/task => 5 left => 10s
        state.start_time = time.time() - 10.0
        state.completed_tasks = 5

        eta = state.get_eta_seconds()
        assert eta is not None
        # 10s elapsed / 5 completed = 2s avg * 5 remaining = ~10s
        assert abs(eta - 10.0) < 1.0  # Allow small timing delta

    def test_get_eta_seconds_almost_done(self) -> None:
        """Test ETA when almost all tasks are complete."""
        state = DashboardState(total_tasks=100)
        state.start_time = time.time() - 100.0
        state.completed_tasks = 99

        eta = state.get_eta_seconds()
        assert eta is not None
        # 100s / 99 tasks ~ 1.01s avg * 1 remaining ~ 1.01s
        assert eta < 3.0

    def test_to_dict(self) -> None:
        """Test full state serialization."""
        state = DashboardState(total_tasks=5)
        state.start_task("task-1")
        state.update_task("task-1", resolved=True)

        result = state.to_dict()

        assert result["total_tasks"] == 5
        assert result["completed_tasks"] == 1
        assert result["resolved_tasks"] == 1
        assert result["failed_tasks"] == 0
        assert result["current_task_id"] is None
        assert isinstance(result["resolution_rate"], float)
        assert isinstance(result["elapsed_seconds"], float)
        assert result["is_paused"] is False
        assert result["is_cancelled"] is False
        assert isinstance(result["task_results"], list)
        assert len(result["task_results"]) == 1
        assert result["task_results"][0]["instance_id"] == "task-1"

    def test_to_dict_is_json_serializable(self) -> None:
        """Test that to_dict output can be serialized to JSON."""
        state = DashboardState(total_tasks=3)
        state.start_task("task-1")
        state.update_task("task-1", resolved=True)
        state.start_task("task-2")
        state.update_task("task-2", error="boom")

        data = state.to_dict()
        serialized = json.dumps(data)
        deserialized = json.loads(serialized)

        assert deserialized["total_tasks"] == 3
        assert deserialized["completed_tasks"] == 2

    def test_pause_and_cancel_flags(self) -> None:
        """Test pause and cancel flag manipulation."""
        state = DashboardState()
        assert state.is_paused is False
        assert state.is_cancelled is False

        state.is_paused = True
        assert state.to_dict()["is_paused"] is True

        state.is_cancelled = True
        assert state.to_dict()["is_cancelled"] is True

    def test_find_or_create_task_existing(self) -> None:
        """Test that _find_or_create_task returns existing task."""
        state = DashboardState(total_tasks=1)
        state.start_task("task-1")

        task = state._find_or_create_task("task-1")
        assert task.instance_id == "task-1"
        assert len(state.task_results) == 1  # no duplicate created

    def test_find_or_create_task_new(self) -> None:
        """Test that _find_or_create_task creates a new task if absent."""
        state = DashboardState(total_tasks=1)
        task = state._find_or_create_task("task-new")

        assert task.instance_id == "task-new"
        assert len(state.task_results) == 1


# ---------------------------------------------------------------------------
# FastAPI app + endpoint tests
# ---------------------------------------------------------------------------


class TestCreateApp:
    """Tests for the create_app factory and its endpoints."""

    @pytest.fixture
    def state(self) -> DashboardState:
        """Provide a pre-populated DashboardState for endpoint tests."""
        s = DashboardState(total_tasks=10)
        s.start_task("task-1")
        s.update_task("task-1", resolved=True)
        s.start_task("task-2")
        s.update_task("task-2", resolved=False)
        return s

    @pytest.fixture
    def client(self, state: DashboardState):
        """Create a TestClient for the FastAPI app.

        Skips if httpx is not installed (required by Starlette TestClient).
        """
        pytest.importorskip("fastapi")
        pytest.importorskip("httpx")
        from starlette.testclient import TestClient

        app = create_app(state)
        return TestClient(app)

    def test_index_returns_html(self, client) -> None:
        """Test that GET / returns the dashboard HTML page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "mcpbr Evaluation Dashboard" in response.text
        assert "text/html" in response.headers["content-type"]

    def test_api_status(self, client, state: DashboardState) -> None:
        """Test that GET /api/status returns correct JSON."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()

        assert data["total_tasks"] == 10
        assert data["completed_tasks"] == 2
        assert data["resolved_tasks"] == 1
        assert data["failed_tasks"] == 1
        assert isinstance(data["resolution_rate"], float)
        assert isinstance(data["task_results"], list)

    def test_api_pause(self, client, state: DashboardState) -> None:
        """Test that POST /api/pause sets is_paused."""
        assert state.is_paused is False
        response = client.post("/api/pause")
        assert response.status_code == 200
        assert response.json()["status"] == "paused"
        assert state.is_paused is True

    def test_api_resume(self, client, state: DashboardState) -> None:
        """Test that POST /api/resume clears is_paused."""
        state.is_paused = True
        response = client.post("/api/resume")
        assert response.status_code == 200
        assert response.json()["status"] == "resumed"
        assert state.is_paused is False

    def test_api_cancel(self, client, state: DashboardState) -> None:
        """Test that POST /api/cancel sets is_cancelled."""
        assert state.is_cancelled is False
        response = client.post("/api/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        assert state.is_cancelled is True
        assert state.is_paused is False

    def test_api_pause_after_cancel_returns_409(self, client, state: DashboardState) -> None:
        """Test that pausing after cancel returns a 409 conflict."""
        state.is_cancelled = True
        response = client.post("/api/pause")
        assert response.status_code == 409
        assert "cancelled" in response.json()["error"].lower()

    def test_api_resume_after_cancel_returns_409(self, client, state: DashboardState) -> None:
        """Test that resuming after cancel returns a 409 conflict."""
        state.is_cancelled = True
        response = client.post("/api/resume")
        assert response.status_code == 409
        assert "cancelled" in response.json()["error"].lower()

    def test_api_status_after_pause_shows_paused(self, client, state: DashboardState) -> None:
        """Test that status reflects paused state."""
        client.post("/api/pause")
        response = client.get("/api/status")
        assert response.json()["is_paused"] is True

    def test_api_status_reflects_task_updates(self, client, state: DashboardState) -> None:
        """Test that status updates when state is mutated externally."""
        state.start_task("task-3")
        state.update_task("task-3", resolved=True)

        response = client.get("/api/status")
        data = response.json()
        assert data["completed_tasks"] == 3
        assert data["resolved_tasks"] == 2


# ---------------------------------------------------------------------------
# WebSocket tests
# ---------------------------------------------------------------------------


class TestWebSocket:
    """Tests for the WebSocket endpoint."""

    @pytest.fixture
    def state(self) -> DashboardState:
        """Provide a DashboardState for WebSocket tests."""
        return DashboardState(total_tasks=5)

    @pytest.fixture
    def client(self, state: DashboardState):
        """Create a TestClient for WebSocket testing."""
        pytest.importorskip("fastapi")
        pytest.importorskip("httpx")
        from starlette.testclient import TestClient

        app = create_app(state)
        return TestClient(app)

    def test_websocket_receives_initial_state(self, client, state: DashboardState) -> None:
        """Test that connecting to /ws receives the initial state."""
        with client.websocket_connect("/ws") as ws:
            data = json.loads(ws.receive_text())
            assert data["total_tasks"] == 5
            assert data["completed_tasks"] == 0

    def test_websocket_receives_periodic_updates(self, client, state: DashboardState) -> None:
        """Test that WebSocket sends periodic updates."""
        with client.websocket_connect("/ws") as ws:
            # Receive initial state
            first = json.loads(ws.receive_text())
            assert first["completed_tasks"] == 0

            # Mutate state
            state.start_task("task-1")
            state.update_task("task-1", resolved=True)

            # Receive a periodic update (within 2s)
            second = json.loads(ws.receive_text())
            assert second["completed_tasks"] == 1
            assert second["resolved_tasks"] == 1


# ---------------------------------------------------------------------------
# Broadcast helper tests
# ---------------------------------------------------------------------------


class TestBroadcast:
    """Tests for the _broadcast async helper."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self) -> None:
        """Test that _broadcast sends to all connections."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        sockets: list = [ws1, ws2]

        await _broadcast({"hello": "world"}, sockets)

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()
        payload = json.loads(ws1.send_text.call_args[0][0])
        assert payload == {"hello": "world"}

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self) -> None:
        """Test that dead connections are removed."""
        ws_good = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("Connection closed")
        sockets: list = [ws_good, ws_dead]

        await _broadcast({"data": 1}, sockets)

        assert ws_dead not in sockets
        assert ws_good in sockets
        assert len(sockets) == 1

    @pytest.mark.asyncio
    async def test_broadcast_empty_list(self) -> None:
        """Test that broadcasting to an empty list is a no-op."""
        sockets: list = []
        await _broadcast({"data": 1}, sockets)
        assert len(sockets) == 0


# ---------------------------------------------------------------------------
# Dependency check tests
# ---------------------------------------------------------------------------


class TestCheckDependencies:
    """Tests for the _check_dependencies guard."""

    def test_check_dependencies_succeeds_when_installed(self) -> None:
        """Test no error when both fastapi and uvicorn are available."""
        pytest.importorskip("fastapi")
        pytest.importorskip("uvicorn")
        # Should not raise
        _check_dependencies()

    def test_check_dependencies_raises_when_fastapi_missing(self) -> None:
        """Test ImportError raised when fastapi is missing."""
        with (
            patch("mcpbr.dashboard.HAS_FASTAPI", False),
            pytest.raises(ImportError, match="fastapi"),
        ):
            _check_dependencies()

    def test_check_dependencies_raises_when_uvicorn_missing(self) -> None:
        """Test ImportError raised when uvicorn is missing."""
        with (
            patch("mcpbr.dashboard.HAS_UVICORN", False),
            pytest.raises(ImportError, match="uvicorn"),
        ):
            _check_dependencies()

    def test_check_dependencies_raises_when_both_missing(self) -> None:
        """Test ImportError lists both missing packages."""
        with (
            patch("mcpbr.dashboard.HAS_FASTAPI", False),
            patch("mcpbr.dashboard.HAS_UVICORN", False),
            pytest.raises(ImportError, match=r"fastapi.*uvicorn"),
        ):
            _check_dependencies()


# ---------------------------------------------------------------------------
# DashboardServer tests
# ---------------------------------------------------------------------------


class TestDashboardServer:
    """Tests for the DashboardServer lifecycle wrapper."""

    def test_init(self) -> None:
        """Test server initializes with correct defaults."""
        pytest.importorskip("fastapi")
        pytest.importorskip("uvicorn")

        state = DashboardState(total_tasks=10)
        server = DashboardServer(state)

        assert server.host == "127.0.0.1"
        assert server.port == 8080
        assert server.state is state
        assert server.is_running is False

    def test_init_custom_host_port(self) -> None:
        """Test server accepts custom host and port."""
        pytest.importorskip("fastapi")
        pytest.importorskip("uvicorn")

        state = DashboardState()
        server = DashboardServer(state, host="0.0.0.0", port=9090)

        assert server.host == "0.0.0.0"
        assert server.port == 9090

    def test_init_raises_when_deps_missing(self) -> None:
        """Test that DashboardServer raises if deps are missing."""
        with patch("mcpbr.dashboard.HAS_FASTAPI", False), pytest.raises(ImportError):
            DashboardServer(DashboardState())

    def test_update_task_proxy(self) -> None:
        """Test that server.update_task delegates to state."""
        pytest.importorskip("fastapi")
        pytest.importorskip("uvicorn")

        state = DashboardState(total_tasks=5)
        server = DashboardServer(state)

        state.start_task("task-1")
        server.update_task("task-1", resolved=True)

        assert state.completed_tasks == 1
        assert state.resolved_tasks == 1

    def test_update_task_proxy_with_error(self) -> None:
        """Test that server.update_task passes error to state."""
        pytest.importorskip("fastapi")
        pytest.importorskip("uvicorn")

        state = DashboardState(total_tasks=5)
        server = DashboardServer(state)

        state.start_task("task-1")
        server.update_task("task-1", error="Something broke")

        assert state.failed_tasks == 1
        assert state.task_results[0].error == "Something broke"

    def test_stop_without_start_is_safe(self) -> None:
        """Test that calling stop without start does not raise."""
        pytest.importorskip("fastapi")
        pytest.importorskip("uvicorn")

        state = DashboardState()
        server = DashboardServer(state)
        server.stop()  # should not raise

    def test_is_running_false_initially(self) -> None:
        """Test that is_running is False before start."""
        pytest.importorskip("fastapi")
        pytest.importorskip("uvicorn")

        server = DashboardServer(DashboardState())
        assert server.is_running is False


# ---------------------------------------------------------------------------
# HTML template tests
# ---------------------------------------------------------------------------


class TestDashboardHTML:
    """Tests for the embedded HTML template."""

    def test_html_contains_title(self) -> None:
        """Test that the HTML includes the dashboard title."""
        assert "mcpbr Evaluation Dashboard" in DASHBOARD_HTML

    def test_html_contains_websocket_code(self) -> None:
        """Test that the HTML includes WebSocket connection logic."""
        assert "WebSocket" in DASHBOARD_HTML
        assert "/ws" in DASHBOARD_HTML

    def test_html_contains_control_buttons(self) -> None:
        """Test that the HTML includes pause/resume/cancel buttons."""
        assert "pause" in DASHBOARD_HTML.lower()
        assert "resume" in DASHBOARD_HTML.lower()
        assert "cancel" in DASHBOARD_HTML.lower()

    def test_html_contains_stats_placeholders(self) -> None:
        """Test that the HTML includes placeholder elements for stats."""
        assert 'id="completed"' in DASHBOARD_HTML
        assert 'id="rate"' in DASHBOARD_HTML
        assert 'id="eta"' in DASHBOARD_HTML
        assert 'id="elapsed"' in DASHBOARD_HTML

    def test_html_contains_api_calls(self) -> None:
        """Test that the HTML JS calls the correct API endpoints."""
        # The JS builds URLs dynamically via: fetch("/api/" + action, ...)
        assert '"/api/"' in DASHBOARD_HTML
        assert "sendControl('pause')" in DASHBOARD_HTML
        assert "sendControl('resume')" in DASHBOARD_HTML
        assert "sendControl('cancel')" in DASHBOARD_HTML

    def test_html_is_valid_structure(self) -> None:
        """Test that the HTML has proper opening and closing tags."""
        assert DASHBOARD_HTML.strip().startswith("<!DOCTYPE html>")
        assert "</html>" in DASHBOARD_HTML
        assert "<head>" in DASHBOARD_HTML
        assert "</head>" in DASHBOARD_HTML
        assert "<body>" in DASHBOARD_HTML
        assert "</body>" in DASHBOARD_HTML


# ---------------------------------------------------------------------------
# ETA edge-case tests
# ---------------------------------------------------------------------------


class TestETACalculation:
    """Focused tests for ETA calculation edge cases."""

    def test_eta_with_zero_remaining(self) -> None:
        """Test ETA is 0 when all tasks are completed."""
        state = DashboardState(total_tasks=5)
        state.start_time = time.time() - 50.0
        state.completed_tasks = 5

        eta = state.get_eta_seconds()
        assert eta is not None
        assert abs(eta) < 1.0  # ~0 remaining

    def test_eta_with_one_task_done(self) -> None:
        """Test ETA extrapolation from a single completed task."""
        state = DashboardState(total_tasks=100)
        state.start_time = time.time() - 5.0  # 5 seconds elapsed
        state.completed_tasks = 1

        eta = state.get_eta_seconds()
        assert eta is not None
        # 5s / 1 task * 99 remaining = ~495s
        assert 490.0 < eta < 500.0

    def test_eta_consistency(self) -> None:
        """Test that ETA decreases as more tasks complete."""
        state = DashboardState(total_tasks=10)
        state.start_time = time.time() - 100.0

        state.completed_tasks = 2
        eta_early = state.get_eta_seconds()

        state.completed_tasks = 8
        eta_late = state.get_eta_seconds()

        assert eta_early is not None
        assert eta_late is not None
        assert eta_late < eta_early


# ---------------------------------------------------------------------------
# Resolution rate edge-case tests
# ---------------------------------------------------------------------------


class TestResolutionRate:
    """Focused tests for resolution rate edge cases."""

    def test_all_resolved(self) -> None:
        """Test 100% resolution rate."""
        state = DashboardState(total_tasks=5)
        for i in range(5):
            state.start_task(f"task-{i}")
            state.update_task(f"task-{i}", resolved=True)

        assert state.get_resolution_rate() == 1.0

    def test_none_resolved(self) -> None:
        """Test 0% resolution rate."""
        state = DashboardState(total_tasks=5)
        for i in range(5):
            state.start_task(f"task-{i}")
            state.update_task(f"task-{i}", resolved=False)

        assert state.get_resolution_rate() == 0.0

    def test_partial_resolution(self) -> None:
        """Test partial resolution rate."""
        state = DashboardState(total_tasks=4)

        state.start_task("task-0")
        state.update_task("task-0", resolved=True)
        state.start_task("task-1")
        state.update_task("task-1", resolved=True)
        state.start_task("task-2")
        state.update_task("task-2", resolved=True)
        state.start_task("task-3")
        state.update_task("task-3", resolved=False)

        assert abs(state.get_resolution_rate() - 0.75) < 1e-9
