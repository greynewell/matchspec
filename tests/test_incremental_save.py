"""Tests for incremental saving of evaluation results."""

import json
from pathlib import Path

from mcpbr.harness import TaskResult
from mcpbr.incremental_save import (
    cleanup_incremental_file,
    convert_incremental_to_final,
    load_incremental_results,
    save_task_result_incremental,
)


class TestIncrementalSave:
    """Test incremental saving functionality."""

    def test_save_single_result(self, tmp_path: Path):
        """Test saving a single task result."""
        output_file = tmp_path / "results.jsonl"

        task_result = TaskResult(
            instance_id="test-1",
            mcp={"resolved": True, "cost": 0.50, "error": None, "patch": "test patch"},
            baseline=None,
        )

        metadata = {"timestamp": "2024-01-01T00:00:00Z", "config": {"model": "sonnet"}}

        save_task_result_incremental(task_result, output_file, metadata)

        assert output_file.exists()

        # Verify file content
        with open(output_file) as f:
            lines = f.readlines()

        assert len(lines) == 2  # Metadata + one result

        # Check metadata
        metadata_entry = json.loads(lines[0])
        assert metadata_entry["type"] == "metadata"
        assert metadata_entry["data"]["timestamp"] == "2024-01-01T00:00:00Z"

        # Check task result
        result_entry = json.loads(lines[1])
        assert result_entry["type"] == "task_result"
        assert result_entry["data"]["instance_id"] == "test-1"
        assert result_entry["data"]["mcp"]["resolved"] is True
        assert result_entry["data"]["mcp"]["cost"] == 0.50

    def test_save_multiple_results(self, tmp_path: Path):
        """Test saving multiple task results."""
        output_file = tmp_path / "results.jsonl"

        metadata = {"config": {"model": "sonnet"}}

        # Save first result with metadata
        task1 = TaskResult(
            instance_id="test-1",
            mcp={"resolved": True, "cost": 0.50, "error": None, "patch": "patch1"},
        )
        save_task_result_incremental(task1, output_file, metadata)

        # Save second result without metadata (should be None after first save)
        task2 = TaskResult(
            instance_id="test-2",
            mcp={"resolved": False, "cost": 0.25, "error": "Timeout", "patch": None},
        )
        save_task_result_incremental(task2, output_file, None)

        # Save third result
        task3 = TaskResult(
            instance_id="test-3",
            mcp={"resolved": True, "cost": 0.75, "error": None, "patch": "patch3"},
        )
        save_task_result_incremental(task3, output_file, None)

        # Verify all results saved
        with open(output_file) as f:
            lines = f.readlines()

        assert len(lines) == 4  # Metadata + 3 results

    def test_load_incremental_results(self, tmp_path: Path):
        """Test loading partial results from file."""
        output_file = tmp_path / "results.jsonl"

        metadata = {"timestamp": "2024-01-01", "config": {"model": "sonnet"}}

        # Save multiple results
        for i in range(3):
            task = TaskResult(
                instance_id=f"test-{i}",
                mcp={
                    "resolved": i % 2 == 0,
                    "cost": 0.1 * i,
                    "error": None if i % 2 == 0 else "Error",
                    "patch": f"patch-{i}" if i % 2 == 0 else None,
                },
            )
            save_task_result_incremental(task, output_file, metadata if i == 0 else None)

        # Load results
        loaded_metadata, task_results = load_incremental_results(output_file)

        assert loaded_metadata is not None
        assert loaded_metadata["timestamp"] == "2024-01-01"
        assert len(task_results) == 3
        assert task_results[0]["instance_id"] == "test-0"
        assert task_results[1]["instance_id"] == "test-1"
        assert task_results[2]["instance_id"] == "test-2"

    def test_load_nonexistent_file(self, tmp_path: Path):
        """Test loading from nonexistent file returns empty results."""
        output_file = tmp_path / "nonexistent.jsonl"

        metadata, results = load_incremental_results(output_file)

        assert metadata is None
        assert results == []

    def test_handle_malformed_lines(self, tmp_path: Path):
        """Test that malformed lines are skipped gracefully."""
        output_file = tmp_path / "results.jsonl"

        # Write a mix of valid and invalid lines
        with open(output_file, "w") as f:
            f.write('{"type": "metadata", "data": {"config": "test"}}\n')
            f.write('{"type": "task_result", "data": {"instance_id": "test-1"}}\n')
            f.write("invalid json line\n")  # Malformed
            f.write('{"type": "task_result", "data": {"instance_id": "test-2"}}\n')
            f.write("{incomplete\n")  # Malformed

        metadata, results = load_incremental_results(output_file)

        assert metadata is not None
        assert len(results) == 2  # Should skip malformed lines
        assert results[0]["instance_id"] == "test-1"
        assert results[1]["instance_id"] == "test-2"

    def test_convert_to_final_format(self, tmp_path: Path):
        """Test converting incremental saves to final JSON format."""
        incremental_file = tmp_path / "results.jsonl"
        final_file = tmp_path / "results.json"

        metadata = {"timestamp": "2024-01-01", "config": {"model": "sonnet"}}

        # Save incremental results
        for i in range(2):
            task = TaskResult(
                instance_id=f"test-{i}",
                mcp={"resolved": True, "cost": 0.5, "error": None, "patch": f"patch-{i}"},
            )
            save_task_result_incremental(task, incremental_file, metadata if i == 0 else None)

        # Convert to final format
        summary = {"total": 2, "resolved": 2, "cost": 1.0}
        convert_incremental_to_final(incremental_file, final_file, summary)

        assert final_file.exists()

        # Verify final format
        with open(final_file) as f:
            final_data = json.load(f)

        assert "metadata" in final_data
        assert "summary" in final_data
        assert "tasks" in final_data
        assert len(final_data["tasks"]) == 2
        assert final_data["summary"]["total"] == 2

    def test_cleanup_incremental_file(self, tmp_path: Path):
        """Test cleanup of incremental save file."""
        output_file = tmp_path / "results.json"
        incremental_file = tmp_path / "results.json.jsonl"  # It appends .jsonl

        # Create incremental file
        task = TaskResult(
            instance_id="test-1",
            mcp={"resolved": True, "cost": 0.5, "error": None, "patch": "patch"},
        )
        save_task_result_incremental(task, output_file, None)

        # File should exist with .jsonl extension
        assert incremental_file.exists()

        # Cleanup
        cleanup_incremental_file(output_file)

        # File should be removed
        assert not incremental_file.exists()

    def test_jsonl_extension_handling(self, tmp_path: Path):
        """Test that .jsonl extension is properly handled."""
        # Test with .json extension
        output_file = tmp_path / "results.json"

        task = TaskResult(
            instance_id="test-1",
            mcp={"resolved": True, "cost": 0.5, "error": None, "patch": "patch"},
        )
        save_task_result_incremental(task, output_file, None)

        # Should create .json.jsonl file
        jsonl_file = tmp_path / "results.json.jsonl"
        assert jsonl_file.exists()

        # Loading should work with either path
        _metadata1, results1 = load_incremental_results(output_file)
        _metadata2, results2 = load_incremental_results(jsonl_file)

        assert results1 == results2

    def test_concurrent_writes_safe(self, tmp_path: Path):
        """Test that file locking makes concurrent writes safe."""
        import asyncio

        output_file = tmp_path / "results.jsonl"

        async def write_result(idx: int):
            """Write a single result."""
            task = TaskResult(
                instance_id=f"test-{idx}",
                mcp={"resolved": True, "cost": 0.1, "error": None, "patch": f"patch-{idx}"},
            )
            # Simulate delay
            await asyncio.sleep(0.01)
            save_task_result_incremental(task, output_file, None)

        async def run_concurrent_writes():
            """Run multiple concurrent writes."""
            tasks = [write_result(i) for i in range(10)]
            await asyncio.gather(*tasks)

        # Run concurrent writes
        asyncio.run(run_concurrent_writes())

        # Verify all results were saved
        _, results = load_incremental_results(output_file)
        assert len(results) == 10

        # Verify all unique IDs
        ids = [r["instance_id"] for r in results]
        assert len(set(ids)) == 10

    def test_save_with_none_values(self, tmp_path: Path):
        """Test saving task results with None values."""
        output_file = tmp_path / "results.jsonl"

        task = TaskResult(
            instance_id="test-1",
            mcp={"resolved": False, "cost": 0.0, "error": "Failed", "patch": None},
        )

        save_task_result_incremental(task, output_file, None)

        _, results = load_incremental_results(output_file)
        assert len(results) == 1
        assert results[0]["mcp"]["patch"] is None
        assert results[0]["mcp"]["error"] == "Failed"
