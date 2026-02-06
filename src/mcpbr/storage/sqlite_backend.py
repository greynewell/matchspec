"""SQLite storage backend for benchmark results.

Provides persistent local storage using SQLite. This is the default storage
backend, requiring no external dependencies or server setup.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import StorageBackend

logger = logging.getLogger(__name__)

# Schema version for migration support
SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    benchmark TEXT NOT NULL,
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    config_json TEXT NOT NULL,
    results_json TEXT NOT NULL,
    metadata_json TEXT,
    pass_rate REAL,
    total_tasks INTEGER DEFAULT 0,
    resolved_tasks INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown',
    result_json TEXT NOT NULL,
    duration_seconds REAL,
    cost_usd REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_benchmark ON runs(benchmark);
CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
CREATE INDEX IF NOT EXISTS idx_task_results_run_id ON task_results(run_id);
CREATE INDEX IF NOT EXISTS idx_task_results_status ON task_results(status);
"""


class SQLiteBackend(StorageBackend):
    """SQLite storage backend.

    Stores evaluation runs and task results in a local SQLite database.
    Default location: ~/.mcpbr/results.db
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize SQLite backend.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.mcpbr/results.db.
        """
        if db_path is None:
            db_path = Path.home() / ".mcpbr" / "results.db"
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create the database connection."""
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._conn

    async def initialize(self) -> None:
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(CREATE_TABLES_SQL)

        # Track schema version
        cursor = self._conn.execute("SELECT version FROM schema_version ORDER BY version DESC")
        row = cursor.fetchone()
        if row is None:
            self._conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))

        self._conn.commit()
        logger.info(f"SQLite backend initialized at {self.db_path}")

    async def store_run(
        self,
        run_id: str,
        config: dict[str, Any],
        results: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store an evaluation run."""
        conn = self._get_conn()

        benchmark = config.get("benchmark", "unknown")
        model = config.get("model", "unknown")
        provider = config.get("provider", "unknown")

        summary = results.get("summary", {})
        pass_rate = summary.get("pass_rate")
        total_tasks = summary.get("total_tasks", 0)
        resolved_tasks = summary.get("resolved_tasks", 0)

        now = datetime.now(tz=None).isoformat()

        conn.execute(
            """INSERT OR REPLACE INTO runs
            (run_id, benchmark, model, provider, config_json, results_json,
             metadata_json, pass_rate, total_tasks, resolved_tasks, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                benchmark,
                model,
                provider,
                json.dumps(config),
                json.dumps(results),
                json.dumps(metadata) if metadata else None,
                pass_rate,
                total_tasks,
                resolved_tasks,
                now,
                now,
            ),
        )

        # Store individual task results
        tasks = results.get("tasks", [])
        for task in tasks:
            task_id = task.get("instance_id", task.get("task_id", "unknown"))
            status = task.get("status", "unknown")
            duration = task.get("duration_seconds")
            cost = task.get("cost_usd")

            conn.execute(
                """INSERT OR REPLACE INTO task_results
                (run_id, task_id, status, result_json, duration_seconds, cost_usd)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, task_id, status, json.dumps(task), duration, cost),
            )

        conn.commit()
        logger.info(f"Stored run {run_id}: {total_tasks} tasks, pass_rate={pass_rate}")
        return run_id

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Retrieve a specific run."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None

        return self._row_to_run(row)

    async def list_runs(
        self,
        benchmark: str | None = None,
        model: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List evaluation runs with optional filtering."""
        conn = self._get_conn()

        query = "SELECT * FROM runs WHERE 1=1"
        params: list[Any] = []

        if benchmark:
            query += " AND benchmark = ?"
            params.append(benchmark)
        if model:
            query += " AND model = ?"
            params.append(model)
        if since:
            query += " AND created_at >= ?"
            params.append(since.isoformat())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [self._row_to_run_summary(row) for row in cursor.fetchall()]

    async def store_task_result(
        self,
        run_id: str,
        task_id: str,
        result: dict[str, Any],
    ) -> None:
        """Store a single task result."""
        conn = self._get_conn()

        status = result.get("status", "unknown")
        duration = result.get("duration_seconds")
        cost = result.get("cost_usd")

        conn.execute(
            """INSERT OR REPLACE INTO task_results
            (run_id, task_id, status, result_json, duration_seconds, cost_usd)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, task_id, status, json.dumps(result), duration, cost),
        )
        conn.commit()

    async def get_task_results(
        self,
        run_id: str,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get task results for a run."""
        conn = self._get_conn()

        if status:
            cursor = conn.execute(
                "SELECT * FROM task_results WHERE run_id = ? AND status = ?",
                (run_id, status),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM task_results WHERE run_id = ?",
                (run_id,),
            )

        results = []
        for row in cursor.fetchall():
            result = json.loads(row["result_json"])
            result["_db_id"] = row["id"]
            results.append(result)
        return results

    async def delete_run(self, run_id: str) -> bool:
        """Delete a run and its task results."""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted run {run_id}")
        return deleted

    async def get_stats(self, benchmark: str | None = None) -> dict[str, Any]:
        """Get aggregate statistics."""
        conn = self._get_conn()

        if benchmark:
            cursor = conn.execute(
                """SELECT
                    COUNT(*) as total_runs,
                    AVG(pass_rate) as avg_pass_rate,
                    MAX(pass_rate) as max_pass_rate,
                    MIN(pass_rate) as min_pass_rate,
                    SUM(total_tasks) as total_tasks_evaluated,
                    SUM(resolved_tasks) as total_tasks_resolved,
                    MIN(created_at) as first_run,
                    MAX(created_at) as last_run
                FROM runs WHERE benchmark = ?""",
                (benchmark,),
            )
        else:
            cursor = conn.execute(
                """SELECT
                    COUNT(*) as total_runs,
                    AVG(pass_rate) as avg_pass_rate,
                    MAX(pass_rate) as max_pass_rate,
                    MIN(pass_rate) as min_pass_rate,
                    SUM(total_tasks) as total_tasks_evaluated,
                    SUM(resolved_tasks) as total_tasks_resolved,
                    MIN(created_at) as first_run,
                    MAX(created_at) as last_run
                FROM runs"""
            )

        row = cursor.fetchone()
        if row is None:
            return {"total_runs": 0}

        return {
            "total_runs": row["total_runs"],
            "avg_pass_rate": row["avg_pass_rate"],
            "max_pass_rate": row["max_pass_rate"],
            "min_pass_rate": row["min_pass_rate"],
            "total_tasks_evaluated": row["total_tasks_evaluated"],
            "total_tasks_resolved": row["total_tasks_resolved"],
            "first_run": row["first_run"],
            "last_run": row["last_run"],
        }

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("SQLite backend closed")

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a run dictionary."""
        return {
            "run_id": row["run_id"],
            "benchmark": row["benchmark"],
            "model": row["model"],
            "provider": row["provider"],
            "config": json.loads(row["config_json"]),
            "results": json.loads(row["results_json"]),
            "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else None,
            "pass_rate": row["pass_rate"],
            "total_tasks": row["total_tasks"],
            "resolved_tasks": row["resolved_tasks"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _row_to_run_summary(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a run summary (without full results)."""
        return {
            "run_id": row["run_id"],
            "benchmark": row["benchmark"],
            "model": row["model"],
            "provider": row["provider"],
            "pass_rate": row["pass_rate"],
            "total_tasks": row["total_tasks"],
            "resolved_tasks": row["resolved_tasks"],
            "created_at": row["created_at"],
        }
