"""Smoke testing to validate setup and connectivity before running benchmarks."""

import asyncio
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import docker

from .config import load_config
from .config_validator import validate_config

console = Console()


@dataclass
class SmokeTestResult:
    """Result of a smoke test check."""

    name: str
    passed: bool
    message: str
    details: str | None = None
    error: str | None = None


class SmokeTestRunner:
    """Runs smoke tests to validate setup and connectivity."""

    def __init__(self, config_path: Path):
        """Initialize smoke test runner.

        Args:
            config_path: Path to configuration file.
        """
        self.config_path = config_path
        self.results: list[SmokeTestResult] = []

    async def run_all_tests(self) -> list[SmokeTestResult]:
        """Run all smoke tests and return results.

        Returns:
            List of smoke test results.
        """
        self.results = []

        # Test 1: Configuration validation
        await self._test_config_validation()

        # Test 2: Docker availability
        await self._test_docker_availability()

        # Test 3: Anthropic API connectivity
        await self._test_anthropic_api()

        # Test 4: MCP server configuration
        await self._test_mcp_server_config()

        return self.results

    async def _test_config_validation(self) -> None:
        """Test configuration file validation."""
        try:
            validation_result = validate_config(self.config_path)

            if validation_result.valid:
                self.results.append(
                    SmokeTestResult(
                        name="Configuration Validation",
                        passed=True,
                        message="Configuration file is valid",
                        details=f"Config: {self.config_path}",
                    )
                )
            else:
                error_details = "\n".join(
                    [f"  - {e.field}: {e.error}" for e in validation_result.errors]
                )
                self.results.append(
                    SmokeTestResult(
                        name="Configuration Validation",
                        passed=False,
                        message="Configuration validation failed",
                        details=error_details,
                        error=f"Found {len(validation_result.errors)} errors",
                    )
                )
        except Exception as e:
            self.results.append(
                SmokeTestResult(
                    name="Configuration Validation",
                    passed=False,
                    message="Failed to validate configuration",
                    error=str(e),
                )
            )

    async def _test_docker_availability(self) -> None:
        """Test Docker daemon connectivity."""
        try:
            client = docker.from_env()
            # Ping Docker to check connectivity
            client.ping()

            # Get Docker info
            info = client.info()
            containers = info.get("Containers", 0)
            images = info.get("Images", 0)

            self.results.append(
                SmokeTestResult(
                    name="Docker Availability",
                    passed=True,
                    message="Docker daemon is running and accessible",
                    details=f"Containers: {containers}, Images: {images}",
                )
            )
        except docker.errors.DockerException as e:
            self.results.append(
                SmokeTestResult(
                    name="Docker Availability",
                    passed=False,
                    message="Docker daemon is not accessible",
                    error=str(e),
                    details="Ensure Docker Desktop/Engine is running",
                )
            )
        except Exception as e:
            self.results.append(
                SmokeTestResult(
                    name="Docker Availability",
                    passed=False,
                    message="Failed to connect to Docker",
                    error=str(e),
                )
            )

    async def _test_anthropic_api(self) -> None:
        """Test Anthropic API connectivity and authentication."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            self.results.append(
                SmokeTestResult(
                    name="Anthropic API",
                    passed=False,
                    message="ANTHROPIC_API_KEY not set",
                    details="Set ANTHROPIC_API_KEY environment variable",
                )
            )
            return

        try:
            client = Anthropic(api_key=api_key)

            # Make a minimal API call to test connectivity
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-3-5-haiku-20241022",  # Use fastest/cheapest model
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}],
            )

            if response.id:
                self.results.append(
                    SmokeTestResult(
                        name="Anthropic API",
                        passed=True,
                        message="API key is valid and API is accessible",
                        details=f"Test request ID: {response.id}",
                    )
                )
        except Exception as e:
            error_msg = str(e)
            details = None

            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                details = "Check that ANTHROPIC_API_KEY is valid"
            elif "rate limit" in error_msg.lower():
                details = "API rate limit reached - API is accessible"
                # Rate limit means API is working, just temporarily unavailable
                self.results.append(
                    SmokeTestResult(
                        name="Anthropic API",
                        passed=True,
                        message="API is accessible (rate limited)",
                        details=details,
                    )
                )
                return

            self.results.append(
                SmokeTestResult(
                    name="Anthropic API",
                    passed=False,
                    message="Failed to connect to Anthropic API",
                    error=error_msg,
                    details=details,
                )
            )

    async def _test_mcp_server_config(self) -> None:
        """Test MCP server configuration and health.

        Validates MCP server configuration and checks if the command is executable.
        See MCP specification for ping/health check details:
        https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping
        """
        try:
            config = load_config(self.config_path)

            # Check that we have a valid MCP server configuration
            if not config.mcp_server or not config.mcp_server.command:
                self.results.append(
                    SmokeTestResult(
                        name="MCP Server Configuration",
                        passed=False,
                        message="MCP server configuration is incomplete",
                        error="Missing command or configuration",
                    )
                )
                return

            details_parts = [
                f"Command: {config.mcp_server.command}",
            ]

            if config.mcp_server.args:
                # Show first few args (truncate if too long)
                args_str = " ".join(str(arg) for arg in config.mcp_server.args[:3])
                if len(config.mcp_server.args) > 3:
                    args_str += "..."
                details_parts.append(f"Args: {args_str}")

            # Check if command is available in PATH
            command_path = shutil.which(config.mcp_server.command)
            if not command_path:
                self.results.append(
                    SmokeTestResult(
                        name="MCP Server Health Check",
                        passed=False,
                        message=f"MCP server command not found: {config.mcp_server.command}",
                        error=f"Command '{config.mcp_server.command}' is not in PATH or not executable",
                        details="Suggestion: Install the MCP server or check your PATH environment variable\n"
                        "MCP Health Check Docs: https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping",
                    )
                )
                return

            details_parts.append(f"Executable: {command_path}")
            details_parts.append(f"Startup timeout: {config.mcp_server.startup_timeout_ms}ms")
            details_parts.append(f"Tool timeout: {config.mcp_server.tool_timeout_ms}ms")

            self.results.append(
                SmokeTestResult(
                    name="MCP Server Health Check",
                    passed=True,
                    message="MCP server is properly configured and executable",
                    details="\n".join(details_parts) + "\n\n"
                    "MCP Health Check Docs: https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping",
                )
            )
        except Exception as e:
            self.results.append(
                SmokeTestResult(
                    name="MCP Server Health Check",
                    passed=False,
                    message="Failed to validate MCP server configuration",
                    error=str(e),
                )
            )

    def print_results(self) -> None:
        """Print smoke test results in a formatted table."""
        table = Table(title="Smoke Test Results", show_header=True, header_style="bold cyan")
        table.add_column("Test", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Message")

        for result in self.results:
            status = "[green]✓ PASS[/green]" if result.passed else "[red]✗ FAIL[/red]"
            message = result.message
            if result.details:
                message += f"\n[dim]{result.details}[/dim]"
            if result.error:
                message += f"\n[red]Error: {result.error}[/red]"

            table.add_row(result.name, status, message)

        console.print(table)

    def get_summary(self) -> dict[str, Any]:
        """Get summary of test results.

        Returns:
            Dictionary with summary statistics.
        """
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": passed / total if total > 0 else 0,
            "all_passed": failed == 0 and total > 0,
        }

    def print_summary(self) -> None:
        """Print summary panel."""
        summary = self.get_summary()

        if summary["all_passed"]:
            status_text = "[green]✓ ALL TESTS PASSED[/green]"
            panel_style = "green"
        else:
            status_text = f"[red]✗ {summary['failed']} TEST(S) FAILED[/red]"
            panel_style = "red"

        summary_text = f"""
{status_text}

