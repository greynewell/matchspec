"""Weights & Biases integration for evaluation logging.

Provides lazy import of wandb to avoid hard dependency. Falls back gracefully
when wandb is not installed.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _get_wandb() -> Any | None:
    """Lazily import wandb.

    Returns:
        The wandb module, or None if not installed.
    """
    try:
        import wandb

        return wandb
    except ImportError:
        return None


def log_evaluation(
    results: dict[str, Any],
    project: str = "mcpbr",
    entity: str | None = None,
    tags: list[str] | None = None,
) -> None:
    """Log evaluation results to Weights & Biases.

    Args:
        results: Evaluation results dictionary with metadata, summary, and tasks.
        project: W&B project name.
        entity: W&B entity (team or user).
        tags: Optional tags for the run.
    """
    wandb = _get_wandb()
    if wandb is None:
        logger.warning("wandb is not installed. Install with: pip install wandb")
        return

    config = results.get("metadata", {}).get("config", {})
    summary = results.get("summary", {}).get("mcp", {})
    tasks = results.get("tasks", [])

    # Initialize W&B run
    run_config = {
        "benchmark": config.get("benchmark", "unknown"),
        "model": config.get("model", "unknown"),
        "provider": config.get("provider", "unknown"),
        "sample_size": config.get("sample_size"),
        "timeout_seconds": config.get("timeout_seconds"),
    }

    wandb.init(
        project=project,
        entity=entity,
        config=run_config,
        tags=tags or [config.get("benchmark", ""), config.get("model", "")],
    )

    try:
        # Log summary metrics
        wandb.log(
            {
                "resolution_rate": summary.get("rate", 0),
                "total_tasks": summary.get("total", 0),
                "resolved_tasks": summary.get("resolved", 0),
                "total_cost": summary.get("total_cost", 0),
                "cost_per_task": summary.get("cost_per_task", 0),
            }
        )

        # Log per-task results as a W&B Table
        if tasks:
            columns = ["instance_id", "resolved", "cost", "error"]
            table_data = []
            for task in tasks:
                mcp = task.get("mcp", {}) or {}
                table_data.append(
                    [
                        task.get("instance_id", ""),
                        mcp.get("resolved", False),
                        mcp.get("cost", 0),
                        mcp.get("error", ""),
                    ]
                )

            table = wandb.Table(columns=columns, data=table_data)
            wandb.log({"task_results": table})
    finally:
        wandb.finish()
