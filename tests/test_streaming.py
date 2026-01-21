"""Tests for streaming results output."""

import json
from pathlib import Path

import pytest
import yaml

from mcpbr.harness import TaskResult
from mcpbr.streaming import (
    StreamingConfig,
    StreamingOutputHandler,
    create_streaming_handler,
)


@pytest.fixture
def metadata():
    """Test metadata."""
    return {
        "timestamp": "2024-01-01T00:00:00Z",
        "config": {
            "model": "claude-sonnet-4",
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "benchmark": "swe-bench",
            "dataset": "princeton-nlp/SWE-bench_Lite",
            "sample_size": 5,
        },
    }


@pytest.fixture
def sample_result():
    """Create a sample task result."""
    return TaskResult(
        instance_id="django__django-12345",
        mcp={
            "resolved": True,
            "patch_applied": True,
            "cost": 0.05,
            "tokens": {"input": 1000, "output": 500},
            "iterations": 3,
            "tool_calls": 5,
        },
        baseline={
            "resolved": False,
            "patch_applied": False,
            "cost": 0.03,
            "tokens": {"input": 800, "output": 400},
            "iterations": 2,
            "tool_calls": 0,
        },
    )


def test_streaming_config():
    """Test streaming configuration."""
    config = StreamingConfig(
        enabled=True,
        console_updates=True,
        progressive_json=Path("test.json"),
    )
    assert config.enabled is True
    assert config.console_updates is True
    assert config.progressive_json == Path("test.json")


def test_streaming_handler_initialization(metadata):
    """Test streaming handler initialization."""
    config = StreamingConfig(enabled=True)
    handler = StreamingOutputHandler(config, metadata)

    assert handler.config.enabled is True
    assert handler.metadata == metadata
    assert len(handler.results) == 0
    assert handler._mcp_resolved == 0
    assert handler._baseline_resolved == 0


def test_streaming_handler_add_result(metadata, sample_result):
    """Test adding results to streaming handler."""
    config = StreamingConfig(enabled=True, console_updates=False)
    handler = StreamingOutputHandler(config, metadata)

    handler.add_result(sample_result)

    assert len(handler.results) == 1
    assert handler._mcp_resolved == 1
    assert handler._mcp_total == 1
    assert handler._baseline_resolved == 0
    assert handler._baseline_total == 1
    assert handler._mcp_cost == 0.05
    assert handler._baseline_cost == 0.03


def test_streaming_handler_multiple_results(metadata):
    """Test adding multiple results."""
    config = StreamingConfig(enabled=True, console_updates=False)
    handler = StreamingOutputHandler(config, metadata)

    # Add resolved result
    result1 = TaskResult(
        instance_id="task-1",
        mcp={"resolved": True, "cost": 0.05},
        baseline={"resolved": False, "cost": 0.03},
    )
    handler.add_result(result1)

    # Add unresolved result
    result2 = TaskResult(
        instance_id="task-2",
        mcp={"resolved": False, "cost": 0.04},
        baseline={"resolved": True, "cost": 0.02},
    )
    handler.add_result(result2)

    assert len(handler.results) == 2
    assert handler._mcp_resolved == 1
    assert handler._mcp_total == 2
    assert handler._baseline_resolved == 1
    assert handler._baseline_total == 2
    assert handler._mcp_cost == 0.09
    assert handler._baseline_cost == 0.05


def test_streaming_handler_get_current_summary(metadata):
    """Test getting current summary statistics."""
    config = StreamingConfig(enabled=True, console_updates=False)
    handler = StreamingOutputHandler(config, metadata)

    # Add two results - one where baseline succeeds
    result1 = TaskResult(
        instance_id="task-1",
        mcp={"resolved": True, "cost": 0.05},
        baseline={"resolved": True, "cost": 0.03},
    )
    handler.add_result(result1)

    result2 = TaskResult(
        instance_id="task-2",
        mcp={"resolved": True, "cost": 0.05},
        baseline={"resolved": False, "cost": 0.03},
    )
    handler.add_result(result2)

    summary = handler._get_current_summary()

    assert summary["mcp"]["resolved"] == 2
    assert summary["mcp"]["total"] == 2
    assert summary["mcp"]["rate"] == 1.0
    assert summary["baseline"]["resolved"] == 1
    assert summary["baseline"]["total"] == 2
    assert summary["baseline"]["rate"] == 0.5
    assert summary["improvement"] == "+100.0%"