Passed: {summary["passed"]}/{summary["total"]}
Success Rate: {summary["success_rate"]:.0%}

[dim]Your setup is {"ready" if summary["all_passed"] else "not ready"} to run evaluations.[/dim]
"""

        console.print(Panel(summary_text.strip(), title="Summary", border_style=panel_style))


async def run_smoke_test(config_path: Path) -> bool:
    """Run smoke test and return success status.

    Args:
        config_path: Path to configuration file.

    Returns:
        True if all tests passed, False otherwise.
    """
    runner = SmokeTestRunner(config_path)

    console.print("\n[bold]Running smoke tests...[/bold]\n")

    await runner.run_all_tests()

    console.print()
    runner.print_results()
    console.print()
    runner.print_summary()
    console.print()

    summary = runner.get_summary()
    return summary["all_passed"]


async def run_mcp_preflight_check(
    config_path: Path, silent: bool = False
) -> tuple[bool, str | None]:
    """Run pre-flight MCP server health check before evaluation.

    Validates that the MCP server command exists and is executable.
    This is a quick check to catch configuration issues early.

    See MCP specification for ping/health check details:
    https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping

    Args:
        config_path: Path to configuration file.
        silent: If True, don't print output (used for testing).

    Returns:
        Tuple of (success: bool, error_message: str | None).
    """
    try:
        config = load_config(config_path)

        if not config.mcp_server or not config.mcp_server.command:
            error_msg = "MCP server not configured in config file"
            if not silent:
                console.print(f"[yellow]⚠️  Warning: {error_msg}[/yellow]")
            return False, error_msg

        command = config.mcp_server.command
        command_path = shutil.which(command)

        if not command_path:
            error_msg = (
                f"MCP server command '{command}' not found in PATH\n"
                f"  Suggestion: Install the MCP server or check your PATH environment variable\n"
                f"  MCP Health Check Docs: https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping"
            )
            if not silent:
                console.print("[red]✗ MCP Pre-flight Check Failed[/red]")
                console.print(f"[red]{error_msg}[/red]")
            return False, error_msg

        if not silent:
            console.print("[green]✓ MCP Pre-flight Check Passed[/green]")
            console.print(f"[dim]  MCP Command: {command} ({command_path})[/dim]")
            if config.mcp_server.args:
                args_str = " ".join(str(arg) for arg in config.mcp_server.args[:3])
                if len(config.mcp_server.args) > 3:
                    args_str += "..."
                console.print(f"[dim]  Args: {args_str}[/dim]")

        return True, None

    except Exception as e:
        error_msg = f"Failed to run MCP pre-flight check: {e}"
        if not silent:
            console.print("[red]✗ MCP Pre-flight Check Failed[/red]")
            console.print(f"[red]{error_msg}[/red]")
        return False, error_msg
