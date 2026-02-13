"""Real-time web dashboard for monitoring benchmark evaluations.

This module provides a FastAPI-based local web server that displays live
evaluation progress, including tasks completed, resolution rates, ETA,
and per-task status. It also exposes REST API endpoints for pause, resume,
and cancel controls.

Requires optional dependencies: ``fastapi`` and ``uvicorn``.
Install them with::

    pip install fastapi uvicorn[standard]

Usage::

    from mcpbr.dashboard import DashboardServer, DashboardState

    state = DashboardState(total_tasks=50)
    server = DashboardServer(state, port=8080)
    server.start()

    # From evaluation loop:
    state.update_task("django__django-12345", resolved=True)

    server.stop()
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    import uvicorn

    HAS_UVICORN = True
except ImportError:
    HAS_UVICORN = False


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class TaskStatus:
    """Status information for a single evaluation task.

    Attributes:
        instance_id: Unique identifier for the task.
        status: One of ``"pending"``, ``"running"``, ``"resolved"``, ``"failed"``.
        started_at: Epoch timestamp when the task started, or ``None``.
        finished_at: Epoch timestamp when the task finished, or ``None``.
        error: Error message if the task failed, or ``None``.
    """

    instance_id: str
    status: str = "pending"
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary.

        Returns:
            Dictionary representation of the task status.
        """
        return {
            "instance_id": self.instance_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


@dataclass
class DashboardState:
    """Shared mutable state that the evaluation harness updates in real time.

    This object is passed to ``DashboardServer`` and should be mutated by the
    harness evaluation loop via :meth:`update_task` and :meth:`start_task`.

    Attributes:
        total_tasks: Total number of tasks in the evaluation.
        completed_tasks: Number of tasks that have finished (resolved + failed).
        resolved_tasks: Number of tasks that resolved successfully.
        failed_tasks: Number of tasks that failed.
        current_task_id: Instance ID of the currently running task, or ``None``.
        start_time: Epoch timestamp when the evaluation started.
        task_results: Ordered list of per-task :class:`TaskStatus` objects.
        is_paused: Whether the evaluation is currently paused.
        is_cancelled: Whether the evaluation has been cancelled.
    """

    total_tasks: int = 0
    completed_tasks: int = 0
    resolved_tasks: int = 0
    failed_tasks: int = 0
    current_task_id: str | None = None
    start_time: float = field(default_factory=time.time)
    task_results: list[TaskStatus] = field(default_factory=list)
    is_paused: bool = False
    is_cancelled: bool = False
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    # -- Mutation helpers used by the evaluation harness --------------------

    def start_task(self, instance_id: str) -> None:
        """Mark a task as currently running.

        Args:
            instance_id: The task's unique identifier.
        """
        with self._lock:
            self.current_task_id = instance_id
            task = self._find_or_create_task(instance_id)
            task.status = "running"
            task.started_at = time.time()

    def update_task(
        self,
        instance_id: str,
        *,
        resolved: bool = False,
        error: str | None = None,
    ) -> None:
        """Record the outcome of a completed task.

        Args:
            instance_id: The task's unique identifier.
            resolved: Whether the task was resolved successfully.
            error: An error message if the task failed.
        """
        with self._lock:
            task = self._find_or_create_task(instance_id)
            task.finished_at = time.time()

            if error is not None:
                task.status = "failed"
                task.error = error
                self.failed_tasks += 1
            elif resolved:
                task.status = "resolved"
                self.resolved_tasks += 1
            else:
                task.status = "failed"
                self.failed_tasks += 1

            self.completed_tasks += 1

            # Clear current task if it matches
            if self.current_task_id == instance_id:
                self.current_task_id = None

    def get_resolution_rate(self) -> float:
        """Return the current resolution rate as a fraction (0.0 -- 1.0).

        Returns:
            Resolved tasks divided by completed tasks, or 0.0 if none completed.
        """
        with self._lock:
            if self.completed_tasks == 0:
                return 0.0
            return self.resolved_tasks / self.completed_tasks

    def get_eta_seconds(self) -> float | None:
        """Estimate remaining seconds based on average task completion time.

        Returns:
            Estimated seconds remaining, or ``None`` if no tasks have completed.
        """
        with self._lock:
            if self.completed_tasks == 0:
                return None
            elapsed = time.time() - self.start_time
            avg_per_task = elapsed / self.completed_tasks
            remaining_tasks = self.total_tasks - self.completed_tasks
            return avg_per_task * remaining_tasks

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full dashboard state to a JSON-safe dictionary.

        Returns:
            Dictionary representation of the dashboard state.
        """
        with self._lock:
            eta = self._get_eta_seconds_unlocked()
            return {
                "total_tasks": self.total_tasks,
                "completed_tasks": self.completed_tasks,
                "resolved_tasks": self.resolved_tasks,
                "failed_tasks": self.failed_tasks,
                "current_task_id": self.current_task_id,
                "resolution_rate": (
                    self.resolved_tasks / self.completed_tasks if self.completed_tasks > 0 else 0.0
                ),
                "eta_seconds": eta,
                "elapsed_seconds": time.time() - self.start_time,
                "is_paused": self.is_paused,
                "is_cancelled": self.is_cancelled,
                "task_results": [t.to_dict() for t in self.task_results],
            }

    def _get_eta_seconds_unlocked(self) -> float | None:
        """Estimate remaining seconds (caller must hold _lock).

        Returns:
            Estimated seconds remaining, or ``None`` if no tasks have completed.
        """
        if self.completed_tasks == 0:
            return None
        elapsed = time.time() - self.start_time
        avg_per_task = elapsed / self.completed_tasks
        remaining_tasks = self.total_tasks - self.completed_tasks
        return avg_per_task * remaining_tasks

    # -- Internal helpers --------------------------------------------------

    def _find_or_create_task(self, instance_id: str) -> TaskStatus:
        """Retrieve an existing TaskStatus or create a new one.

        Args:
            instance_id: The task's unique identifier.

        Returns:
            The matching :class:`TaskStatus` object.
        """
        for task in self.task_results:
            if task.instance_id == instance_id:
                return task
        task = TaskStatus(instance_id=instance_id)
        self.task_results.append(task)
        return task


# ---------------------------------------------------------------------------
# HTML dashboard template
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mcpbr Dashboard</title>
<style>
  :root { --bg: #0f172a; --card: #1e293b; --text: #e2e8f0; --accent: #38bdf8;
          --green: #4ade80; --red: #f87171; --yellow: #fbbf24; --border: #334155; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg);
         color: var(--text); padding: 1.5rem; }
  h1 { font-size: 1.5rem; margin-bottom: 1rem; color: var(--accent); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 1rem; margin-bottom: 1.5rem; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 0.5rem;
          padding: 1rem; }
  .card .label { font-size: 0.75rem; text-transform: uppercase; color: #94a3b8;
                 margin-bottom: 0.25rem; }
  .card .value { font-size: 1.5rem; font-weight: 700; }
  .progress-bar { width: 100%; height: 0.5rem; background: var(--border);
                  border-radius: 0.25rem; overflow: hidden; margin: 0.5rem 0; }
  .progress-fill { height: 100%; background: var(--accent); transition: width 0.3s; }
  .controls { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
  .controls button { padding: 0.5rem 1rem; border: none; border-radius: 0.25rem;
                     cursor: pointer; font-weight: 600; font-size: 0.875rem; }
  .btn-pause  { background: var(--yellow); color: #000; }
  .btn-resume { background: var(--green); color: #000; }
  .btn-cancel { background: var(--red); color: #fff; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }
  th { color: #94a3b8; text-transform: uppercase; font-size: 0.75rem; }
  .status-resolved { color: var(--green); }
  .status-failed   { color: var(--red); }
  .status-running  { color: var(--yellow); }
  .status-pending  { color: #64748b; }
  #connection { font-size: 0.75rem; color: #64748b; margin-bottom: 1rem; }
</style>
</head>
<body>
<h1>mcpbr Evaluation Dashboard</h1>
<div id="connection">Connecting...</div>

<div class="grid">
  <div class="card"><div class="label">Completed</div>
    <div class="value" id="completed">0 / 0</div></div>
  <div class="card"><div class="label">Resolution Rate</div>
    <div class="value" id="rate">0.0%</div></div>
  <div class="card"><div class="label">ETA</div>
    <div class="value" id="eta">--</div></div>
  <div class="card"><div class="label">Elapsed</div>
    <div class="value" id="elapsed">0s</div></div>
  <div class="card"><div class="label">Status</div>
    <div class="value" id="run-status">Running</div></div>
</div>

<div class="progress-bar"><div class="progress-fill" id="progress" style="width:0%"></div></div>

<div class="controls">
  <button class="btn-pause"  onclick="sendControl('pause')">Pause</button>
  <button class="btn-resume" onclick="sendControl('resume')">Resume</button>
  <button class="btn-cancel" onclick="sendControl('cancel')">Cancel</button>
</div>

<table>
  <thead><tr><th>Instance ID</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead>
  <tbody id="tasks"></tbody>
</table>

<script>
let ws;
function connect() {
  const loc = window.location;
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(proto + "//" + loc.host + "/ws");
  ws.onopen = () => {
    document.getElementById("connection").textContent = "Connected (live)";
  };
  ws.onclose = () => {
    document.getElementById("connection").textContent = "Disconnected - reconnecting...";
    setTimeout(connect, 2000);
  };
  ws.onmessage = (evt) => {
    const data = JSON.parse(evt.data);
    update(data);
  };
}

function update(d) {
  document.getElementById("completed").textContent = d.completed_tasks + " / " + d.total_tasks;
  document.getElementById("rate").textContent = (d.resolution_rate * 100).toFixed(1) + "%";
  document.getElementById("elapsed").textContent = fmtTime(d.elapsed_seconds);
  document.getElementById("eta").textContent = d.eta_seconds != null ? fmtTime(d.eta_seconds) : "--";
  const pct = d.total_tasks > 0 ? (d.completed_tasks / d.total_tasks * 100) : 0;
  document.getElementById("progress").style.width = pct + "%";

  let status = "Running";
  if (d.is_cancelled) status = "Cancelled";
  else if (d.is_paused) status = "Paused";
  document.getElementById("run-status").textContent = status;

  const tbody = document.getElementById("tasks");
  tbody.innerHTML = "";
  (d.task_results || []).forEach(t => {
    const tr = document.createElement("tr");
    const dur = (t.started_at && t.finished_at)
      ? fmtTime(t.finished_at - t.started_at)
      : (t.started_at ? "running..." : "-");
    const tdId = document.createElement("td");
    tdId.textContent = t.instance_id;
    const tdStatus = document.createElement("td");
    tdStatus.textContent = t.status;
    tdStatus.className = "status-" + t.status;
    const tdDur = document.createElement("td");
    tdDur.textContent = dur;
    const tdErr = document.createElement("td");
    tdErr.textContent = t.error || "";
    tr.appendChild(tdId);
    tr.appendChild(tdStatus);
    tr.appendChild(tdDur);
    tr.appendChild(tdErr);
    tbody.appendChild(tr);
  });
}

function fmtTime(s) {
  if (s == null) return "--";
  s = Math.round(s);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return m > 0 ? m + "m " + sec + "s" : sec + "s";
}

function sendControl(action) {
  fetch("/api/" + action, { method: "POST" })
    .then(r => r.json())
    .then(d => { if (d.error) alert(d.error); });
}

connect();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI application factory
# ---------------------------------------------------------------------------


def _check_dependencies() -> None:
    """Raise ``ImportError`` if required optional dependencies are missing."""
    missing = []
    if not HAS_FASTAPI:
        missing.append("fastapi")
    if not HAS_UVICORN:
        missing.append("uvicorn")
    if missing:
        raise ImportError(
            f"Dashboard requires optional dependencies: {', '.join(missing)}. "
            f"Install them with:  pip install {' '.join(missing)}"
        )


def create_app(state: DashboardState) -> FastAPI:
    """Build and return a configured FastAPI application.

    Args:
        state: Shared dashboard state that will be read / mutated by endpoints.

    Returns:
        A :class:`FastAPI` instance with all routes registered.

    Raises:
        ImportError: If ``fastapi`` is not installed.
    """
    _check_dependencies()

    app = FastAPI(title="mcpbr Dashboard", docs_url=None, redoc_url=None)
    connected_websockets: list[WebSocket] = []

    # -- HTML page ---------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        """Serve the single-page dashboard HTML."""
        return HTMLResponse(content=DASHBOARD_HTML)

    # -- REST API ----------------------------------------------------------

    @app.get("/api/status", response_class=JSONResponse)
    async def api_status() -> JSONResponse:
        """Return current evaluation state as JSON."""
        return JSONResponse(content=state.to_dict())

    @app.post("/api/pause", response_class=JSONResponse)
    async def api_pause() -> JSONResponse:
        """Pause the evaluation loop."""
        if state.is_cancelled:
            return JSONResponse(
                content={"error": "Evaluation is already cancelled."},
                status_code=409,
            )
        state.is_paused = True
        await _broadcast(state.to_dict(), connected_websockets)
        return JSONResponse(content={"status": "paused"})

    @app.post("/api/resume", response_class=JSONResponse)
    async def api_resume() -> JSONResponse:
        """Resume a paused evaluation."""
        if state.is_cancelled:
            return JSONResponse(
                content={"error": "Evaluation is already cancelled."},
                status_code=409,
            )
        state.is_paused = False
        await _broadcast(state.to_dict(), connected_websockets)
        return JSONResponse(content={"status": "resumed"})

    @app.post("/api/cancel", response_class=JSONResponse)
    async def api_cancel() -> JSONResponse:
        """Cancel the evaluation."""
        state.is_cancelled = True
        state.is_paused = False
        await _broadcast(state.to_dict(), connected_websockets)
        return JSONResponse(content={"status": "cancelled"})

    # -- WebSocket ---------------------------------------------------------

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """Handle a WebSocket connection for live state updates."""
        await websocket.accept()
        connected_websockets.append(websocket)
        try:
            # Send initial state immediately
            await websocket.send_text(json.dumps(state.to_dict()))
            # Keep connection alive and push updates periodically
            while True:
                await asyncio.sleep(1)
                await websocket.send_text(json.dumps(state.to_dict()))
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.debug("WebSocket connection closed unexpectedly.")
        finally:
            if websocket in connected_websockets:
                connected_websockets.remove(websocket)

    # Expose internals for testing
    app.state.connected_websockets = connected_websockets  # type: ignore[attr-defined]
    app.state.dashboard_state = state  # type: ignore[attr-defined]

    return app


async def _broadcast(data: dict[str, Any], websockets: list[Any]) -> None:
    """Send *data* to every connected WebSocket, removing dead connections.

    Args:
        data: JSON-serializable dictionary to send.
        websockets: Mutable list of active WebSocket connections.
    """
    payload = json.dumps(data)
    dead: list[Any] = []
    for ws in websockets:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        websockets.remove(ws)


# ---------------------------------------------------------------------------
# Server wrapper
# ---------------------------------------------------------------------------


class DashboardServer:
    """Manages the lifecycle of the dashboard web server.

    The server runs in a background daemon thread so that it does not block
    the evaluation loop.

    Args:
        state: Shared :class:`DashboardState` updated by the harness.
        host: Bind address. Defaults to ``"127.0.0.1"``.
        port: TCP port. Defaults to ``8080``.

    Raises:
        ImportError: If ``fastapi`` or ``uvicorn`` are not installed.

    Example::

        state = DashboardState(total_tasks=50)
        server = DashboardServer(state)
        server.start()  # non-blocking
        # ... run evaluation ...
        server.stop()
    """

    def __init__(
        self,
        state: DashboardState,
        host: str = "127.0.0.1",
        port: int = 8080,
    ) -> None:
        _check_dependencies()
        self.state = state
        self.host = host
        self.port = port
        self.app = create_app(state)
        self._server: uvicorn.Server | None = None  # type: ignore[name-defined]
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the dashboard server in a background thread.

        The thread is a daemon so it will not prevent process exit.
        """
        config = uvicorn.Config(  # type: ignore[name-defined]
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
            loop="asyncio",
        )
        self._server = uvicorn.Server(config)  # type: ignore[name-defined]
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        logger.info("Dashboard started at http://%s:%s", self.host, self.port)

    def stop(self) -> None:
        """Signal the server to shut down and wait for the thread to finish."""
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._server = None
        logger.info("Dashboard stopped.")

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the background server thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def update_task(
        self,
        instance_id: str,
        *,
        resolved: bool = False,
        error: str | None = None,
    ) -> None:
        """Convenience proxy to :meth:`DashboardState.update_task`.

        Args:
            instance_id: The task's unique identifier.
            resolved: Whether the task resolved successfully.
            error: An error message if the task failed.
        """
        self.state.update_task(instance_id, resolved=resolved, error=error)
