"""Tests for XML export functionality."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.reporting import save_xml_results


class TestXMLExport:
    """Tests for XML export functionality."""

    @pytest.fixture
    def sample_results(self) -> EvaluationResults:
        """Create sample evaluation results for testing."""
        return EvaluationResults(
            metadata={
                "timestamp": "2024-01-20T10:30:00Z",
                "config": {
                    "model": "claude-sonnet-4-5-20250514",
                    "provider": "anthropic",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": "2",
                    "timeout_seconds": "300",
                    "max_concurrent": "4",
                    "max_iterations": "10",
                    "agent_harness": "claude-code",
                },
                "mcp_server": {
                    "name": "mcpbr",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "env": {},
                },
            },
            summary={
                "mcp": {"resolved": 1, "total": 2, "rate": 0.5},
                "baseline": {"resolved": 0, "total": 2, "rate": 0.0},
                "improvement": "+50.0%",
            },
            tasks=[
                TaskResult(
                    instance_id="test-123",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "iterations": 5,
                        "tool_calls": 10,
                        "tokens": {"input": 1000, "output": 500},
                        "tool_usage": {"Read": 3, "Write": 2},
                        "fail_to_pass": {"passed": 2, "total": 2},
                        "pass_to_pass": {"passed": 5, "total": 5},
                    },
                    baseline={
                        "resolved": False,
                        "patch_generated": False,
                        "iterations": 3,
                        "tool_calls": 5,
                        "tokens": {"input": 800, "output": 300},
                        "error": "Test failed",
                    },
                ),
                TaskResult(
                    instance_id="test-456",
                    mcp={
                        "resolved": False,
                        "patch_generated": True,
                        "iterations": 8,
                        "tool_calls": 15,
                        "tokens": {"input": 1200, "output": 600},
                    },
                    baseline={
                        "resolved": False,
                        "patch_generated": False,
                        "iterations": 2,
                        "tool_calls": 4,
                        "tokens": {"input": 600, "output": 200},
                    },
                ),
            ],
        )

    def test_save_xml_results_creates_file(
        self, tmp_path: Path, sample_results: EvaluationResults
    ) -> None:
        """Test that save_xml_results creates an XML file."""
        output_path = tmp_path / "results.xml"
        save_xml_results(sample_results, output_path)
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_xml_structure(self, tmp_path: Path, sample_results: EvaluationResults) -> None:
        """Test that XML has correct structure."""
        output_path = tmp_path / "results.xml"
        save_xml_results(sample_results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Check root element
        assert root.tag == "mcpbr-evaluation"
        assert root.get("version") == "1.0"

        # Check main sections
        metadata = root.find("metadata")
        assert metadata is not None
        summary = root.find("summary")
        assert summary is not None
        tasks = root.find("tasks")
        assert tasks is not None

    def test_xml_metadata(self, tmp_path: Path, sample_results: EvaluationResults) -> None:
        """Test that metadata is correctly written to XML."""
        output_path = tmp_path / "results.xml"
        save_xml_results(sample_results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()
        metadata = root.find("metadata")
        assert metadata is not None

        # Check timestamp
        timestamp = metadata.find("timestamp")
        assert timestamp is not None
        assert timestamp.text == "2024-01-20T10:30:00Z"

        # Check config
        config = metadata.find("config")
        assert config is not None
        model = config.find("model")
        assert model is not None
        assert model.text == "claude-sonnet-4-5-20250514"

        # Check MCP server
        mcp_server = metadata.find("mcp-server")
        assert mcp_server is not None
        command = mcp_server.find("command")
        assert command is not None
        assert command.text == "npx"

    def test_xml_summary(self, tmp_path: Path, sample_results: EvaluationResults) -> None:
        """Test that summary is correctly written to XML."""
        output_path = tmp_path / "results.xml"
        save_xml_results(sample_results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()
        summary = root.find("summary")
        assert summary is not None

        # Check MCP summary
        mcp = summary.find("mcp")
        assert mcp is not None
        resolved = mcp.find("resolved")
        assert resolved is not None
        assert resolved.text == "1"
        total = mcp.find("total")
        assert total is not None
        assert total.text == "2"
        rate = mcp.find("rate")
        assert rate is not None
        assert rate.text == "0.5000"

        # Check baseline summary
        baseline = summary.find("baseline")
        assert baseline is not None
        resolved = baseline.find("resolved")
        assert resolved is not None
        assert resolved.text == "0"

        # Check improvement
        improvement = summary.find("improvement")
        assert improvement is not None
        assert improvement.text == "+50.0%"

    def test_xml_tasks(self, tmp_path: Path, sample_results: EvaluationResults) -> None:
        """Test that tasks are correctly written to XML."""
        output_path = tmp_path / "results.xml"
        save_xml_results(sample_results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()
        tasks = root.find("tasks")
        assert tasks is not None

        # Check task elements
        task_elements = tasks.findall("task")
        assert len(task_elements) == 2

        # Check first task
        task1 = task_elements[0]
        assert task1.get("id") == "test-123"

        # Check MCP result for task 1
        mcp = task1.find("mcp")
        assert mcp is not None
        resolved = mcp.find("resolved")
        assert resolved is not None
        assert resolved.text == "true"
        iterations = mcp.find("iterations")
        assert iterations is not None
        assert iterations.text == "5"

        # Check tokens
        tokens = mcp.find("tokens")
        assert tokens is not None
        input_tokens = tokens.find("input")
        assert input_tokens is not None
        assert input_tokens.text == "1000"

        # Check tool usage
        tool_usage = mcp.find("tool-usage")
        assert tool_usage is not None
        tools = tool_usage.findall("tool")
        assert len(tools) == 2

        # Check baseline result for task 1
        baseline = task1.find("baseline")
        assert baseline is not None
        resolved = baseline.find("resolved")
        assert resolved is not None
        assert resolved.text == "false"
        error = baseline.find("error")
        assert error is not None
        assert error.text == "Test failed"

    def test_xml_test_results(self, tmp_path: Path, sample_results: EvaluationResults) -> None:
        """Test that test results (fail-to-pass, pass-to-pass) are correctly written."""
        output_path = tmp_path / "results.xml"
        save_xml_results(sample_results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()
        tasks = root.find("tasks")
        assert tasks is not None

        task1 = tasks.find("task[@id='test-123']")
        assert task1 is not None
        mcp = task1.find("mcp")
        assert mcp is not None

        # Check fail-to-pass
        fail_to_pass = mcp.find("fail-to-pass")
        assert fail_to_pass is not None
        passed = fail_to_pass.find("passed")
        assert passed is not None
        assert passed.text == "2"
        total = fail_to_pass.find("total")
        assert total is not None
        assert total.text == "2"

        # Check pass-to-pass
        pass_to_pass = mcp.find("pass-to-pass")
        assert pass_to_pass is not None
        passed = pass_to_pass.find("passed")
        assert passed is not None
        assert passed.text == "5"

    def test_xml_creates_parent_directories(
        self, tmp_path: Path, sample_results: EvaluationResults
    ) -> None:
        """Test that save_xml_results creates parent directories."""
        output_path = tmp_path / "subdir" / "nested" / "results.xml"
        save_xml_results(sample_results, output_path)
        assert output_path.exists()

    def test_xml_well_formed(self, tmp_path: Path, sample_results: EvaluationResults) -> None:
        """Test that generated XML is well-formed and parseable."""
        output_path = tmp_path / "results.xml"
        save_xml_results(sample_results, output_path)

        # This should not raise an exception
        tree = ET.parse(output_path)
        root = tree.getroot()
        assert root is not None

    def test_xml_with_minimal_data(self, tmp_path: Path) -> None:
        """Test XML export with minimal data."""
        minimal_results = EvaluationResults(
            metadata={
                "timestamp": "2024-01-20T10:30:00Z",
                "config": {"model": "test-model"},
                "mcp_server": {"command": "test"},
            },
            summary={
                "mcp": {"resolved": 0, "total": 0, "rate": 0.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "0.0%",
            },
            tasks=[],
        )

        output_path = tmp_path / "minimal.xml"
        save_xml_results(minimal_results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()
        assert root.tag == "mcpbr-evaluation"

    def test_xml_escapes_special_characters(self, tmp_path: Path) -> None:
        """Test that special XML characters are properly escaped."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2024-01-20T10:30:00Z",
                "config": {"model": "test-model"},
                "mcp_server": {"command": "test"},
            },
            summary={
                "mcp": {"resolved": 0, "total": 1, "rate": 0.0},
                "baseline": {"resolved": 0, "total": 1, "rate": 0.0},
                "improvement": "0.0%",
            },
            tasks=[
                TaskResult(
                    instance_id="test-123",
                    mcp={
                        "resolved": False,
                        "error": "Error: <tag> & \"quote\" 'apostrophe'",
                        "iterations": 1,
                        "tool_calls": 1,
                        "tokens": {"input": 100, "output": 50},
                    },
                )
            ],
        )

        output_path = tmp_path / "escaped.xml"
        save_xml_results(results, output_path)

        # Parse the XML to ensure it's valid
        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find the error element
        task = root.find(".//task[@id='test-123']/mcp/error")
        assert task is not None
        # The error text should be properly unescaped when parsed
        assert "<tag>" in task.text
        assert "&" in task.text
