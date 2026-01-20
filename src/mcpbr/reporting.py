"""Reporting utilities for evaluation results."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING
from xml.dom import minidom

import yaml
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from .harness import EvaluationResults


def print_summary(results: "EvaluationResults", console: Console) -> None:
    """Print a summary of evaluation results to the console.

    Args:
        results: Evaluation results.
        console: Rich console for output.
    """
    console.print()
    console.print("[bold]Evaluation Results[/bold]")
    console.print()

    table = Table(title="Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("MCP Agent", style="green")
    table.add_column("Baseline", style="yellow")

    mcp = results.summary["mcp"]
    baseline = results.summary["baseline"]

    table.add_row(
        "Resolved",
        f"{mcp['resolved']}/{mcp['total']}",
        f"{baseline['resolved']}/{baseline['total']}",
    )
    table.add_row(
        "Resolution Rate",
        f"{mcp['rate']:.1%}",
        f"{baseline['rate']:.1%}",
    )

    console.print(table)
    console.print()
    console.print(f"[bold]Improvement:[/bold] {results.summary['improvement']}")

    console.print()
    console.print("[bold]Per-Task Results[/bold]")

    task_table = Table()
    task_table.add_column("Instance ID", style="dim")
    task_table.add_column("MCP", justify="center")
    task_table.add_column("Baseline", justify="center")
    task_table.add_column("Error", style="red", max_width=50)

    for task in results.tasks:
        mcp_status = (
            "[green]PASS[/green]" if task.mcp and task.mcp.get("resolved") else "[red]FAIL[/red]"
        )
        if task.mcp is None:
            mcp_status = "[dim]-[/dim]"

        baseline_status = (
            "[green]PASS[/green]"
            if task.baseline and task.baseline.get("resolved")
            else "[red]FAIL[/red]"
        )
        if task.baseline is None:
            baseline_status = "[dim]-[/dim]"

        error_msg = ""
        if task.mcp and task.mcp.get("error"):
            error_msg = task.mcp.get("error", "")
        elif task.baseline and task.baseline.get("error"):
            error_msg = task.baseline.get("error", "")

        if len(error_msg) > 50:
            error_msg = error_msg[:47] + "..."

        task_table.add_row(task.instance_id, mcp_status, baseline_status, error_msg)

    console.print(task_table)


def save_json_results(results: "EvaluationResults", output_path: Path) -> None:
    """Save evaluation results to a JSON file.

    Args:
        results: Evaluation results.
        output_path: Path to save the JSON file.
    """
    data = {
        "metadata": results.metadata,
        "summary": results.summary,
        "tasks": [],
    }

    for task in results.tasks:
        task_data = {
            "instance_id": task.instance_id,
        }
        if task.mcp:
            task_data["mcp"] = task.mcp
        if task.baseline:
            task_data["baseline"] = task.baseline
        data["tasks"].append(task_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)


def save_markdown_report(results: "EvaluationResults", output_path: Path) -> None:
    """Save evaluation results as a Markdown report.

    Args:
        results: Evaluation results.
        output_path: Path to save the Markdown file.
    """
    lines = []

    lines.append("# SWE-bench MCP Evaluation Report")
    lines.append("")
    lines.append(f"**Generated:** {results.metadata['timestamp']}")
    lines.append(f"**Model:** {results.metadata['config']['model']}")
    lines.append(f"**Dataset:** {results.metadata['config']['dataset']}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")

    mcp = results.summary["mcp"]
    baseline = results.summary["baseline"]

    lines.append("| Metric | MCP Agent | Baseline |")
    lines.append("|--------|-----------|----------|")
    lines.append(
        f"| Resolved | {mcp['resolved']}/{mcp['total']} | {baseline['resolved']}/{baseline['total']} |"
    )
    lines.append(f"| Resolution Rate | {mcp['rate']:.1%} | {baseline['rate']:.1%} |")
    lines.append("")
    lines.append(f"**Improvement:** {results.summary['improvement']}")
    lines.append("")

    lines.append("## MCP Server Configuration")
    lines.append("")
    lines.append("```")
    lines.append(f"command: {results.metadata['mcp_server']['command']}")
    lines.append(f"args: {results.metadata['mcp_server']['args']}")
    lines.append("```")
    lines.append("")

    lines.append("## Per-Task Results")
    lines.append("")
    lines.append("| Instance ID | MCP | Baseline |")
    lines.append("|-------------|-----|----------|")

    for task in results.tasks:
        mcp_status = "PASS" if task.mcp and task.mcp.get("resolved") else "FAIL"
        if task.mcp is None:
            mcp_status = "-"

        baseline_status = "PASS" if task.baseline and task.baseline.get("resolved") else "FAIL"
        if task.baseline is None:
            baseline_status = "-"

        lines.append(f"| {task.instance_id} | {mcp_status} | {baseline_status} |")

    lines.append("")

    mcp_only = []
    baseline_only = []
    both = []
    neither = []

    for task in results.tasks:
        mcp_resolved = task.mcp and task.mcp.get("resolved")
        baseline_resolved = task.baseline and task.baseline.get("resolved")

        if mcp_resolved and baseline_resolved:
            both.append(task.instance_id)
        elif mcp_resolved:
            mcp_only.append(task.instance_id)
        elif baseline_resolved:
            baseline_only.append(task.instance_id)
        else:
            neither.append(task.instance_id)

    lines.append("## Analysis")
    lines.append("")
    lines.append(f"- **Resolved by both:** {len(both)}")
    lines.append(f"- **Resolved by MCP only:** {len(mcp_only)}")
    lines.append(f"- **Resolved by Baseline only:** {len(baseline_only)}")
    lines.append(f"- **Resolved by neither:** {len(neither)}")
    lines.append("")

    if mcp_only:
        lines.append("### Tasks Resolved by MCP Only")
        lines.append("")
        for task_id in mcp_only:
            lines.append(f"- {task_id}")
        lines.append("")

    if baseline_only:
        lines.append("### Tasks Resolved by Baseline Only")
        lines.append("")
        for task_id in baseline_only:
            lines.append(f"- {task_id}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


def save_yaml_results(results: "EvaluationResults", output_path: Path) -> None:
    """Save evaluation results to a YAML file.

    Args:
        results: Evaluation results.
        output_path: Path to save the YAML file.
    """
    data = {
        "metadata": results.metadata,
        "summary": results.summary,
        "tasks": [],
    }

    for task in results.tasks:
        task_data = {
            "instance_id": task.instance_id,
        }
        if task.mcp:
            task_data["mcp"] = task.mcp
        if task.baseline:
            task_data["baseline"] = task.baseline
        data["tasks"].append(task_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def save_xml_results(results: "EvaluationResults", output_path: Path) -> None:
    """Save evaluation results to an XML file.

    Args:
        results: Evaluation results.
        output_path: Path to save the XML file.
    """
    # Create root element
    root = ET.Element("mcpbr-evaluation")
    root.set("version", "1.0")

    # Add metadata section
    metadata = ET.SubElement(root, "metadata")
    ET.SubElement(metadata, "timestamp").text = results.metadata["timestamp"]

    # Add config subsection
    config = ET.SubElement(metadata, "config")
    for key, value in results.metadata["config"].items():
        if value is not None:
            ET.SubElement(config, key).text = str(value)

    # Add MCP server subsection
    mcp_server = ET.SubElement(metadata, "mcp-server")
    for key, value in results.metadata["mcp_server"].items():
        if isinstance(value, list):
            list_elem = ET.SubElement(mcp_server, key)
            for item in value:
                ET.SubElement(list_elem, "item").text = str(item)
        elif isinstance(value, dict):
            dict_elem = ET.SubElement(mcp_server, key)
            for k, v in value.items():
                ET.SubElement(dict_elem, k).text = str(v)
        else:
            ET.SubElement(mcp_server, key).text = str(value)

    # Add summary section
    summary = ET.SubElement(root, "summary")

    # MCP summary
    mcp_summary = ET.SubElement(summary, "mcp")
    ET.SubElement(mcp_summary, "resolved").text = str(results.summary["mcp"]["resolved"])
    ET.SubElement(mcp_summary, "total").text = str(results.summary["mcp"]["total"])
    ET.SubElement(mcp_summary, "rate").text = f"{results.summary['mcp']['rate']:.4f}"

    # Baseline summary
    baseline_summary = ET.SubElement(summary, "baseline")
    ET.SubElement(baseline_summary, "resolved").text = str(results.summary["baseline"]["resolved"])
    ET.SubElement(baseline_summary, "total").text = str(results.summary["baseline"]["total"])
    ET.SubElement(baseline_summary, "rate").text = f"{results.summary['baseline']['rate']:.4f}"

    # Improvement
    ET.SubElement(summary, "improvement").text = results.summary["improvement"]

    # Add tasks section
    tasks = ET.SubElement(root, "tasks")
    for task in results.tasks:
        task_elem = ET.SubElement(tasks, "task")
        task_elem.set("id", task.instance_id)

        # Add MCP result if present
        if task.mcp:
            mcp_result = ET.SubElement(task_elem, "mcp")
            _add_task_result_elements(mcp_result, task.mcp)

        # Add baseline result if present
        if task.baseline:
            baseline_result = ET.SubElement(task_elem, "baseline")
            _add_task_result_elements(baseline_result, task.baseline)

    # Pretty print the XML
    xml_string = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(xml_string)
    pretty_xml = dom.toprettyxml(indent="  ")

    # Remove extra blank lines
    lines = [line for line in pretty_xml.split("\n") if line.strip()]
    pretty_xml = "\n".join(lines)

    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(pretty_xml)


def _add_task_result_elements(parent: ET.Element, result: dict) -> None:
    """Add task result elements to parent XML element.

    Args:
        parent: Parent XML element to add result data to.
        result: Task result dictionary.
    """
    # Add simple boolean/string fields
    if "resolved" in result:
        ET.SubElement(parent, "resolved").text = str(result["resolved"]).lower()
    if "patch_generated" in result:
        ET.SubElement(parent, "patch-generated").text = str(result["patch_generated"]).lower()
    if "patch_applied" in result:
        ET.SubElement(parent, "patch-applied").text = str(result["patch_applied"]).lower()
    if "error" in result:
        ET.SubElement(parent, "error").text = str(result["error"])

    # Add iterations and tool_calls
    if "iterations" in result:
        ET.SubElement(parent, "iterations").text = str(result["iterations"])
    if "tool_calls" in result:
        ET.SubElement(parent, "tool-calls").text = str(result["tool_calls"])

    # Add tokens subsection
    if "tokens" in result:
        tokens = ET.SubElement(parent, "tokens")
        ET.SubElement(tokens, "input").text = str(result["tokens"]["input"])
        ET.SubElement(tokens, "output").text = str(result["tokens"]["output"])

    # Add tool_usage subsection if present
    if "tool_usage" in result:
        tool_usage = ET.SubElement(parent, "tool-usage")
        for tool_name, count in result["tool_usage"].items():
            tool_elem = ET.SubElement(tool_usage, "tool")
            tool_elem.set("name", tool_name)
            tool_elem.text = str(count)

    # Add test results if present
    if "fail_to_pass" in result:
        fail_to_pass = ET.SubElement(parent, "fail-to-pass")
        ET.SubElement(fail_to_pass, "passed").text = str(result["fail_to_pass"]["passed"])
        ET.SubElement(fail_to_pass, "total").text = str(result["fail_to_pass"]["total"])

    if "pass_to_pass" in result:
        pass_to_pass = ET.SubElement(parent, "pass-to-pass")
        ET.SubElement(pass_to_pass, "passed").text = str(result["pass_to_pass"]["passed"])
        ET.SubElement(pass_to_pass, "total").text = str(result["pass_to_pass"]["total"])

    # Add messages if present
    if "messages" in result:
        messages = ET.SubElement(parent, "messages")
        for msg in result["messages"]:
            msg_elem = ET.SubElement(messages, "message")
            if isinstance(msg, dict):
                for key, value in msg.items():
                    ET.SubElement(msg_elem, key).text = str(value)
            else:
                msg_elem.text = str(msg)
