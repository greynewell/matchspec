"""Agent harness abstractions for different agent backends."""

import asyncio
import json
import os
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TextIO, runtime_checkable

from rich.console import Console

from .docker_env import TaskEnvironment
from .log_formatter import InstanceLogWriter, StreamEventFormatter

if TYPE_CHECKING:
    from .config import MCPServerConfig


@dataclass
class AgentResult:
    """Result from an agent run."""

    patch: str
    success: bool
    error: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    iterations: int = 0
    tool_calls: int = 0
    tool_usage: dict[str, int] = field(default_factory=dict)
    tool_failures: dict[str, int] = field(default_factory=dict)
    tool_errors: dict[str, list[str]] = field(default_factory=dict)
    messages: list[dict[str, Any]] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    profiling_report: dict[str, Any] | None = None
    cost_usd: float | None = None  # Total cost from API (includes cache tokens)


@runtime_checkable
class AgentHarness(Protocol):
    """Protocol for agent harnesses that solve SWE-bench tasks.

    To add a new harness:
    1. Create a class implementing this protocol
    2. Add it to HARNESS_REGISTRY
    3. Add the harness name to VALID_HARNESSES in config.py
    """

    async def solve(
        self,
        task: dict[str, Any],
        workdir: str,
        timeout: int = 300,
        verbose: bool = False,
        task_id: str | None = None,
        env: TaskEnvironment | None = None,
    ) -> AgentResult:
        """Solve a SWE-bench task and return the patch.

        Args:
            task: SWE-bench task dictionary with problem_statement, etc.
            workdir: Path to the repository working directory.
            timeout: Timeout in seconds.
            verbose: If True, stream output to console.
            task_id: Task identifier for prefixing output.
            env: Optional Docker environment to run inside.

        Returns:
            AgentResult with the generated patch.
        """
        ...


