"""Tests for XML export functionality."""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.reporting import save_xml_results


@pytest.fixture
def sample_results() -> EvaluationResults:
    """Create sample evaluation results for testing."""
    return EvaluationResults(
        metadata={
            "timestamp": "2026-01-20T12:00:00Z",
            "config": {
                "model": "claude-sonnet-4-5-20250929",
                "provider": "anthropic",
                "agent_harness": "claude-code",
                "benchmark": "swe-bench-lite",
                "dataset": "SWE-bench/SWE-bench_Lite",
                "sample_size": 2,
                "timeout_seconds": 300,
                "max_iterations": 10,
            },
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            },
        },
        summary={
            "mcp": {"resolved": 1, "total": 2, "rate": 0.5},
            "baseline": {"resolved": 0, "total": 2, "rate": 0.0},
            "improvement": "+100.0%",
        },
        tasks=[
            TaskResult(
                instance_id="test-task-1",
                mcp={
                    "patch_generated": True,
                    "tokens": {"input": 100, "output": 500},
                    "iterations": 5,
                    "tool_calls": 10,
                    "tool_usage": {"Read": 3, "Write": 2, "Bash": 5},
                    "resolved": True,
                    "patch_applied": True,
                },
                baseline={
                    "patch_generated": True,
                    "tokens": {"input": 50, "output": 300},
                    "iterations": 3,
                    "tool_calls": 5,
                    "tool_usage": {"Read": 2, "Write": 1, "Bash": 2},
                    "resolved": False,
                    "patch_applied": True,
                },
            ),
            TaskResult(
                instance_id="test-task-2",
                mcp={
                    "patch_generated": False,
                    "tokens": {"input": 80, "output": 400},
                    "iterations": 4,
                    "tool_calls": 8,
                    "tool_usage": {"Read": 4, "Bash": 4},
                    "resolved": False,
                    "patch_applied": False,
                },
                baseline={
                    "patch_generated": False,
                    "tokens": {"input": 40, "output": 200},
                    "iterations": 2,
                    "tool_calls": 3,
                    "tool_usage": {"Read": 1, "Bash": 2},
                    "resolved": False,
                    "patch_applied": False,
                },
            ),
        ],
    )