def test_streaming_handler_progressive_json(metadata, sample_result, tmp_path):
    """Test progressive JSON file writing."""
    json_path = tmp_path / "results.json"
    config = StreamingConfig(
        enabled=True,
        console_updates=False,
        progressive_json=json_path,
    )
    handler = StreamingOutputHandler(config, metadata)

    handler.start()
    handler.add_result(sample_result)
    handler.stop()

    # Check JSON file was created and contains data
    assert json_path.exists()
    with open(json_path) as f:
        data = json.load(f)

    assert "metadata" in data
    assert "summary" in data
    assert "tasks" in data
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["instance_id"] == "django__django-12345"


def test_streaming_handler_progressive_yaml(metadata, sample_result, tmp_path):
    """Test progressive YAML file writing."""
    yaml_path = tmp_path / "results.yaml"
    config = StreamingConfig(
        enabled=True,
        console_updates=False,
        progressive_yaml=yaml_path,
    )
    handler = StreamingOutputHandler(config, metadata)

    handler.start()
    handler.add_result(sample_result)
    handler.stop()

    # Check YAML file was created and contains data
    assert yaml_path.exists()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    assert "metadata" in data
    assert "summary" in data
    assert "tasks" in data
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["instance_id"] == "django__django-12345"


def test_streaming_handler_progressive_markdown(metadata, sample_result, tmp_path):
    """Test progressive Markdown file writing."""
    md_path = tmp_path / "results.md"
    config = StreamingConfig(
        enabled=True,
        console_updates=False,
        progressive_markdown=md_path,
    )
    handler = StreamingOutputHandler(config, metadata)

    handler.start()
    handler.add_result(sample_result)
    handler.stop()

    # Check Markdown file was created and contains data
    assert md_path.exists()
    content = md_path.read_text()

    assert "# Evaluation Results (Live)" in content
    assert "django__django-12345" in content
    assert "PASS" in content
    assert "FAIL" in content


def test_streaming_handler_multiple_formats(metadata, sample_result, tmp_path):
    """Test writing to multiple formats simultaneously."""
    json_path = tmp_path / "results.json"
    yaml_path = tmp_path / "results.yaml"
    md_path = tmp_path / "results.md"

    config = StreamingConfig(
        enabled=True,
        console_updates=False,
        progressive_json=json_path,
        progressive_yaml=yaml_path,
        progressive_markdown=md_path,
    )
    handler = StreamingOutputHandler(config, metadata)

    handler.start()
    handler.add_result(sample_result)
    handler.stop()

    # Check all files were created
    assert json_path.exists()
    assert yaml_path.exists()
    assert md_path.exists()


def test_streaming_handler_updates_on_each_result(metadata, tmp_path):
    """Test that files are updated after each result."""
    json_path = tmp_path / "results.json"
    config = StreamingConfig(
        enabled=True,
        console_updates=False,
        progressive_json=json_path,
    )
    handler = StreamingOutputHandler(config, metadata)

    handler.start()

    # Add first result
    result1 = TaskResult(
        instance_id="task-1",
        mcp={"resolved": True, "cost": 0.05},
    )
    handler.add_result(result1)

    # Check file after first result
    with open(json_path) as f:
        data = json.load(f)
    assert len(data["tasks"]) == 1

    # Add second result
    result2 = TaskResult(
        instance_id="task-2",
        mcp={"resolved": False, "cost": 0.03},
    )
    handler.add_result(result2)

    # Check file after second result
    with open(json_path) as f:
        data = json.load(f)
    assert len(data["tasks"]) == 2

    handler.stop()


