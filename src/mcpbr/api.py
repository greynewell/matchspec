"""REST API server for querying benchmark results.

Provides HTTP endpoints for listing, retrieving, and deleting evaluation runs,
as well as aggregate statistics. Uses Python's built-in ``http.server`` module
to avoid additional dependencies.

Usage::

    from mcpbr.api import start_api_server

    start_api_server(host="127.0.0.1", port=8000, db_path="~/.mcpbr/results.db")

Endpoints::

    GET    /api/v1/health            Health check
    GET    /api/v1/runs              List runs (?benchmark=X&model=Y&limit=N)
    GET    /api/v1/runs/{run_id}     Get a specific run
    GET    /api/v1/runs/{run_id}/tasks  Task results (?status=X)
    DELETE /api/v1/runs/{run_id}     Delete a run
    GET    /api/v1/stats             Aggregate statistics (?benchmark=X)
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from mcpbr.storage.sqlite_backend import SQLiteBackend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Route patterns
# ---------------------------------------------------------------------------

# Matches /api/v1/runs/{run_id}/tasks
_RUNS_TASKS_RE = re.compile(r"^/api/v1/runs/(?P<run_id>[^/]+)/tasks$")
# Matches /api/v1/runs/{run_id}
_RUN_DETAIL_RE = re.compile(r"^/api/v1/runs/(?P<run_id>[^/]+)$")


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


# Maximum allowed value for the ?limit= query parameter.
MAX_QUERY_LIMIT = 1000


class BenchmarkAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the benchmark results API.

    Attributes:
        storage: The :class:`SQLiteBackend` instance shared across requests.
            Injected via :func:`_make_handler_class`.
        api_token: Optional bearer token for authentication. ``None`` disables auth.
    """

    storage: SQLiteBackend
    api_token: str | None = None

    # Silence per-request log lines from BaseHTTPRequestHandler.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.debug(format, *args)

    # ------------------------------------------------------------------
    # Auth & security helpers
    # ------------------------------------------------------------------

    def _check_auth(self) -> bool:
        """Return True if the request is authenticated (or auth is disabled)."""
        if not self.api_token:
            return True
        auth_header = self.headers.get("Authorization", "")
        expected = f"Bearer {self.api_token}"
        return hmac.compare_digest(auth_header, expected)

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Serialise *data* as JSON and write an HTTP response."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    # ------------------------------------------------------------------
    # GET dispatcher
    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        """Dispatch GET requests to the appropriate handler."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        try:
            # Health endpoint is always accessible (no auth required)
            if path == "/api/v1/health":
                self._handle_health()
                return

            # All other endpoints require auth (when configured)
            if not self._check_auth():
                self._send_error_json(401, "Authentication required")
                return

            if path == "/api/v1/runs":
                self._handle_list_runs(query)
            elif path == "/api/v1/stats":
                self._handle_stats(query)
            else:
                # Try parameterised routes
                match_tasks = _RUNS_TASKS_RE.match(path)
                if match_tasks:
                    run_id = match_tasks.group("run_id")
                    self._handle_run_tasks(run_id, query)
                    return

                match_detail = _RUN_DETAIL_RE.match(path)
                if match_detail:
                    run_id = match_detail.group("run_id")
                    self._handle_get_run(run_id)
                    return

                self._send_error_json(404, "Not found")
        except Exception:
            logger.exception("Unhandled error in GET %s", self.path)
            self._send_error_json(500, "Internal server error")

    # ------------------------------------------------------------------
    # DELETE dispatcher
    # ------------------------------------------------------------------

    def do_DELETE(self) -> None:  # noqa: N802
        """Dispatch DELETE requests."""
        if not self._check_auth():
            self._send_error_json(401, "Authentication required")
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            match_detail = _RUN_DETAIL_RE.match(path)
            if match_detail:
                run_id = match_detail.group("run_id")
                self._handle_delete_run(run_id)
            else:
                self._send_error_json(404, "Not found")
        except Exception:
            logger.exception("Unhandled error in DELETE %s", self.path)
            self._send_error_json(500, "Internal server error")

    # ------------------------------------------------------------------
    # Endpoint implementations
    # ------------------------------------------------------------------

    def _handle_health(self) -> None:
        self._send_json({"status": "ok"})

    def _handle_list_runs(self, query: dict[str, list[str]]) -> None:
        benchmark = _first(query, "benchmark")
        model = _first(query, "model")
        limit_str = _first(query, "limit")
        if limit_str:
            try:
                limit = int(limit_str)
            except ValueError:
                self._send_error_json(400, f"Invalid limit value: {limit_str!r}")
                return
            if limit < 1:
                self._send_error_json(400, "limit must be a positive integer")
                return
            limit = min(limit, MAX_QUERY_LIMIT)
        else:
            limit = 50

        runs = asyncio.run(self.storage.list_runs(benchmark=benchmark, model=model, limit=limit))
        self._send_json({"runs": runs, "count": len(runs)})

    def _handle_get_run(self, run_id: str) -> None:
        run = asyncio.run(self.storage.get_run(run_id))
        if run is None:
            self._send_error_json(404, f"Run '{run_id}' not found")
            return
        self._send_json(run)

    def _handle_run_tasks(self, run_id: str, query: dict[str, list[str]]) -> None:
        # First verify the run exists
        run = asyncio.run(self.storage.get_run(run_id))
        if run is None:
            self._send_error_json(404, f"Run '{run_id}' not found")
            return

        status = _first(query, "status")
        tasks = asyncio.run(self.storage.get_task_results(run_id, status=status))
        self._send_json({"run_id": run_id, "tasks": tasks, "count": len(tasks)})

    def _handle_delete_run(self, run_id: str) -> None:
        deleted = asyncio.run(self.storage.delete_run(run_id))
        if not deleted:
            self._send_error_json(404, f"Run '{run_id}' not found")
            return
        self._send_json({"deleted": True, "run_id": run_id})

    def _handle_stats(self, query: dict[str, list[str]]) -> None:
        benchmark = _first(query, "benchmark")
        stats = asyncio.run(self.storage.get_stats(benchmark=benchmark))
        self._send_json(stats)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first(query: dict[str, list[str]], key: str) -> str | None:
    """Return the first value for *key* from a parsed query string, or ``None``."""
    values = query.get(key)
    if values:
        return values[0]
    return None


def _make_handler_class(
    storage: SQLiteBackend, api_token: str | None = None
) -> type[BenchmarkAPIHandler]:
    """Create a handler class with the given storage backend bound to it.

    This avoids global state by producing a new class whose ``storage``
    class attribute points to the supplied backend instance.
    """
    return type(
        "BoundBenchmarkAPIHandler",
        (BenchmarkAPIHandler,),
        {"storage": storage, "api_token": api_token},
    )


# ---------------------------------------------------------------------------
# Server entry points
# ---------------------------------------------------------------------------


def start_api_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    db_path: str | Path | None = None,
) -> None:
    """Start the REST API server (blocking).

    Args:
        host: Bind address. Defaults to ``127.0.0.1``.
        port: Port number. Defaults to ``8000``.
        db_path: Path to the SQLite database. Defaults to ``~/.mcpbr/results.db``.
    """
    storage = SQLiteBackend(db_path)
    asyncio.run(storage.initialize())

    handler_class = _make_handler_class(storage)
    server = HTTPServer((host, port), handler_class)
    logger.info("Starting API server on %s:%d (db=%s)", host, port, storage.db_path)

    try:
        print(f"mcpbr API server listening on http://{host}:{port}")
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down API server")
    finally:
        server.server_close()
        asyncio.run(storage.close())


def create_api_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    storage: SQLiteBackend | None = None,
    db_path: str | Path | None = None,
    api_token: str | None = None,
) -> HTTPServer:
    """Create (but do not start) an :class:`HTTPServer` for testing or embedding.

    Either *storage* or *db_path* must be provided. If *storage* is given it
    must already be initialised.

    Args:
        host: Bind address.
        port: Port number.
        storage: Pre-initialised storage backend.
        db_path: Path to SQLite database (ignored when *storage* is given).
        api_token: Optional bearer token for authentication. ``None`` disables auth.

    Returns:
        An :class:`HTTPServer` ready for ``serve_forever()`` or single-request
        handling via ``handle_request()``.
    """
    if host in ("0.0.0.0", "::"):
        logger.warning(
            "API server binding to %s — this exposes the API to all network interfaces. "
            "Consider using 127.0.0.1 for local-only access, or set an api_token.",
            host,
        )

    if storage is None:
        storage = SQLiteBackend(db_path)
        asyncio.run(storage.initialize())

    handler_class = _make_handler_class(storage, api_token=api_token)
    return HTTPServer((host, port), handler_class)


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def cli_serve(host: str, port: int, db_path: str | None) -> None:
    """Entry point for the ``mcpbr serve`` CLI command.

    Args:
        host: Bind address.
        port: Port number.
        db_path: Path to the SQLite database, or ``None`` for the default.
    """
    resolved_path = Path(db_path) if db_path else None
    start_api_server(host=host, port=port, db_path=resolved_path)
