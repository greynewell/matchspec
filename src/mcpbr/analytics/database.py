"""SQLite-based historical results database for mcpbr evaluation results.

Provides persistent storage for evaluation runs and their task-level results,
enabling trend analysis, regression detection, and historical comparisons.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    benchmark TEXT,
    model TEXT,
    provider TEXT,
    agent_harness TEXT,
    sample_size INTEGER,
    timeout_seconds INTEGER,
    max_iterations INTEGER,
    resolution_rate REAL,
    total_cost REAL,
    total_tasks INTEGER,
    resolved_tasks INTEGER,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS task_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    instance_id TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    cost REAL DEFAULT 0.0,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    iterations INTEGER DEFAULT 0,
    tool_calls INTEGER DEFAULT 0,
    runtime_seconds REAL DEFAULT 0.0,
    error TEXT,
    result_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp);
CREATE INDEX IF NOT EXISTS idx_runs_benchmark ON runs(benchmark);
CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model);
CREATE INDEX IF NOT EXISTS idx_task_results_run_id ON task_results(run_id);
CREATE INDEX IF NOT EXISTS idx_task_results_instance_id ON task_results(instance_id);
"""


class ResultsDatabase:
    """SQLite-backed storage for mcpbr evaluation results.

    Stores evaluation runs and per-task results, supporting queries for
    trend analysis, filtering, and cleanup of old data.

    Example::

        with ResultsDatabase("my_results.db") as db:
            run_id = db.store_run(results_data)
            run = db.get_run(run_id)
            trends = db.get_trends(benchmark="swe-bench-verified")
    """

    def __init__(self, db_path: str | Path = "mcpbr_results.db") -> None:
        """Open or create the SQLite results database.

        Args:
            db_path: Path to the SQLite database file. The file and any
                parent directories are created if they do not exist.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        self._create_tables()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> ResultsDatabase:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store_run(self, results_data: dict[str, Any]) -> int:
        """Store a complete evaluation run with its task results.

        Args:
            results_data: Evaluation results dictionary. Expected keys are
                ``metadata`` (with ``timestamp``, ``config``, and optionally
                ``mcp_server``), ``summary`` (with ``mcp`` sub-dict), and
                ``tasks`` (list of per-task result dicts).

        Returns:
            The auto-generated ``run_id`` for the stored run.

        Raises:
            sqlite3.Error: On database write failures.
        """
        metadata = results_data.get("metadata", {})
        config = metadata.get("config", {})
        summary_mcp = results_data.get("summary", {}).get("mcp", {})

        timestamp = metadata.get("timestamp", datetime.now(UTC).isoformat())

        cur = self._conn.execute(
            """
            INSERT INTO runs (
                timestamp, benchmark, model, provider, agent_harness,
                sample_size, timeout_seconds, max_iterations,
                resolution_rate, total_cost, total_tasks, resolved_tasks,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                config.get("benchmark"),
                config.get("model"),
                config.get("provider"),
                config.get("agent_harness"),
                config.get("sample_size"),
                config.get("timeout_seconds"),
                config.get("max_iterations"),
                summary_mcp.get("rate"),
                summary_mcp.get("total_cost"),
                summary_mcp.get("total"),
                summary_mcp.get("resolved"),
                json.dumps(metadata),
            ),
        )

        run_id = cur.lastrowid
        assert run_id is not None

        # Insert task-level results
        tasks = results_data.get("tasks", [])
        for task in tasks:
            mcp = task.get("mcp", {})
            tokens = mcp.get("tokens", {})
            self._conn.execute(
                """
                INSERT INTO task_results (
                    run_id, instance_id, resolved, cost,
                    tokens_input, tokens_output, iterations,
                    tool_calls, runtime_seconds, error, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    task.get("instance_id", ""),
                    1 if mcp.get("resolved") else 0,
                    mcp.get("cost", 0.0),
                    tokens.get("input", 0),
                    tokens.get("output", 0),
                    mcp.get("iterations", 0),
                    mcp.get("tool_calls", 0),
                    mcp.get("runtime_seconds", 0.0),
                    mcp.get("error"),
                    json.dumps(task),
                ),
            )

        self._conn.commit()
        return run_id

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        """Retrieve a specific evaluation run by ID.

        Args:
            run_id: The run identifier returned by :meth:`store_run`.

        Returns:
            A dictionary with the run's columns, or ``None`` if not found.
        """
        cur = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_runs(
        self,
        limit: int = 50,
        benchmark: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        """List evaluation runs with optional filtering.

        Args:
            limit: Maximum number of runs to return. Runs are ordered by
                timestamp descending (most recent first).
            benchmark: Filter by benchmark name (exact match).
            model: Filter by model identifier (exact match).
            provider: Filter by provider name (exact match).

        Returns:
            List of run dictionaries, most recent first.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if benchmark is not None:
            clauses.append("benchmark = ?")
            params.append(benchmark)
        if model is not None:
            clauses.append("model = ?")
            params.append(model)
        if provider is not None:
            clauses.append("provider = ?")
            params.append(provider)

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        query = f"SELECT * FROM runs {where} ORDER BY timestamp DESC LIMIT ?"  # noqa: S608 -- WHERE clause built from hardcoded column names with parameterized values
        params.append(limit)

        cur = self._conn.execute(query, params)
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def get_task_results(self, run_id: int) -> list[dict[str, Any]]:
        """Get all task-level results for a specific run.

        Args:
            run_id: The run identifier.

        Returns:
            List of task result dictionaries for the run.
        """
        cur = self._conn.execute(
            "SELECT * FROM task_results WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def delete_run(self, run_id: int) -> bool:
        """Delete an evaluation run and all its associated task results.

        Args:
            run_id: The run identifier to delete.

        Returns:
            ``True`` if a run was deleted, ``False`` if no run existed
            with the given ID.
        """
        cur = self._conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def get_trends(
        self,
        benchmark: str | None = None,
        model: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get resolution rate, cost, and token trends over time.

        Returns a time-ordered list of aggregate metrics for each run
        matching the optional filters.

        Args:
            benchmark: Filter by benchmark name.
            model: Filter by model identifier.
            limit: Maximum number of data points to return.

        Returns:
            List of dicts with keys ``timestamp``, ``resolution_rate``,
            ``total_cost``, ``total_tokens``, ``resolved_tasks``, and
            ``total_tasks``, ordered by timestamp ascending.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if benchmark is not None:
            clauses.append("r.benchmark = ?")
            params.append(benchmark)
        if model is not None:
            clauses.append("r.model = ?")
            params.append(model)

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        base_query = (
            "SELECT r.id, r.timestamp, r.resolution_rate, r.total_cost,"
            " r.resolved_tasks, r.total_tasks,"
            " COALESCE(SUM(t.tokens_input + t.tokens_output), 0) AS total_tokens"
            " FROM runs r LEFT JOIN task_results t ON t.run_id = r.id"
        )
        query = f"{base_query} {where} GROUP BY r.id ORDER BY r.timestamp ASC LIMIT ?"
        params.append(limit)

        cur = self._conn.execute(query, params)
        results: list[dict[str, Any]] = []
        for row in cur.fetchall():
            results.append(
                {
                    "timestamp": row["timestamp"],
                    "resolution_rate": row["resolution_rate"],
                    "total_cost": row["total_cost"],
                    "total_tokens": row["total_tokens"],
                    "resolved_tasks": row["resolved_tasks"],
                    "total_tasks": row["total_tasks"],
                }
            )
        return results

    def cleanup(self, max_age_days: int = 90) -> int:
        """Delete runs older than the specified age.

        Args:
            max_age_days: Maximum age in days. Runs with a timestamp older
                than this many days from now will be deleted along with
                their task results (via ``ON DELETE CASCADE``).

        Returns:
            Number of runs deleted.
        """
        cutoff = (datetime.now(UTC) - timedelta(days=max_age_days)).isoformat()
        cur = self._conn.execute("DELETE FROM runs WHERE timestamp < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        """Close the database connection.

        After calling this method the database instance should not be used.
        """
        self._conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        """Create the schema tables and indexes if they do not already exist."""
        self._conn.executescript(_SCHEMA_SQL)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a ``sqlite3.Row`` to a plain dictionary.

        JSON-encoded columns (``metadata_json``, ``result_json``) are
        automatically decoded back into Python objects.
        """
        d: dict[str, Any] = dict(row)
        for key in ("metadata_json", "result_json"):
            if key in d and d[key] is not None:
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    d[key] = json.loads(d[key])
        return d