async def _run_cli_command(
    command: list[str],
    workdir: str,
    timeout: int,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> tuple[int, str, str]:
    """Run a CLI command asynchronously.

    Args:
        command: Command and arguments to run.
        workdir: Working directory.
        timeout: Timeout in seconds.
        env: Optional environment variables.
        input_text: Optional text to pass to stdin.

    Returns:
        Tuple of (exit_code, stdout, stderr).
    """
    full_env = {**os.environ}
    if env:
        full_env.update(env)

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=workdir,
        env=full_env,
        stdin=asyncio.subprocess.PIPE if input_text else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        input_bytes = input_text.encode("utf-8") if input_text else None
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=input_bytes),
            timeout=timeout,
        )
        return (
            process.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    except asyncio.TimeoutError:
        process.kill()
        return -1, "", "Command timed out"


async def _run_cli_streaming(
    command: list[str],
    workdir: str,
    timeout: int,
    env: dict[str, str] | None = None,
    prefix: str | None = None,
    console: Console | None = None,
    formatter: StreamEventFormatter | None = None,
) -> tuple[int, str, str]:
    """Run a CLI command with real-time streaming output.

    Args:
        command: Command and arguments to run.
        workdir: Working directory.
        timeout: Timeout in seconds.
        env: Optional environment variables.
        prefix: Optional prefix for each output line.
        console: Rich console for output (if None and no formatter, uses print).
        formatter: Optional StreamEventFormatter for structured JSON output.

    Returns:
        Tuple of (exit_code, stdout, stderr).
    """
    full_env = {**os.environ}
    if env:
        full_env.update(env)

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=workdir,
        env=full_env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    async def read_stream(
        stream: asyncio.StreamReader | None,
        lines: list[str],
        is_stderr: bool = False,
    ) -> None:
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace").rstrip()
            lines.append(decoded)

            if is_stderr:
                if console:
                    console.print(f"[dim red]{decoded}[/dim red]")
            elif formatter:
                formatter.format_line(decoded, prefix)
            elif console:
                prefix_str = f"[{prefix}] " if prefix else ""
                console.print(f"[dim]{prefix_str}{decoded}[/dim]")

    try:
        await asyncio.wait_for(
            asyncio.gather(
                read_stream(process.stdout, stdout_lines),
                read_stream(process.stderr, stderr_lines, is_stderr=True),
            ),
            timeout=timeout,
        )
        await process.wait()
        return (
            process.returncode or 0,
            "\n".join(stdout_lines),
            "\n".join(stderr_lines),
        )
    except asyncio.TimeoutError:
        process.kill()
        return -1, "\n".join(stdout_lines), "Command timed out"


async def _get_git_diff(workdir: str) -> str:
    """Get the git diff of changes, including only modifications to existing files.

    Stages all changes but only includes modifications (not new files) in the diff.
    This excludes agent-created debug scripts, test files, and other artifacts.

    Args:
        workdir: Path to the git repository.

    Returns:
        Git diff string with only modified file changes.
    """
    await _run_cli_command(["git", "add", "-A"], workdir, timeout=30)

    # Try with filter first (excludes debug scripts, test files)
    exit_code, stdout, stderr = await _run_cli_command(
        [
            "git",
            "diff",
            "--cached",
            "HEAD",
            "--diff-filter=M",
        ],
        workdir,
        timeout=30,
    )
    if exit_code == 0 and stdout.strip():
        return stdout

    # Fallback: try without filter if nothing found (for new files like HumanEval solution.py)
    exit_code, stdout, stderr = await _run_cli_command(
        ["git", "diff", "--cached", "HEAD"],
        workdir,
        timeout=30,
    )
    if exit_code == 0:
        return stdout
    return ""


async def _get_git_diff_in_docker(env: TaskEnvironment) -> str:
    """Get the git diff of changes from inside Docker container.

    Args:
        env: Docker task environment.

    Returns:
        Git diff string with only modified file changes.
    """
    workdir = env.workdir

    await env.exec_command(
        f"git config --global --add safe.directory {workdir}",
        timeout=10,
        workdir=workdir,
    )

    _, status_out, _ = await env.exec_command(
        "git status --short",
        timeout=30,
        workdir=workdir,
    )

    await env.exec_command("git add -A", timeout=30, workdir=workdir)

    exit_code, stdout, stderr = await env.exec_command(
        "git diff --cached HEAD --diff-filter=M",
        timeout=30,
        workdir=workdir,
    )
    if exit_code == 0 and stdout.strip():
        return stdout

    exit_code, stdout, stderr = await env.exec_command(
        "git diff --cached HEAD",
        timeout=30,
        workdir=workdir,
    )
    if exit_code == 0 and stdout.strip():
        return stdout

    _, unstaged, _ = await env.exec_command(
        "git diff",
        timeout=30,
        workdir=workdir,
    )
    if unstaged.strip():
        await env.exec_command("git add -A", timeout=30, workdir=workdir)
        _, stdout, _ = await env.exec_command(
            "git diff --cached HEAD",
            timeout=30,
            workdir=workdir,
        )
        if stdout.strip():
            return stdout

    return ""


async def _write_prompt_file(workdir: str, problem_statement: str) -> str:
    """Write the problem statement to a temporary file.

    Args:
        workdir: Working directory.
        problem_statement: The problem statement text.

    Returns:
        Path to the prompt file.
    """
    prompt_path = os.path.join(workdir, ".swebench_prompt.md")
    Path(prompt_path).write_text(f"# Problem Statement\n\n{problem_statement}")
    return prompt_path


def _parse_tool_usage_from_stream(
    stdout: str,
) -> tuple[
    int,
    dict[str, int],
    dict[str, int],
    dict[str, list[str]],
    int,
    int,
    int,
    str | None,
    float | None,
]:
    """Parse tool usage and metadata from stream-json output.

    Args:
        stdout: Raw stdout from Claude Code CLI in stream-json format.

    Returns:
        Tuple of (total_tool_calls, tool_usage_dict, tool_failures_dict,
                  tool_errors_dict, num_turns, tokens_in, tokens_out, result_subtype, cost_usd).
    """
    tool_usage: dict[str, int] = {}
    tool_failures: dict[str, int] = {}
    tool_errors: dict[str, list[str]] = {}
    tool_use_id_to_name: dict[str, str] = {}
    total_tool_calls = 0
    num_turns = 0
    tokens_in = 0
    tokens_out = 0
    result_tokens_in = 0
    result_tokens_out = 0
    has_result = False
    result_subtype: str | None = None
    cost_usd: float | None = None

    for line in stdout.split("\n"):
        if not line.strip():
            continue
        try:
            event = json.loads(line)

            if event.get("type") == "assistant":
                message = event.get("message", {})
                content = message.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_name = block.get("name", "unknown")
                            tool_id = block.get("id", "")
                            tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
                            total_tool_calls += 1
                            # Track tool_use_id -> tool_name for failure tracking
                            if tool_id:
                                tool_use_id_to_name[tool_id] = tool_name

                usage = message.get("usage", {})
                tokens_in += usage.get("input_tokens", 0)
                tokens_out += usage.get("output_tokens", 0)

            if event.get("type") == "user":
                message = event.get("message", {})
                content = message.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            is_error = block.get("is_error", False)
                            if is_error:
                                tool_use_id = block.get("tool_use_id", "")
                                tool_name = tool_use_id_to_name.get(tool_use_id, "unknown")
                                # Increment failure count
                                tool_failures[tool_name] = tool_failures.get(tool_name, 0) + 1
                                # Capture error message
                                error_content = block.get("content", "")
                                if isinstance(error_content, str):
                                    error_msg = error_content[:200]  # Truncate long errors
                                elif isinstance(error_content, list):
                                    # Extract text from content blocks
                                    texts = [
                                        item.get("text", "")
                                        for item in error_content
                                        if isinstance(item, dict) and "text" in item
                                    ]
                                    error_msg = " ".join(texts)[:200]
                                else:
                                    error_msg = str(error_content)[:200]

                                if tool_name not in tool_errors:
                                    tool_errors[tool_name] = []
                                # Only keep first few errors per tool to avoid memory bloat
                                if len(tool_errors[tool_name]) < 5:
                                    tool_errors[tool_name].append(error_msg)

            if event.get("type") == "result":
                has_result = True
                num_turns = event.get("num_turns", 1)
                result_subtype = event.get("subtype")
                usage = event.get("usage", {})
                result_tokens_in = usage.get("input_tokens", 0)
                result_tokens_out = usage.get("output_tokens", 0)
                # Extract total cost from API (includes cache tokens)
                cost_usd = event.get("total_cost_usd")

        except json.JSONDecodeError:
            continue

    if has_result and (result_tokens_in > 0 or result_tokens_out > 0):
        tokens_in = result_tokens_in
        tokens_out = result_tokens_out

    return (
        total_tool_calls,
        tool_usage,
        tool_failures,
        tool_errors,
        num_turns,
        tokens_in,
        tokens_out,
        result_subtype,
        cost_usd,
    )


DEFAULT_PROMPT = (
    "Fix the following bug in this repository:\n\n"
    "{problem_statement}\n\n"
    "IMPORTANT CONSTRAINTS:\n"
    "- Only modify the minimum files necessary to fix the bug\n"
    "- Do NOT create new test files\n"
    "- Do NOT create documentation files\n"
    "- Do NOT create reproduction scripts\n"
    "- Focus solely on the fix in existing source files"
)

MCP_PROMPT_SUFFIX = (
    "\n\nYou have access to an MCP server with additional tools. "
    "Consider using the MCP tools (prefixed with mcp__) when they would "
    "help you understand or navigate the codebase more effectively."
)


def _generate_no_patch_error_message(
    git_status: str,
    git_stderr: str,
    buggy_line: str,
    tool_usage: dict[str, int],
) -> str:
    """Generate accurate error message when no patch is produced.

    Args:
        git_status: Output from 'git status --short'
        git_stderr: Stderr from git command (may contain 'command not found')
        buggy_line: Result from buggy line check (empty if not present)
        tool_usage: Dictionary of tool names to call counts

    Returns:
        Human-readable error message describing what actually happened
    """
    # Check if git is missing
    if git_stderr and "command not found" in git_stderr:
        return (
            "git command not found - ensure git is installed in the environment "
            "or use prebuilt Docker images with git pre-installed"
        )

    # Check if files were changed according to git
    if git_status.strip():
        return f"Files changed but no valid patch: {git_status.strip()}"

    # Check if any Edit/Write tools were actually called
    edit_tools = {"Edit", "Write", "NotebookEdit"}
    tools_used = set(tool_usage.keys())
    edit_tools_used = tools_used & edit_tools

    # If buggy line is not present (empty), it might have been fixed
    if not buggy_line:
        if edit_tools_used:
            # Edit tools were used but no git changes detected
            tools_str = ", ".join(sorted(edit_tools_used))
            return (
                f"{tools_str} tool(s) used but no changes detected - "
                "file may be unchanged or changes were reverted"
            )
        else:
            # No edit tools used and buggy line not found
            # Agent may have completed without making changes
            if tools_used:
                tools_list = ", ".join(sorted(tools_used))
                return (
                    f"No patches applied - agent completed without making changes. "
                    f"Tools used: {tools_list}"
                )
            else:
                return "No patches applied - agent made no tool calls"
    else:
        # Buggy line is still present
        return f"Buggy line still present: {buggy_line}"


class ClaudeCodeHarness:
    """Harness that uses Claude Code CLI (claude) for solving tasks."""

    def __init__(
        self,
        model: str | None = None,
        mcp_server: "MCPServerConfig | None" = None,
        prompt: str | None = None,
        max_iterations: int = 10,
        verbosity: int = 1,
        log_file: TextIO | InstanceLogWriter | None = None,
        mcp_logs_dir: Path | None = None,
        thinking_budget: int | None = None,
    ) -> None:
        """Initialize Claude Code harness.

        Args:
            model: Optional model override.
            mcp_server: MCP server configuration to use.
            prompt: Custom prompt template. Use {problem_statement} placeholder.
            max_iterations: Maximum number of agentic turns.
            verbosity: Verbosity level (0=silent, 1=summary, 2=detailed).
            log_file: Optional file handle for writing raw JSON logs.
            mcp_logs_dir: Directory for MCP server logs. Default: ~/.mcpbr_state/logs
            thinking_budget: Extended thinking token budget. Set to enable thinking mode.
        """
        self.model = model
        self.mcp_server = mcp_server
        self.prompt_template = prompt or DEFAULT_PROMPT
        if mcp_server:
            self.prompt_template += MCP_PROMPT_SUFFIX
        self.max_iterations = max_iterations
        self.verbosity = verbosity
        self.log_file = log_file
        self.mcp_logs_dir = mcp_logs_dir
        self.thinking_budget = thinking_budget
        self._console = Console()

    async def solve(
        self,
        task: dict[str, Any],
        workdir: str,
        timeout: int = 300,
        verbose: bool = False,
        task_id: str | None = None,
        env: TaskEnvironment | None = None,
    ) -> AgentResult:
        """Solve task using Claude Code CLI.

        If env is provided and has claude_cli_installed=True, runs inside Docker.
        Otherwise runs locally on the host.
        """
        if env and env.claude_cli_installed:
            return await self._solve_in_docker(task, env, timeout, verbose, task_id)

        return await self._solve_locally(task, workdir, timeout, verbose, task_id)

    async def _solve_locally(
        self,
        task: dict[str, Any],
        workdir: str,
        timeout: int,
        verbose: bool,
        task_id: str | None,
    ) -> AgentResult:
        """Solve task using local Claude Code CLI."""
        if not shutil.which("claude"):
            return AgentResult(
                patch="",
                success=False,
                error="Claude Code CLI (claude) not found in PATH",
            )

        problem_statement = task.get("problem_statement", "")
        prompt = self.prompt_template.format(problem_statement=problem_statement)
        instance_id = task_id or task.get("instance_id", "unknown")

        mcp_server_name = None
        if self.mcp_server:
            mcp_server_name = self.mcp_server.name
            args = self.mcp_server.get_args_for_workdir(workdir)
            mcp_env = self.mcp_server.get_expanded_env()
            add_cmd = [
                "claude",
                "mcp",
                "add",
                mcp_server_name,
                "--",
                self.mcp_server.command,
            ] + args
            exit_code, stdout, stderr = await _run_cli_command(
                add_cmd, workdir, timeout=30, env=mcp_env
            )
            if exit_code != 0:
                self._console.print(
                    f"[yellow]Warning: MCP server add failed (exit {exit_code}): {stderr or stdout}[/yellow]"
                )

        try:
            command = [
                "claude",
                "--print",
                "--verbose",
                "--dangerously-skip-permissions",
                "--output-format",
                "stream-json",
                "--max-turns",
                str(self.max_iterations),
            ]

            if self.model:
                command.extend(["--model", self.model])

            command.append(prompt)

            # Prepare environment variables
            claude_env: dict[str, str] | None = None
            if self.thinking_budget is not None:
                claude_env = {"MAX_THINKING_TOKENS": str(self.thinking_budget)}

            if verbose:
                from .log_formatter import FormatterConfig

                config = FormatterConfig(
                    verbosity=self.verbosity,
                    workdir=workdir,
                    show_timestamps=True,
                )
                formatter = StreamEventFormatter(self._console, config, self.log_file)

                run_type = "mcp" if self.mcp_server else "baseline"
                formatter.print_run_start(instance_id, run_type)

                exit_code, stdout, stderr = await _run_cli_streaming(
                    command,
                    workdir,
                    timeout,
                    prefix=instance_id,
                    console=self._console,
                    formatter=formatter,
                    env=claude_env,
                )
            else:
                exit_code, stdout, stderr = await _run_cli_command(
                    command,
                    workdir,
                    timeout,
                    env=claude_env,
                )

            (
                total_tool_calls,
                tool_usage,
                tool_failures,
                tool_errors,
                num_turns,
                tokens_in,
                tokens_out,
                result_subtype,
                cost_usd,
            ) = _parse_tool_usage_from_stream(stdout)

            if result_subtype == "error_max_turns" and num_turns > self.max_iterations:
                num_turns = self.max_iterations

            if exit_code != 0:
                error_msg = stderr or "Unknown error"
                if mcp_server_name:
                    await _run_cli_command(
                        ["claude", "mcp", "remove", mcp_server_name],
                        workdir,
                        timeout=10,
                    )
                return AgentResult(
                    patch="",
                    success=False,
                    error=f"Claude Code failed (exit {exit_code}): {error_msg}",
                    stdout=stdout,
                    stderr=stderr,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                    iterations=num_turns,
                    tool_calls=total_tool_calls,
                    tool_usage=tool_usage,
                    tool_failures=tool_failures,
                    tool_errors=tool_errors,
                    cost_usd=cost_usd,
                )

            if mcp_server_name:
                await _run_cli_command(
                    ["claude", "mcp", "remove", mcp_server_name],
                    workdir,
                    timeout=10,
                )

            # Check git status to understand what happened
            git_exit, git_status, git_stderr = await _run_cli_command(
                ["git", "status", "--short"],
                workdir,
                timeout=30,
            )

            patch = await _get_git_diff(workdir)

            # Generate appropriate error message if no patch
            error_msg = None
            if not patch:
                error_msg = _generate_no_patch_error_message(
                    git_status=git_status,
                    git_stderr=git_stderr,
                    buggy_line="",  # Local mode doesn't have buggy line check
                    tool_usage=tool_usage,
                )

            return AgentResult(
                patch=patch,
                success=bool(patch),
                error=error_msg,
                iterations=num_turns or 1,
                stdout=stdout,
                stderr=stderr,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                tool_calls=total_tool_calls,
                tool_usage=tool_usage,
                tool_failures=tool_failures,
                tool_errors=tool_errors,
                cost_usd=cost_usd,
            )
        except Exception:
            if mcp_server_name:
                await _run_cli_command(
                    ["claude", "mcp", "remove", mcp_server_name],
                    workdir,
                    timeout=10,
                )
            raise

    async def _solve_in_docker(
        self,
        task: dict[str, Any],
        env: TaskEnvironment,
        timeout: int,
        verbose: bool,
        task_id: str | None,
    ) -> AgentResult:
        """Solve task using Claude Code CLI inside Docker container."""
        problem_statement = task.get("problem_statement", "")
        prompt = self.prompt_template.format(problem_statement=problem_statement)
        instance_id = task_id or task.get("instance_id", "unknown")

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return AgentResult(
                patch="",
                success=False,
                error="ANTHROPIC_API_KEY environment variable not set",
                cost_usd=None,
            )

        docker_env = {
            "ANTHROPIC_API_KEY": api_key,
            "HOME": "/home/mcpbr",
            "USER": "mcpbr",
        }

        # Add MCP timeout configuration if MCP server is configured
        # See: https://code.claude.com/docs/en/settings.md
        if self.mcp_server:
            docker_env["MCP_TIMEOUT"] = str(self.mcp_server.startup_timeout_ms)
            docker_env["MCP_TOOL_TIMEOUT"] = str(self.mcp_server.tool_timeout_ms)

        # Add thinking budget to enable extended thinking
        # See: https://code.claude.com/docs/en/common-workflows#use-extended-thinking-thinking-mode
        if self.thinking_budget is not None:
            docker_env["MAX_THINKING_TOKENS"] = str(self.thinking_budget)

        prompt_file = "/tmp/.mcpbr_prompt.txt"
        await env.exec_command(
            f"cat > {prompt_file} << 'MCPBR_PROMPT_EOF'\n{prompt}\nMCPBR_PROMPT_EOF",
            timeout=10,
        )
        await env.exec_command(f"chown mcpbr:mcpbr {prompt_file}", timeout=5)

        env_file = "/tmp/.mcpbr_env.sh"
        # Use shlex.quote() to safely escape all environment variable values
        env_exports = (
            f"export ANTHROPIC_API_KEY={shlex.quote(api_key)}\nexport HOME='/home/mcpbr'\n"
        )

        # Add MCP server env vars and timeout configuration
        if self.mcp_server:
            # Add MCP timeout configuration for Claude CLI
            # See: https://code.claude.com/docs/en/settings.md
            env_exports += (
                f"export MCP_TIMEOUT={shlex.quote(str(self.mcp_server.startup_timeout_ms))}\n"
            )
            env_exports += (
                f"export MCP_TOOL_TIMEOUT={shlex.quote(str(self.mcp_server.tool_timeout_ms))}\n"
            )

            # Add user-defined MCP server env vars
            for key, value in self.mcp_server.get_expanded_env().items():
                # Sanitize key (must be valid shell identifier) and quote value
                safe_key = key.replace("-", "_").replace(".", "_")
                env_exports += f"export {safe_key}={shlex.quote(value)}\n"

        # Add thinking budget to enable extended thinking
        if self.thinking_budget is not None:
            env_exports += f"export MAX_THINKING_TOKENS={shlex.quote(str(self.thinking_budget))}\n"

        await env.exec_command(
            f"cat > {env_file} << 'MCPBR_ENV_EOF'\n{env_exports}MCPBR_ENV_EOF",
            timeout=10,
        )
        await env.exec_command(f"chown mcpbr:mcpbr {env_file}", timeout=5)

        # Register MCP server if configured (separate from main execution for better error reporting)
        mcp_server_name = None
        if self.mcp_server:
            mcp_server_name = self.mcp_server.name
            args = self.mcp_server.get_args_for_workdir(env.workdir)
            args_str = " ".join(args)

            # Log MCP server initialization
            if verbose:
                self._console.print(f"[cyan]Registering MCP server: {mcp_server_name}[/cyan]")
                self._console.print(f"[dim]  Command: {self.mcp_server.command} {args_str}[/dim]")

            # Register MCP server separately with its own timeout
            # Use shlex.quote() to prevent shell injection and handle spaces/special characters
            quoted_workdir = shlex.quote(env.workdir)
            quoted_env_file = shlex.quote(env_file)
            quoted_server_name = shlex.quote(mcp_server_name)
            quoted_command = shlex.quote(self.mcp_server.command)
            quoted_args = " ".join(shlex.quote(arg) for arg in args)

            mcp_add_cmd = [
                "/bin/bash",
                "-c",
                f"cd {quoted_workdir} && su mcpbr -c 'source {quoted_env_file} && cd {quoted_workdir} && claude mcp add {quoted_server_name} -- {quoted_command} {quoted_args}'",
            ]

            try:
                mcp_exit_code, mcp_stdout, mcp_stderr = await env.exec_command(
                    mcp_add_cmd,
                    timeout=60,  # Separate 60s timeout for MCP registration
                    environment=docker_env,
                )

                if mcp_exit_code != 0:
                    error_msg = f"MCP server registration failed (exit {mcp_exit_code})"
                    if mcp_stderr:
                        error_msg += f": {mcp_stderr}"
                    if mcp_stdout:
                        error_msg += f"\nStdout: {mcp_stdout}"
                    if verbose:
                        self._console.print(f"[red]✗ {error_msg}[/red]")

                    # Clean up temp files before early return
                    await env.exec_command(f"rm -f {prompt_file} {env_file}", timeout=5)

                    return AgentResult(
                        patch="",
                        success=False,
                        error=error_msg,
                        stdout=mcp_stdout,
                        stderr=mcp_stderr,
                        cost_usd=None,
                    )

                if verbose:
                    self._console.print("[green]✓ MCP server registered successfully[/green]")
                    if mcp_stdout.strip():
                        self._console.print(f"[dim]{mcp_stdout.strip()}[/dim]")

            except asyncio.TimeoutError:
                error_msg = "MCP server registration timed out after 60s. The MCP server may have failed to start or is hanging during initialization."
                if verbose:
                    self._console.print(f"[red]✗ {error_msg}[/red]")

                # Clean up temp files before early return
                await env.exec_command(f"rm -f {prompt_file} {env_file}", timeout=5)

                return AgentResult(
                    patch="",
                    success=False,
                    error=error_msg,
                    cost_usd=None,
                )

        try:
            claude_args = [
                "--print",
                "--verbose",
                "--dangerously-skip-permissions",
                "--output-format",
                "stream-json",
                "--max-turns",
                str(self.max_iterations),
            ]

            if self.model:
                claude_args.extend(["--model", self.model])

            claude_args_str = " ".join(claude_args)

            # Run Claude Code (MCP server already registered above)
            # Use shlex.quote() to prevent shell injection
            quoted_workdir = shlex.quote(env.workdir)
            quoted_env_file = shlex.quote(env_file)
            quoted_prompt_file = shlex.quote(prompt_file)

            # Build inner command first, then quote for su -c
            inner_cmd = f'source {quoted_env_file} && cd {quoted_workdir} && claude {claude_args_str} "$(cat {quoted_prompt_file})"'

            command = [
                "/bin/bash",
                "-c",
                f"cd {quoted_workdir} && su mcpbr -c {shlex.quote(inner_cmd)}",
            ]

            # Set up MCP server log file if MCP is enabled
            mcp_log_file = None
            mcp_log_path = None
            if self.mcp_server:
                from pathlib import Path

                # Determine logs directory: use mcp_logs_dir if provided, otherwise fall back to home directory
                if self.mcp_logs_dir:
                    state_dir = self.mcp_logs_dir / "logs"
                else:
                    state_dir = Path.home() / ".mcpbr_state" / "logs"
                state_dir.mkdir(parents=True, exist_ok=True)
                # Sanitize instance_id to prevent path traversal
                safe_instance_id = instance_id.replace("/", "_").replace("\\", "_")
                mcp_log_path = state_dir / f"{safe_instance_id}_mcp.log"
                mcp_log_file = open(mcp_log_path, "w")

            if verbose:
                from .log_formatter import FormatterConfig

                config = FormatterConfig(
                    verbosity=self.verbosity,
                    workdir=env.workdir,
                    show_timestamps=True,
                )
                formatter = StreamEventFormatter(self._console, config, self.log_file)

                run_type = "mcp" if self.mcp_server else "baseline"
                formatter.print_run_start(instance_id, run_type)

                def on_stdout(line: str) -> None:
                    formatter.format_line(line, instance_id)
                    # Capture all stdout to MCP log
                    if mcp_log_file:
                        mcp_log_file.write(f"[STDOUT] {line}\n")
                        mcp_log_file.flush()

                def on_stderr(line: str) -> None:
                    self._console.print(f"[dim red]{line}[/dim red]")
                    # Capture all stderr to MCP log (MCP servers often log to stderr)
                    if mcp_log_file:
                        mcp_log_file.write(f"[STDERR] {line}\n")
                        mcp_log_file.flush()

                exit_code, stdout, stderr = await env.exec_command_streaming(
                    command,
                    workdir=env.workdir,
                    environment=docker_env,
                    timeout=timeout,
                    on_stdout=on_stdout,
                    on_stderr=on_stderr,
                )
            else:
                exit_code, stdout, stderr = await env.exec_command(
                    command,
                    timeout=timeout,
                    environment=docker_env,
                )

                # Write stdout/stderr to MCP log even in non-verbose mode
                if mcp_log_file:
                    for line in stdout.splitlines():
                        mcp_log_file.write(f"[STDOUT] {line}\n")
                    if stderr:
                        for line in stderr.splitlines():
                            mcp_log_file.write(f"[STDERR] {line}\n")
                    mcp_log_file.flush()

            (
                total_tool_calls,
                tool_usage,
                tool_failures,
                tool_errors,
                num_turns,
                tokens_in,
                tokens_out,
                result_subtype,
                cost_usd,
            ) = _parse_tool_usage_from_stream(stdout)

            if result_subtype == "error_max_turns" and num_turns > self.max_iterations:
                num_turns = self.max_iterations

            if exit_code != 0:
                error_msg = stderr or "Unknown error"

                # Add context about timeout vs other failures
                if num_turns == 0 and total_tool_calls == 0:
                    # Agent never started - likely timeout during execution
                    if exit_code == 124:  # Standard timeout exit code
                        error_msg = f"Task timed out after {timeout}s before starting execution. This may indicate the Claude Code agent failed to initialize or hung during startup."
                    else:
                        error_msg = f"Agent failed before making any progress (exit {exit_code}). {error_msg}"

                    if self.mcp_server:
                        error_msg += f"\n\nMCP server was registered: {mcp_server_name}. Check MCP server logs for initialization issues."
                        if mcp_log_path:
                            error_msg += f"\nMCP server logs saved to: {mcp_log_path}"

                if mcp_server_name:
                    # Use shlex.quote() for MCP removal command
                    quoted_env_file = shlex.quote(env_file)
                    quoted_server_name = shlex.quote(mcp_server_name)
                    remove_cmd = (
                        f"source {quoted_env_file} && claude mcp remove {quoted_server_name}"
                    )
                    await env.exec_command(
                        f"su mcpbr -c {shlex.quote(remove_cmd)}",
                        timeout=10,
                        environment=docker_env,
                    )

                return AgentResult(
                    patch="",
                    success=False,
                    error=f"Claude Code failed (exit {exit_code}): {error_msg}",
                    stdout=stdout,
                    stderr=stderr,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                    iterations=num_turns,
                    tool_calls=total_tool_calls,
                    tool_usage=tool_usage,
                    tool_failures=tool_failures,
                    tool_errors=tool_errors,
                    cost_usd=cost_usd,
                )

            if mcp_server_name:
                # Use shlex.quote() for MCP removal command
                quoted_env_file = shlex.quote(env_file)
                quoted_server_name = shlex.quote(mcp_server_name)
                remove_cmd = f"source {quoted_env_file} && claude mcp remove {quoted_server_name}"
                await env.exec_command(
                    f"su mcpbr -c {shlex.quote(remove_cmd)}",
                    timeout=10,
                    environment=docker_env,
                )

            _, git_status, git_stderr = await env.exec_command(
                "git status --short",
                timeout=30,
            )

            # Debug: check if the buggy line still exists (should show nothing if fixed)
            _, sep_check, _ = await env.exec_command(
                "grep -n '= 1$' /workspace/astropy/modeling/separable.py | grep 'cright'",
                timeout=10,
            )

            # Also check file modification time
            _, file_info, _ = await env.exec_command(
                "stat -c '%Y %n' /workspace/astropy/modeling/separable.py",
                timeout=10,
            )

            patch = await _get_git_diff_in_docker(env)

            error_msg = None
            if not patch:
                buggy_line = sep_check.strip()
                # Use helper function to generate accurate error message
                error_msg = _generate_no_patch_error_message(
                    git_status=git_status,
                    git_stderr=git_stderr,
                    buggy_line=buggy_line,
                    tool_usage=tool_usage,
                )

            return AgentResult(
                patch=patch,
                success=bool(patch),
                error=error_msg,
                iterations=num_turns or 1,
                stdout=stdout,
                stderr=stderr,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                tool_calls=total_tool_calls,
                tool_usage=tool_usage,
                tool_failures=tool_failures,
                tool_errors=tool_errors,
                cost_usd=cost_usd,
            )
        except asyncio.TimeoutError:
            # Task execution timed out - but we may have partial stdout with tool usage stats
            # Try to parse what we have so far from MCP log file
            partial_stdout = ""
            if mcp_log_file:
                try:
                    mcp_log_file.flush()
                    mcp_log_file.close()
                    # Read back the log to extract stdout lines
                    if mcp_log_path and mcp_log_path.exists():
                        with open(mcp_log_path, "r") as f:
                            stdout_lines = []
                            for line in f:
                                if line.startswith("[STDOUT] "):
                                    stdout_lines.append(line[9:])  # Strip "[STDOUT] " prefix
                            partial_stdout = "".join(stdout_lines)
                except Exception as e:
                    if verbose:
                        self._console.print(
                            f"[dim yellow]Failed to read partial stdout from MCP log: {e}[/dim yellow]"
                        )

            # Parse tool usage from partial stdout
            (
                total_tool_calls,
                tool_usage,
                tool_failures,
                tool_errors,
                num_turns,
                tokens_in,
                tokens_out,
                result_subtype,
                cost_usd,
            ) = _parse_tool_usage_from_stream(partial_stdout)

            if mcp_server_name:
                try:
                    # Use shlex.quote() for MCP removal command
                    quoted_env_file = shlex.quote(env_file)
                    quoted_server_name = shlex.quote(mcp_server_name)
                    remove_cmd = (
                        f"source {quoted_env_file} && claude mcp remove {quoted_server_name}"
                    )
                    await env.exec_command(
                        f"su mcpbr -c {shlex.quote(remove_cmd)}",
                        timeout=10,
                        environment=docker_env,
                    )
                except Exception as e:
                    if verbose:
                        self._console.print(f"[dim red]Failed to remove MCP server: {e}[/dim red]")

            error_msg = f"Task execution timed out after {timeout}s."
            if self.mcp_server:
                error_msg += f" MCP server '{mcp_server_name}' was registered successfully but the agent failed to complete within the timeout."
                if mcp_log_path:
                    error_msg += f"\nMCP server logs saved to: {mcp_log_path}"
            else:
                error_msg += " The Claude Code agent failed to complete within the timeout."

            # Include statistics from partial execution
            if total_tool_calls > 0:
                error_msg += f" Agent made {total_tool_calls} tool calls across {num_turns} iterations before timeout."

            return AgentResult(
                patch="",
                success=False,
                error=error_msg,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                iterations=num_turns,
                tool_calls=total_tool_calls,
                tool_usage=tool_usage,
                tool_failures=tool_failures,
                tool_errors=tool_errors,
                stdout=partial_stdout,
                cost_usd=cost_usd,
            )
        except Exception:
            if mcp_server_name:
                try:
                    # Use shlex.quote() for MCP removal command
                    quoted_env_file = shlex.quote(env_file)
                    quoted_server_name = shlex.quote(mcp_server_name)
                    remove_cmd = (
                        f"source {quoted_env_file} && claude mcp remove {quoted_server_name}"
                    )
                    await env.exec_command(
                        f"su mcpbr -c {shlex.quote(remove_cmd)}",
                        timeout=10,
                        environment=docker_env,
                    )
                except Exception as e:
                    if verbose:
                        self._console.print(f"[dim red]Failed to remove MCP server: {e}[/dim red]")
            raise
        finally:
            # Close MCP log file if it was opened
            if mcp_log_file:
                try:
                    mcp_log_file.close()
                    if verbose and mcp_log_path:
                        self._console.print(f"[dim]MCP server logs saved to: {mcp_log_path}[/dim]")
                except Exception as e:
                    if verbose:
                        self._console.print(f"[dim red]Failed to close MCP log file: {e}[/dim red]")

            await env.exec_command(f"rm -f {prompt_file} {env_file}", timeout=5)


HARNESS_REGISTRY: dict[str, type] = {
    "claude-code": ClaudeCodeHarness,
}


def create_harness(
    harness_name: str,
    model: str | None = None,
    mcp_server: "MCPServerConfig | None" = None,
    prompt: str | None = None,
    max_iterations: int = 10,
    verbosity: int = 1,
    log_file: TextIO | InstanceLogWriter | None = None,
    mcp_logs_dir: Path | None = None,
    thinking_budget: int | None = None,
) -> AgentHarness:
    """Factory function to create an agent harness.

    Args:
        harness_name: Name of the harness (currently only 'claude-code').
        model: Optional model override.
        mcp_server: MCP server configuration (used by claude-code harness).
        prompt: Custom prompt template. Use {problem_statement} placeholder.
        max_iterations: Maximum agent iterations (used by claude-code harness).
        verbosity: Verbosity level for logging (0=silent, 1=summary, 2=detailed).
        log_file: Optional file handle for writing raw JSON logs.
        mcp_logs_dir: Directory for MCP server logs.
        thinking_budget: Extended thinking token budget. Set to enable thinking mode.

    Returns:
        AgentHarness instance.

    Raises:
        ValueError: If harness_name is not recognized.
    """
    if harness_name not in HARNESS_REGISTRY:
        raise ValueError(
            f"Unknown harness: {harness_name}. Available harnesses: {list(HARNESS_REGISTRY.keys())}"
        )

    harness_class = HARNESS_REGISTRY[harness_name]

    return harness_class(
        model=model,
        mcp_server=mcp_server,
        prompt=prompt,
        max_iterations=max_iterations,
        verbosity=verbosity,
        log_file=log_file,
        mcp_logs_dir=mcp_logs_dir,
        thinking_budget=thinking_budget,
    )


def list_available_harnesses() -> list[str]:
    """List available external harness names.

    Returns:
        List of harness names.
    """
    return list(HARNESS_REGISTRY.keys())