def test_create_streaming_handler_factory(metadata):
    """Test factory function for creating streaming handler."""
    handler = create_streaming_handler(
        enabled=True,
        metadata=metadata,
        console_updates=True,
        progressive_json=Path("test.json"),
    )

    assert isinstance(handler, StreamingOutputHandler)
    assert handler.config.enabled is True
    assert handler.config.console_updates is True
    assert handler.config.progressive_json == Path("test.json")


def test_streaming_handler_disabled(metadata, sample_result):
    """Test that streaming handler respects disabled config."""
    config = StreamingConfig(enabled=False)
    handler = StreamingOutputHandler(config, metadata)

    # Start should not raise an error
    handler.start()
    handler.add_result(sample_result)
    handler.stop()

    assert len(handler.results) == 1


def test_streaming_handler_no_console_updates(metadata, sample_result):
    """Test streaming handler with console updates disabled."""
    config = StreamingConfig(enabled=True, console_updates=False)
    handler = StreamingOutputHandler(config, metadata)

    # Should not start live display
    handler.start()
    assert handler.live is None

    handler.add_result(sample_result)
    handler.stop()

    assert len(handler.results) == 1


def test_streaming_handler_get_results(metadata):
    """Test getting results from handler."""
    config = StreamingConfig(enabled=True, console_updates=False)
    handler = StreamingOutputHandler(config, metadata)

    result1 = TaskResult(instance_id="task-1")
    result2 = TaskResult(instance_id="task-2")

    handler.add_result(result1)
    handler.add_result(result2)

    results = handler.get_results()
    assert len(results) == 2
    assert results[0].instance_id == "task-1"
    assert results[1].instance_id == "task-2"


def test_streaming_handler_cost_tracking(metadata):
    """Test cost tracking in streaming handler."""
    config = StreamingConfig(enabled=True, console_updates=False)
    handler = StreamingOutputHandler(config, metadata)

    # Add results with various costs
    for i in range(5):
        result = TaskResult(
            instance_id=f"task-{i}",
            mcp={"resolved": i % 2 == 0, "cost": 0.05 + i * 0.01},
            baseline={"resolved": i % 3 == 0, "cost": 0.03 + i * 0.01},
        )
        handler.add_result(result)

    # Check totals
    assert handler._mcp_total == 5
    assert handler._baseline_total == 5
    assert handler._mcp_resolved == 3  # tasks 0, 2, 4
    assert handler._baseline_resolved == 2  # tasks 0, 3

    # Check costs
    expected_mcp_cost = sum(0.05 + i * 0.01 for i in range(5))
    expected_baseline_cost = sum(0.03 + i * 0.01 for i in range(5))
    assert abs(handler._mcp_cost - expected_mcp_cost) < 0.001
    assert abs(handler._baseline_cost - expected_baseline_cost) < 0.001


def test_streaming_handler_improvement_calculation(metadata):
    """Test improvement percentage calculation."""
    config = StreamingConfig(enabled=True, console_updates=False)
    handler = StreamingOutputHandler(config, metadata)

    # Add results where MCP is better
    for i in range(10):
        result = TaskResult(
            instance_id=f"task-{i}",
            mcp={"resolved": i < 7, "cost": 0.05},  # 70% success
            baseline={"resolved": i < 5, "cost": 0.03},  # 50% success
        )
        handler.add_result(result)

    summary = handler._get_current_summary()
    # Improvement should be (0.7 - 0.5) / 0.5 * 100 = 40%
    assert summary["improvement"] == "+40.0%"


def test_streaming_handler_no_baseline_improvement(metadata):
    """Test improvement calculation when baseline has no successes."""
    config = StreamingConfig(enabled=True, console_updates=False)
    handler = StreamingOutputHandler(config, metadata)

    result = TaskResult(
        instance_id="task-1",
        mcp={"resolved": True, "cost": 0.05},
        baseline={"resolved": False, "cost": 0.03},
    )
    handler.add_result(result)

    summary = handler._get_current_summary()
    assert summary["improvement"] == "N/A"