class TestSaveXmlResults:
    """Tests for save_xml_results function."""

    def test_saves_valid_xml(self, sample_results: EvaluationResults) -> None:
        """Test that XML output is valid and well-formed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(sample_results, output_path)

            assert output_path.exists()

            # Parse XML to ensure it's well-formed
            tree = ET.parse(output_path)
            root = tree.getroot()

            assert root.tag == "evaluation_results"
            assert root.find("metadata") is not None
            assert root.find("summary") is not None
            assert root.find("tasks") is not None

    def test_xml_contains_metadata(self, sample_results: EvaluationResults) -> None:
        """Test that XML contains metadata section with expected data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(sample_results, output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()
            metadata = root.find("metadata")

            assert metadata is not None
            assert metadata.find("timestamp") is not None
            assert metadata.find("timestamp").text == "2026-01-20T12:00:00Z"

            config = metadata.find("config")
            assert config is not None
            assert config.find("model") is not None
            assert config.find("model").text == "claude-sonnet-4-5-20250929"
            assert config.find("provider").text == "anthropic"
            assert config.find("benchmark").text == "swe-bench"

    def test_xml_contains_summary(self, sample_results: EvaluationResults) -> None:
        """Test that XML contains summary section with expected data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(sample_results, output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()
            summary = root.find("summary")

            assert summary is not None

            mcp = summary.find("mcp")
            assert mcp is not None
            assert mcp.find("resolved").text == "1"
            assert mcp.find("total").text == "2"
            assert mcp.find("rate").text == "0.5"

            baseline = summary.find("baseline")
            assert baseline is not None
            assert baseline.find("resolved").text == "0"
            assert baseline.find("total").text == "2"
            assert baseline.find("rate").text == "0.0"

            improvement = summary.find("improvement")
            assert improvement is not None
            assert improvement.text == "+100.0%"

    def test_xml_contains_tasks(self, sample_results: EvaluationResults) -> None:
        """Test that XML contains tasks section with all task results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(sample_results, output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()
            tasks = root.find("tasks")

            assert tasks is not None
            task_elements = tasks.findall("task")
            assert len(task_elements) == 2

            # Check first task
            task1 = task_elements[0]
            assert task1.get("instance_id") == "test-task-1"
            assert task1.find("mcp") is not None
            assert task1.find("baseline") is not None

            mcp1 = task1.find("mcp")
            assert mcp1.find("resolved").text == "true"
            assert mcp1.find("iterations").text == "5"
            assert mcp1.find("tool_calls").text == "10"

            # Check second task
            task2 = task_elements[1]
            assert task2.get("instance_id") == "test-task-2"
            assert task2.find("mcp") is not None
            assert task2.find("baseline") is not None

    def test_xml_handles_nested_structures(self, sample_results: EvaluationResults) -> None:
        """Test that XML properly handles nested dictionaries like tokens and tool_usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(sample_results, output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()
            tasks = root.find("tasks")
            task1 = tasks.find("task")
            mcp = task1.find("mcp")

            # Check nested tokens dictionary
            tokens = mcp.find("tokens")
            assert tokens is not None
            assert tokens.find("input").text == "100"
            assert tokens.find("output").text == "500"

            # Check nested tool_usage dictionary
            tool_usage = mcp.find("tool_usage")
            assert tool_usage is not None
            assert tool_usage.find("Read").text == "3"
            assert tool_usage.find("Write").text == "2"
            assert tool_usage.find("Bash").text == "5"

    def test_xml_handles_boolean_values(self, sample_results: EvaluationResults) -> None:
        """Test that boolean values are properly converted to lowercase strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(sample_results, output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()
            tasks = root.find("tasks")
            task1 = tasks.find("task")
            mcp = task1.find("mcp")

            # Booleans should be lowercase strings
            assert mcp.find("patch_generated").text == "true"
            assert mcp.find("resolved").text == "true"
            assert mcp.find("patch_applied").text == "true"

            task2 = tasks.findall("task")[1]
            mcp2 = task2.find("mcp")
            assert mcp2.find("patch_generated").text == "false"
            assert mcp2.find("resolved").text == "false"

    def test_creates_parent_directories(self, sample_results: EvaluationResults) -> None:
        """Test that parent directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "nested" / "results.xml"
            save_xml_results(sample_results, output_path)

            assert output_path.exists()
            assert output_path.parent.exists()

    def test_xml_is_pretty_printed(self, sample_results: EvaluationResults) -> None:
        """Test that XML output is properly indented and human-readable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(sample_results, output_path)

            content = output_path.read_text()

            # Check for XML declaration
            assert content.startswith("<?xml version=")

            # Check for proper indentation (should have multiple levels)
            lines = content.split("\n")
            # Should have lines with different indentation levels
            indent_levels = set()
            for line in lines:
                if line.strip():
                    # Count leading spaces
                    spaces = len(line) - len(line.lstrip())
                    indent_levels.add(spaces)

            # Should have at least 3 different indentation levels
            assert len(indent_levels) >= 3

    def test_xml_handles_none_values(self) -> None:
        """Test that XML properly handles None values."""
        results = EvaluationResults(
            metadata={"timestamp": "2026-01-20T12:00:00Z", "config": {}},
            summary={"mcp": {"resolved": 0, "total": 1, "rate": 0.0}},
            tasks=[
                TaskResult(
                    instance_id="test-task-1",
                    mcp={"resolved": False, "error": None},
                    baseline=None,  # Baseline not run
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(results, output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()
            tasks = root.find("tasks")
            task1 = tasks.find("task")
            mcp = task1.find("mcp")

            # None values in dictionaries should be skipped (not included)
            error = mcp.find("error")
            assert error is None

            # baseline should not exist since it was None
            assert task1.find("baseline") is None

    def test_xml_handles_special_characters(self) -> None:
        """Test that XML properly escapes special characters."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T12:00:00Z",
                "config": {"note": "Test with <special> & 'chars' \"here\""},
            },
            summary={"mcp": {"resolved": 0, "total": 1, "rate": 0.0}},
            tasks=[
                TaskResult(
                    instance_id="test-task-<1>",
                    mcp={"resolved": False, "error": "Error: <message> & details"},
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(results, output_path)

            # Parse XML - if special chars aren't escaped, this will fail
            tree = ET.parse(output_path)
            root = tree.getroot()

            # Verify the special characters are preserved correctly
            metadata = root.find("metadata")
            config = metadata.find("config")
            note = config.find("note")
            assert note.text == "Test with <special> & 'chars' \"here\""

            tasks = root.find("tasks")
            task1 = tasks.find("task")
            assert task1.get("instance_id") == "test-task-<1>"

            mcp = task1.find("mcp")
            error = mcp.find("error")
            assert error.text == "Error: <message> & details"

    def test_xml_handles_unicode(self) -> None:
        """Test that XML properly handles Unicode characters."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T12:00:00Z",
                "config": {"note": "测试 unicode 🔥"},
            },
            summary={"mcp": {"resolved": 0, "total": 1, "rate": 0.0}},
            tasks=[
                TaskResult(
                    instance_id="test-task-🔥",
                    mcp={"resolved": False, "message": "日本語"},
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(results, output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()

            metadata = root.find("metadata")
            config = metadata.find("config")
            note = config.find("note")
            assert note.text == "测试 unicode 🔥"

            tasks = root.find("tasks")
            task1 = tasks.find("task")
            assert task1.get("instance_id") == "test-task-🔥"

            mcp = task1.find("mcp")
            message = mcp.find("message")
            assert message.text == "日本語"

    def test_xml_handles_lists(self) -> None:
        """Test that XML properly handles list values."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T12:00:00Z",
                "config": {
                    "tags": ["tag1", "tag2", "tag3"],
                    "numbers": [1, 2, 3],
                },
            },
            summary={"mcp": {"resolved": 0, "total": 1, "rate": 0.0}},
            tasks=[
                TaskResult(
                    instance_id="test-task-1",
                    mcp={"resolved": False},
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(results, output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()

            metadata = root.find("metadata")
            config = metadata.find("config")

            # Check tags list
            tags = config.find("tags")
            assert tags is not None
            items = tags.findall("item")
            assert len(items) == 3
            assert items[0].text == "tag1"
            assert items[1].text == "tag2"
            assert items[2].text == "tag3"

            # Check numbers list
            numbers = config.find("numbers")
            assert numbers is not None
            items = numbers.findall("item")
            assert len(items) == 3
            assert items[0].text == "1"
            assert items[1].text == "2"
            assert items[2].text == "3"

    def test_xml_handles_numeric_values(self, sample_results: EvaluationResults) -> None:
        """Test that numeric values are properly converted to strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.xml"
            save_xml_results(sample_results, output_path)

            tree = ET.parse(output_path)
            root = tree.getroot()

            metadata = root.find("metadata")
            config = metadata.find("config")

            # Integer values
            assert config.find("sample_size").text == "2"
            assert config.find("timeout_seconds").text == "300"
            assert config.find("max_iterations").text == "10"

            # Float values in summary
            summary = root.find("summary")
            mcp = summary.find("mcp")
            assert mcp.find("rate").text == "0.5"

    def test_xml_structure_matches_json_yaml(self, sample_results: EvaluationResults) -> None:
        """Test that XML structure contains the same data as JSON/YAML exports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_path = Path(tmpdir) / "results.xml"
            save_xml_results(sample_results, xml_path)

            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Verify main sections exist
            assert root.find("metadata") is not None
            assert root.find("summary") is not None
            assert root.find("tasks") is not None

            # Verify metadata structure
            metadata = root.find("metadata")
            assert metadata.find("timestamp") is not None
            assert metadata.find("config") is not None
            assert metadata.find("mcp_server") is not None

            # Verify summary structure
            summary = root.find("summary")
            assert summary.find("mcp") is not None
            assert summary.find("baseline") is not None
            assert summary.find("improvement") is not None

            # Verify tasks structure
            tasks = root.find("tasks")
            task_elements = tasks.findall("task")
            assert len(task_elements) == len(sample_results.tasks)

            for i, task_elem in enumerate(task_elements):
                task_result = sample_results.tasks[i]
                assert task_elem.get("instance_id") == task_result.instance_id

                if task_result.mcp:
                    assert task_elem.find("mcp") is not None
                if task_result.baseline:
                    assert task_elem.find("baseline") is not None
