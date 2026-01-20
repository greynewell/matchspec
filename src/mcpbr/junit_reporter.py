"""JUnit XML report generation for CI/CD integration."""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .harness import EvaluationResults


def save_junit_xml(results: "EvaluationResults", output_path: Path) -> None:
    """Save evaluation results as JUnit XML format.

    Maps mcpbr evaluation results to JUnit XML format for CI/CD integration.
    Each task is represented as a test case, with resolved/unresolved mapped
    to pass/fail states.

    Args:
        results: Evaluation results from the harness.
        output_path: Path to save the JUnit XML file.

    JUnit XML Structure:
        - testsuites: Root element containing all test suites
        - testsuite: Container for test cases (one for MCP, one for baseline)
        - testcase: Individual task evaluation
        - failure: Task that was unresolved (test failed)
        - error: Task that encountered an error during execution
    """
    # Create root element
    testsuites = ET.Element("testsuites")
    testsuites.set("name", "mcpbr Evaluation")
    testsuites.set("timestamp", results.metadata["timestamp"])

    # Calculate overall statistics
    mcp_total = results.summary["mcp"]["total"]
    baseline_total = results.summary["baseline"]["total"]
    total_tests = mcp_total + baseline_total

    mcp_resolved = results.summary["mcp"]["resolved"]
    baseline_resolved = results.summary["baseline"]["resolved"]
    total_passed = mcp_resolved + baseline_resolved

    mcp_failed = mcp_total - mcp_resolved
    baseline_failed = baseline_total - baseline_resolved
    total_failures = mcp_failed + baseline_failed

    testsuites.set("tests", str(total_tests))
    testsuites.set("failures", str(total_failures))
    testsuites.set("errors", "0")

    # Create MCP test suite
    if mcp_total > 0:
        mcp_suite = _create_test_suite(
            results,
            "mcp",
            "MCP Agent Evaluation",
            mcp_total,
            mcp_resolved,
        )
        testsuites.append(mcp_suite)

    # Create baseline test suite
    if baseline_total > 0:
        baseline_suite = _create_test_suite(
            results,
            "baseline",
            "Baseline Agent Evaluation",
            baseline_total,
            baseline_resolved,
        )
        testsuites.append(baseline_suite)

    # Write XML to file
    tree = ET.ElementTree(testsuites)
    ET.indent(tree, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def _create_test_suite(
    results: "EvaluationResults",
    suite_type: str,
    suite_name: str,
    total: int,
    resolved: int,
) -> ET.Element:
    """Create a test suite element for either MCP or baseline.

    Args:
        results: Evaluation results.
        suite_type: Either "mcp" or "baseline".
        suite_name: Display name for the test suite.
        total: Total number of tasks in this suite.
        resolved: Number of resolved tasks.

    Returns:
        ElementTree Element representing the test suite.
    """
    testsuite = ET.Element("testsuite")
    testsuite.set("name", suite_name)
    testsuite.set("tests", str(total))
    testsuite.set("failures", str(total - resolved))
    testsuite.set("errors", "0")
    testsuite.set("skipped", "0")
    testsuite.set("timestamp", results.metadata["timestamp"])

    # Add metadata as properties
    properties = ET.SubElement(testsuite, "properties")

    _add_property(properties, "model", results.metadata["config"]["model"])
    _add_property(properties, "provider", results.metadata["config"]["provider"])
    _add_property(properties, "agent_harness", results.metadata["config"]["agent_harness"])
    _add_property(properties, "benchmark", results.metadata["config"]["benchmark"])
    _add_property(properties, "dataset", results.metadata["config"]["dataset"])

    if results.metadata["config"].get("cybergym_level") is not None:
        _add_property(
            properties, "cybergym_level", str(results.metadata["config"]["cybergym_level"])
        )

    if suite_type == "mcp":
        _add_property(properties, "mcp_command", results.metadata["mcp_server"]["command"])
        _add_property(properties, "mcp_args", str(results.metadata["mcp_server"]["args"]))

    # Calculate total time for all test cases
    total_time = 0.0
    for task in results.tasks:
        task_data = getattr(task, suite_type)
        if task_data:
            # Add test case
            testcase = _create_test_case(task.instance_id, task_data, suite_type)
            testsuite.append(testcase)

            # Accumulate time (if available)
            # Note: Current implementation doesn't track per-task time,
            # so we'll use 0.0 for now. This can be enhanced later.
            total_time += 0.0

    testsuite.set("time", f"{total_time:.3f}")

    return testsuite


def _create_test_case(instance_id: str, task_data: dict, suite_type: str) -> ET.Element:
    """Create a test case element for a single task.

    Args:
        instance_id: Task instance ID.
        task_data: Task result data (either mcp or baseline).
        suite_type: Either "mcp" or "baseline".

    Returns:
        ElementTree Element representing the test case.
    """
    testcase = ET.Element("testcase")
    testcase.set("name", instance_id)
    testcase.set("classname", f"mcpbr.{suite_type}")
    testcase.set("time", "0.000")  # TODO: Add timing information when available

    # Add system-out with metadata
    system_out = ET.SubElement(testcase, "system-out")
    output_lines = []
    output_lines.append(f"Instance ID: {instance_id}")
    output_lines.append(f"Run Type: {suite_type}")

    if task_data.get("tokens"):
        tokens = task_data["tokens"]
        output_lines.append(f"Input Tokens: {tokens.get('input', 0)}")
        output_lines.append(f"Output Tokens: {tokens.get('output', 0)}")

    output_lines.append(f"Iterations: {task_data.get('iterations', 0)}")
    output_lines.append(f"Tool Calls: {task_data.get('tool_calls', 0)}")

    if task_data.get("tool_usage"):
        output_lines.append("\nTool Usage:")
        for tool_name, count in task_data["tool_usage"].items():
            output_lines.append(f"  {tool_name}: {count}")

    if task_data.get("patch_generated"):
        output_lines.append(f"\nPatch Generated: Yes")
    else:
        output_lines.append(f"\nPatch Generated: No")

    if task_data.get("patch_applied") is not None:
        output_lines.append(f"Patch Applied: {task_data['patch_applied']}")

    # Add test results if available
    if task_data.get("fail_to_pass"):
        ftp = task_data["fail_to_pass"]
        output_lines.append(f"\nFail-to-Pass Tests: {ftp['passed']}/{ftp['total']}")

    if task_data.get("pass_to_pass"):
        ptp = task_data["pass_to_pass"]
        output_lines.append(f"Pass-to-Pass Tests: {ptp['passed']}/{ptp['total']}")

    system_out.text = "\n".join(output_lines)

    # Check if task was resolved
    resolved = task_data.get("resolved", False)

    if not resolved:
        # Task failed - add failure element
        failure = ET.SubElement(testcase, "failure")
        failure.set("type", "UnresolvedTask")

        # Determine failure message
        error_msg = task_data.get("error")
        eval_error = task_data.get("eval_error")

        if error_msg:
            failure.set("message", f"Task failed: {error_msg}")
            failure.text = f"Error during execution: {error_msg}"
        elif eval_error:
            failure.set("message", f"Evaluation failed: {eval_error}")
            failure.text = f"Evaluation error: {eval_error}"
        elif not task_data.get("patch_generated"):
            failure.set("message", "No patch generated")
            failure.text = "The agent did not generate a patch for this task."
        elif not task_data.get("patch_applied"):
            failure.set("message", "Patch could not be applied")
            failure.text = "The generated patch could not be applied to the repository."
        else:
            # Tests failed
            failure.set("message", "Tests failed after applying patch")
            failure_details = []

            if task_data.get("fail_to_pass"):
                ftp = task_data["fail_to_pass"]
                if ftp["passed"] < ftp["total"]:
                    failure_details.append(
                        f"Fail-to-Pass: {ftp['passed']}/{ftp['total']} tests passed"
                    )

            if task_data.get("pass_to_pass"):
                ptp = task_data["pass_to_pass"]
                if ptp["passed"] < ptp["total"]:
                    failure_details.append(
                        f"Pass-to-Pass: {ptp['passed']}/{ptp['total']} tests passed"
                    )

            if failure_details:
                failure.text = "\n".join(failure_details)
            else:
                failure.text = "Task was not resolved (reason unknown)."

    return testcase


def _add_property(properties: ET.Element, name: str, value: str) -> None:
    """Add a property element to the properties section.

    Args:
        properties: Properties element.
        name: Property name.
        value: Property value.
    """
    prop = ET.SubElement(properties, "property")
    prop.set("name", name)
    prop.set("value", value)
