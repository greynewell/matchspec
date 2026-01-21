"""Incremental saving of evaluation results to prevent data loss on crash."""

import fcntl
import json
from pathlib import Path
from typing import Any


def save_task_result_incremental(
    task_result: Any,  # TaskResult from harness module
    output_path: Path,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save a single task result incrementally to a JSON Lines file.

    Uses file locking to ensure safe concurrent writes. Each task result is
    written as a separate JSON object on its own line, allowing for easy
    recovery of partial results if the run crashes.

    Args:
        task_result: Task result to save (TaskResult dataclass).
        output_path: Path to the incremental results file (will be created if needed).
        metadata: Optional metadata to include on first write.
    """
    # Convert to .jsonl extension for clarity
    if output_path.suffix != ".jsonl":
        output_path = output_path.with_suffix(output_path.suffix + ".jsonl")

    # Prepare task data - TaskResult has mcp and baseline dicts
    task_data = {
        "instance_id": task_result.instance_id,
        "mcp": task_result.mcp,
        "baseline": task_result.baseline,
    }

    # On first write, include metadata
    is_new_file = not output_path.exists()

    # Open file in append mode with exclusive lock
    with open(output_path, "a") as f:
        # Acquire exclusive lock (blocks until available)
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

        try:
            # Write metadata header if this is a new file
            if is_new_file and metadata:
                header = {"type": "metadata", "data": metadata}
                f.write(json.dumps(header) + "\n")

            # Write task result
            result_entry = {"type": "task_result", "data": task_data}
            f.write(json.dumps(result_entry) + "\n")
            f.flush()  # Ensure it's written to disk immediately
        finally:
            # Release lock
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def load_incremental_results(output_path: Path) -> tuple[dict[str, Any] | None, list[dict]]:
    """Load partial results from an incremental save file.

    Args:
        output_path: Path to the incremental results file.

    Returns:
        Tuple of (metadata, list of task results).
        Returns (None, []) if file doesn't exist or is empty.
    """
    # Handle .jsonl extension
    if (
        output_path.suffix != ".jsonl"
        and (output_path.parent / (output_path.name + ".jsonl")).exists()
    ):
        output_path = output_path.parent / (output_path.name + ".jsonl")

    if not output_path.exists():
        return None, []

    metadata = None
    task_results = []

    with open(output_path) as f:
        # Acquire shared lock for reading
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)

        try:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    if entry.get("type") == "metadata":
                        metadata = entry.get("data")
                    elif entry.get("type") == "task_result":
                        task_results.append(entry.get("data"))
                except json.JSONDecodeError:
                    # Skip malformed lines (partial writes during crash)
                    continue
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return metadata, task_results


def convert_incremental_to_final(
    incremental_path: Path,
    final_path: Path,
    summary: dict[str, Any],
) -> None:
    """Convert incremental save file to final JSON results format.

    Args:
        incremental_path: Path to the incremental .jsonl file.
        final_path: Path to write the final JSON results.
        summary: Summary statistics to include in final results.
    """
    metadata, task_results = load_incremental_results(incremental_path)

    if metadata is None:
        metadata = {}

    final_results = {
        "metadata": metadata,
        "summary": summary,
        "tasks": task_results,
    }

    with open(final_path, "w") as f:
        json.dump(final_results, f, indent=2)


def cleanup_incremental_file(output_path: Path) -> None:
    """Remove incremental save file after successful completion.

    Args:
        output_path: Path to the incremental results file.
    """
    # Handle .jsonl extension
    if output_path.suffix != ".jsonl":
        jsonl_path = output_path.with_suffix(output_path.suffix + ".jsonl")
    else:
        jsonl_path = output_path

    if jsonl_path.exists():
        jsonl_path.unlink()
