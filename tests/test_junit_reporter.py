"""Tests for JUnit XML report generation."""

import xml.etree.ElementTree as ET
from pathlib import Path

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.junit_reporter import save_junit_xml


class TestJUnitXMLGeneration:
    """Tests for JUnit XML report generation."""

    def test_basic_junit_xml_structure(self, tmp_path: Path) -> None:
        """Test that basic JUnit XML structure is created correctly."""
        # Create minimal evaluation results
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 2,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 1, "total": 2, "rate": 0.5},
                "baseline": {"resolved": 1, "total": 2, "rate": 0.5},
                "improvement": "+0.0%",
            },
            tasks=[
                TaskResult(
                    instance_id="test-task-1",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                    baseline={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                ),
                TaskResult(
                    instance_id="test-task-2",
                    mcp={
                        "resolved": False,
                        "patch_generated": False,
                        "error": "Timeout",
                        "tokens": {"input": 50, "output": 100},
                        "iterations": 3,
                        "tool_calls": 5,
                    },
                    baseline={
                        "resolved": False,
                        "patch_generated": False,
                        "error": "Timeout",
                        "tokens": {"input": 50, "output": 100},
                        "iterations": 3,
                        "tool_calls": 5,
                    },
                ),
            ],
        )

        # Save JUnit XML
        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        # Verify file was created
        assert output_path.exists()

        # Parse XML
        tree = ET.parse(output_path)
        root = tree.getroot()

        # Verify root element
        assert root.tag == "testsuites"
        assert root.get("name") == "mcpbr Evaluation"
        assert root.get("tests") == "4"  # 2 MCP + 2 baseline
        assert root.get("failures") == "2"  # 1 MCP failed + 1 baseline failed

    def test_testsuite_creation(self, tmp_path: Path) -> None:
        """Test that test suites are created correctly."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
                "baseline": {"resolved": 0, "total": 1, "rate": 0.0},
                "improvement": "+100.0%",
            },
            tasks=[
                TaskResult(
                    instance_id="test-task-1",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                    baseline={
                        "resolved": False,
                        "patch_generated": True,
                        "patch_applied": False,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find test suites
        testsuites = root.findall("testsuite")
        assert len(testsuites) == 2

        # Check MCP suite
        mcp_suite = testsuites[0]
        assert mcp_suite.get("name") == "MCP Agent Evaluation"
        assert mcp_suite.get("tests") == "1"
        assert mcp_suite.get("failures") == "0"

        # Check baseline suite
        baseline_suite = testsuites[1]
        assert baseline_suite.get("name") == "Baseline Agent Evaluation"
        assert baseline_suite.get("tests") == "1"
        assert baseline_suite.get("failures") == "1"

    def test_testcase_pass(self, tmp_path: Path) -> None:
        """Test that passing test cases have no failure element."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-pass",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                        "fail_to_pass": {"passed": 2, "total": 2},
                        "pass_to_pass": {"passed": 10, "total": 10},
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find test case
        testcase = root.find(".//testcase[@name='test-pass']")
        assert testcase is not None

        # Should have no failure element
        failure = testcase.find("failure")
        assert failure is None

        # Should have system-out with metadata
        system_out = testcase.find("system-out")
        assert system_out is not None
        assert "Instance ID: test-pass" in system_out.text
        assert "Input Tokens: 100" in system_out.text
        assert "Fail-to-Pass Tests: 2/2" in system_out.text

    def test_testcase_failure_no_patch(self, tmp_path: Path) -> None:
        """Test that test cases with no patch have appropriate failure element."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 0, "total": 1, "rate": 0.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-fail",
                    mcp={
                        "resolved": False,
                        "patch_generated": False,
                        "tokens": {"input": 50, "output": 100},
                        "iterations": 3,
                        "tool_calls": 5,
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find test case
        testcase = root.find(".//testcase[@name='test-fail']")
        assert testcase is not None

        # Should have failure element
        failure = testcase.find("failure")
        assert failure is not None
        assert failure.get("type") == "UnresolvedTask"
        assert failure.get("message") == "No patch generated"
        assert "did not generate a patch" in failure.text

    def test_testcase_failure_with_error(self, tmp_path: Path) -> None:
        """Test that test cases with errors have appropriate failure element."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 0, "total": 1, "rate": 0.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-error",
                    mcp={
                        "resolved": False,
                        "patch_generated": False,
                        "error": "Timeout exceeded",
                        "tokens": {"input": 50, "output": 100},
                        "iterations": 3,
                        "tool_calls": 5,
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find test case
        testcase = root.find(".//testcase[@name='test-error']")
        assert testcase is not None

        # Should have failure element with error message
        failure = testcase.find("failure")
        assert failure is not None
        assert failure.get("message") == "Task failed: Timeout exceeded"
        assert "Error during execution: Timeout exceeded" in failure.text

    def test_testcase_failure_patch_not_applied(self, tmp_path: Path) -> None:
        """Test that test cases where patch couldn't be applied have failure element."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 0, "total": 1, "rate": 0.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-patch-fail",
                    mcp={
                        "resolved": False,
                        "patch_generated": True,
                        "patch_applied": False,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find test case
        testcase = root.find(".//testcase[@name='test-patch-fail']")
        assert testcase is not None

        # Should have failure element
        failure = testcase.find("failure")
        assert failure is not None
        assert failure.get("message") == "Patch could not be applied"
        assert "could not be applied" in failure.text

    def test_testcase_failure_tests_failed(self, tmp_path: Path) -> None:
        """Test that test cases with failing tests have detailed failure info."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 0, "total": 1, "rate": 0.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-tests-fail",
                    mcp={
                        "resolved": False,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                        "fail_to_pass": {"passed": 1, "total": 2},
                        "pass_to_pass": {"passed": 8, "total": 10},
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find test case
        testcase = root.find(".//testcase[@name='test-tests-fail']")
        assert testcase is not None

        # Should have failure element with test details
        failure = testcase.find("failure")
        assert failure is not None
        assert failure.get("message") == "Tests failed after applying patch"
        assert "Fail-to-Pass: 1/2 tests passed" in failure.text
        assert "Pass-to-Pass: 8/10 tests passed" in failure.text

    def test_properties_in_testsuite(self, tmp_path: Path) -> None:
        """Test that test suite includes properties with metadata."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-task",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find MCP test suite
        mcp_suite = root.find(".//testsuite[@name='MCP Agent Evaluation']")
        assert mcp_suite is not None

        # Check properties
        properties = mcp_suite.find("properties")
        assert properties is not None

        # Check specific properties
        prop_dict = {p.get("name"): p.get("value") for p in properties.findall("property")}
        assert prop_dict["model"] == "claude-sonnet-4-5-20250929"
        assert prop_dict["provider"] == "anthropic"
        assert prop_dict["agent_harness"] == "claude-code"
        assert prop_dict["benchmark"] == "swe-bench"
        assert prop_dict["dataset"] == "SWE-bench/SWE-bench_Lite"
        assert prop_dict["mcp_command"] == "npx"

    def test_cybergym_level_in_properties(self, tmp_path: Path) -> None:
        """Test that CyberGym level is included in properties when present."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "cybergym",
                    "dataset": "sunblaze-ucb/cybergym",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": 2,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-task",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find MCP test suite
        mcp_suite = root.find(".//testsuite[@name='MCP Agent Evaluation']")
        assert mcp_suite is not None

        # Check properties include cybergym_level
        properties = mcp_suite.find("properties")
        prop_dict = {p.get("name"): p.get("value") for p in properties.findall("property")}
        assert "cybergym_level" in prop_dict
        assert prop_dict["cybergym_level"] == "2"

    def test_tool_usage_in_system_out(self, tmp_path: Path) -> None:
        """Test that tool usage is included in system-out."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-task",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                        "tool_usage": {
                            "Bash": 5,
                            "Read": 3,
                            "Edit": 2,
                        },
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Find test case
        testcase = root.find(".//testcase[@name='test-task']")
        assert testcase is not None

        # Check system-out includes tool usage
        system_out = testcase.find("system-out")
        assert system_out is not None
        assert "Tool Usage:" in system_out.text
        assert "Bash: 5" in system_out.text
        assert "Read: 3" in system_out.text
        assert "Edit: 2" in system_out.text

    def test_output_directory_creation(self, tmp_path: Path) -> None:
        """Test that output directory is created if it doesn't exist."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-task",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                ),
            ],
        )

        # Use a nested path that doesn't exist
        output_path = tmp_path / "reports" / "ci" / "junit.xml"
        assert not output_path.parent.exists()

        save_junit_xml(results, output_path)

        # Verify directory and file were created
        assert output_path.parent.exists()
        assert output_path.exists()

    def test_mcp_only_evaluation(self, tmp_path: Path) -> None:
        """Test JUnit XML generation for MCP-only evaluation."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 1, "total": 1, "rate": 1.0},
                "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-task",
                    mcp={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                    baseline=None,  # No baseline run
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Should only have one test suite
        testsuites = root.findall("testsuite")
        assert len(testsuites) == 1
        assert testsuites[0].get("name") == "MCP Agent Evaluation"

    def test_baseline_only_evaluation(self, tmp_path: Path) -> None:
        """Test JUnit XML generation for baseline-only evaluation."""
        results = EvaluationResults(
            metadata={
                "timestamp": "2026-01-20T10:00:00+00:00",
                "config": {
                    "model": "claude-sonnet-4-5-20250929",
                    "provider": "anthropic",
                    "agent_harness": "claude-code",
                    "benchmark": "swe-bench",
                    "dataset": "SWE-bench/SWE-bench_Lite",
                    "sample_size": 1,
                    "timeout_seconds": 300,
                    "max_iterations": 10,
                    "cybergym_level": None,
                },
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                    "args_note": "{workdir} is replaced with task repository path at runtime",
                },
            },
            summary={
                "mcp": {"resolved": 0, "total": 0, "rate": 0.0},
                "baseline": {"resolved": 1, "total": 1, "rate": 1.0},
                "improvement": "N/A",
            },
            tasks=[
                TaskResult(
                    instance_id="test-task",
                    mcp=None,  # No MCP run
                    baseline={
                        "resolved": True,
                        "patch_generated": True,
                        "patch_applied": True,
                        "tokens": {"input": 100, "output": 200},
                        "iterations": 5,
                        "tool_calls": 10,
                    },
                ),
            ],
        )

        output_path = tmp_path / "junit.xml"
        save_junit_xml(results, output_path)

        tree = ET.parse(output_path)
        root = tree.getroot()

        # Should only have one test suite
        testsuites = root.findall("testsuite")
        assert len(testsuites) == 1
        assert testsuites[0].get("name") == "Baseline Agent Evaluation"
