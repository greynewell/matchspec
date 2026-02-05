"""Comprehensive pre-flight validation for mcpbr evaluations."""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

import docker

from .config import HarnessConfig

console = Console()


@dataclass
class PreflightCheck:
    """Result of a single pre-flight check."""

    name: str
    status: str  # "✓", "✗", or "⚠"
    details: str
    critical: bool = True  # If True, failure prevents execution


def run_comprehensive_preflight(
    config: HarnessConfig, config_path: Path
) -> tuple[list[PreflightCheck], list[str]]:
    """Run all pre-flight checks and return results.

    Args:
        config: Harness configuration.
        config_path: Path to configuration file.

    Returns:
        Tuple of (checks: list of PreflightCheck, failures: list of error messages).
    """
    checks: list[PreflightCheck] = []
    failures: list[str] = []

    # 1. Docker check
    try:
        client = docker.from_env()
        client.ping()
        info = client.info()
        version = info.get("ServerVersion", "unknown")
        checks.append(
            PreflightCheck(
                name="Docker",
                status="✓",
                details=f"v{version} running",
                critical=True,
            )
        )
    except docker.errors.DockerException:
        checks.append(
            PreflightCheck(
                name="Docker",
                status="✗",
                details="Not running",
                critical=True,
            )
        )
        failures.append("Docker is not running. Please start Docker Desktop and try again.")
    except Exception as e:
        checks.append(
            PreflightCheck(
                name="Docker",
                status="✗",
                details=f"Error: {str(e)[:40]}",
                critical=True,
            )
        )
        failures.append(f"Docker check failed: {e}")

    # 2. API key check
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        # Mask the key for display
        masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        checks.append(
            PreflightCheck(
                name="ANTHROPIC_API_KEY",
                status="✓",
                details=f"Set ({masked})",
                critical=True,
            )
        )
    else:
        checks.append(
            PreflightCheck(
                name="ANTHROPIC_API_KEY",
                status="✗",
                details="Not set",
                critical=True,
            )
        )
        failures.append(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please set it before running: export ANTHROPIC_API_KEY=your-key"
        )

    # 3. MCP server check (handle both single and comparison modes)
    if config.comparison_mode:
        # Check both servers in comparison mode
        servers_ok = True

        if config.mcp_server_a and config.mcp_server_a.command:
            command_path_a = shutil.which(config.mcp_server_a.command)
            if not command_path_a:
                servers_ok = False
                failures.append(
                    f"MCP server A command '{config.mcp_server_a.command}' not found in PATH. "
                    "Please install it or check your PATH."
                )
        else:
            servers_ok = False
            failures.append("MCP server A not configured")

        if config.mcp_server_b and config.mcp_server_b.command:
            command_path_b = shutil.which(config.mcp_server_b.command)
            if not command_path_b:
                servers_ok = False
                failures.append(
                    f"MCP server B command '{config.mcp_server_b.command}' not found in PATH. "
                    "Please install it or check your PATH."
                )
        else:
            servers_ok = False
            failures.append("MCP server B not configured")

        if servers_ok:
            checks.append(
                PreflightCheck(
                    name="MCP Server",
                    status="✓",
                    details="Comparison mode: both servers found",
                    critical=True,
                )
            )
        else:
            checks.append(
                PreflightCheck(
                    name="MCP Server",
                    status="✗",
                    details="Comparison mode: server(s) missing",
                    critical=True,
                )
            )
    elif config.mcp_server and config.mcp_server.command:
        # Single server mode
        command_path = shutil.which(config.mcp_server.command)
        if command_path:
            checks.append(
                PreflightCheck(
                    name="MCP Server",
                    status="✓",
                    details=f"{config.mcp_server.command} found",
                    critical=True,
                )
            )
        else:
            checks.append(
                PreflightCheck(
                    name="MCP Server",
                    status="✗",
                    details=f"{config.mcp_server.command} not found",
                    critical=True,
                )
            )
            failures.append(
                f"MCP server command '{config.mcp_server.command}' not found in PATH. "
                "Please install it or check your PATH."
            )
    else:
        checks.append(
            PreflightCheck(
                name="MCP Server",
                status="✗",
                details="Not configured",
                critical=True,
            )
        )
        failures.append("MCP server not configured in config file")

    # 4. Config file check (already loaded, so just mark as valid)
    checks.append(
        PreflightCheck(
            name="Config File",
            status="✓",
            details=f"{config_path.name}",
            critical=True,
        )
    )

    # 5. Dataset access check (optional - HuggingFace)
    try:
        # Try importing huggingface_hub to check if available
        import huggingface_hub  # noqa: F401

        checks.append(
            PreflightCheck(
                name="Dataset Access",
                status="✓",
                details="HuggingFace available",
                critical=False,
            )
        )
    except ImportError:
        checks.append(
            PreflightCheck(
                name="Dataset Access",
                status="⚠",
                details="HuggingFace not installed",
                critical=False,
            )
        )
        # Not a failure, just a warning

    # 6. Disk space check
    try:
        stat = shutil.disk_usage("/")
        free_gb = stat.free // (1024**3)
        if free_gb > 10:
            checks.append(
                PreflightCheck(
                    name="Disk Space",
                    status="✓",
                    details=f"{free_gb} GB free",
                    critical=False,
                )
            )
        else:
            checks.append(
                PreflightCheck(
                    name="Disk Space",
                    status="⚠",
                    details=f"Only {free_gb} GB free",
                    critical=False,
                )
            )
            # Warning, not a critical failure
    except Exception:
        checks.append(
            PreflightCheck(
                name="Disk Space",
                status="⚠",
                details="Could not check",
                critical=False,
            )
        )

    return checks, failures


def display_preflight_results(checks: list[PreflightCheck], failures: list[str]) -> None:
    """Display pre-flight check results in a formatted table.

    Args:
        checks: List of pre-flight check results.
        failures: List of failure messages.
    """
    table = Table(title="Pre-flight Validation", show_header=True, header_style="bold")
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center", width=8)
    table.add_column("Details")

    for check in checks:
        # Color the row based on status
        if check.status == "✓":
            style = "green"
        elif check.status == "✗":
            style = "red"
        else:  # "⚠"
            style = "yellow"

        table.add_row(check.name, check.status, check.details, style=style)

    console.print()
    console.print(table)
    console.print()

    if failures:
        console.print("[red bold]✗ Pre-flight failed[/red bold]")
        for failure in failures:
            console.print(f"[red]  • {failure}[/red]")
        console.print()
    else:
        console.print("[green bold]✓ All checks passed, starting evaluation...[/green bold]")
        console.print()
