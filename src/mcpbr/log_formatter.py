"""Log formatting utilities for stream-json output from Claude CLI."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from rich.console import Console
from rich.text import Text


@dataclass
class FormatterConfig:
    """Configuration for the stream event formatter."""

    max_content_length: int = 200
    max_file_lines: int = 10
    show_timestamps: bool = True
    workdir: str | None = None
    verbosity: int = 1  # 0=silent, 1=summary, 2=detailed
    compact_prefix: bool = True  # Shorten task IDs for readability


class StreamEventFormatter:
    """Formats stream-json events from Claude CLI for readable console output."""

    def __init__(
        self,
        console: Console,
        config: FormatterConfig | None = None,
        log_file: TextIO | None = None,
    ) -> None:
        """Initialize the formatter.

        Args:
            console: Rich console for output.
            config: Formatter configuration.
            log_file: Optional file handle for writing raw JSON logs.
        """
        self.console = console
        self.config = config or FormatterConfig()
        self.log_file = log_file
        self._temp_dir_pattern = re.compile(
            r"/(?:private/)?(?:var/folders|tmp)/[^/]+(?:/[^/]+)*/mcpbr_[^/]+/"
        )

    def format_line(self, line: str, prefix: str | None = None) -> None:
        """Format and print a single line of stream-json output.

        Args:
            line: Raw JSON line from Claude CLI.
            prefix: Optional prefix (e.g., task ID).
        """
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()

        if not line.strip():
            return

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if self.config.verbosity >= 2:
                self.console.print(f"[dim]{line}[/dim]")
            return

        event_type = event.get("type", "")

        if event_type == "assistant":
            self._format_assistant_event(event, prefix)
        elif event_type == "user":
            self._format_user_event(event, prefix)
        elif event_type == "result":
            self._format_result_event(event, prefix)

    def _format_assistant_event(self, event: dict[str, Any], prefix: str | None) -> None:
        """Format an assistant message event."""
        message = event.get("message", {})
        if not isinstance(message, dict):
            return
        content = message.get("content", [])

        if not isinstance(content, list):
            return

        for block in content:
            if not isinstance(block, dict):
                continue

            if block.get("type") == "tool_use":
                self._format_tool_use(block, prefix)
            elif block.get("type") == "text" and self.config.verbosity >= 2:
                text = block.get("text", "")
                if text.strip():
                    self._print_event(prefix, "", text[:200], style="dim", symbol="|")

    def _format_tool_use(self, block: dict[str, Any], prefix: str | None) -> None:
        """Format a tool_use block."""
        tool_name = block.get("name", "unknown")
        tool_input = block.get("input", {})

        summary = self._summarize_tool_input(tool_name, tool_input)
        self._print_event(prefix, tool_name, summary, style="cyan", symbol=">")

    def _format_user_event(self, event: dict[str, Any], prefix: str | None) -> None:
        """Format a user/tool_result event."""
        message = event.get("message", {})
        if not isinstance(message, dict):
            return
        content = message.get("content", [])

        if not isinstance(content, list):
            return

        for block in content:
            if not isinstance(block, dict):
                continue

            if block.get("type") == "tool_result":
                self._format_tool_result(block, event, prefix)

    def _format_tool_result(
        self, block: dict[str, Any], event: dict[str, Any], prefix: str | None
    ) -> None:
        """Format a tool_result block."""
        result_content = block.get("content", "")
        tool_use_result = event.get("tool_use_result", {})
        if not isinstance(tool_use_result, dict):
            tool_use_result = {}

        is_error = block.get("is_error", False)

        # Extract detailed error information
        error_context = self._extract_error_context(result_content, tool_use_result, block)

        # Use bold red for errors to make them stand out
        style = "bold red" if is_error else "dim"

        summary = self._summarize_tool_result(
            result_content, tool_use_result, is_error, error_context
        )
        symbol = "!" if is_error else "<"
        label = "ERROR" if is_error else ""
        self._print_event(prefix, label, summary, style=style, symbol=symbol)

    def _format_result_event(self, event: dict[str, Any], prefix: str | None) -> None:
        """Format a final result event."""
        if self.config.verbosity < 1:
            return

        num_turns = event.get("num_turns", 0)
        usage = event.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)

        summary = f"turns={num_turns} tokens={tokens_in:,}/{tokens_out:,}"
        self._print_event(prefix, "done", summary, style="green", symbol="*")

    def _summarize_tool_input(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Create a summary of tool input."""
        if self.config.verbosity < 2:
            return ""

        summaries = []

        if tool_name in ("Read", "read_file"):
            file_path = tool_input.get("file_path", tool_input.get("path", ""))
            file_path = self._shorten_path(file_path)
            offset = tool_input.get("offset")
            limit = tool_input.get("limit")
            if offset is not None or limit is not None:
                # Ensure offset and limit are integers for arithmetic
                offset = int(offset) if offset is not None else 0
                limit = int(limit) if limit is not None else 0
                end_line = offset + limit if limit else "..."
                summaries.append(f"{file_path} (lines {offset}-{end_line})")
            else:
                summaries.append(file_path)

        elif tool_name in ("Grep", "grep"):
            pattern = tool_input.get("pattern", "")
            file_type = tool_input.get("type", "")
            summaries.append(f'pattern="{pattern}"')
            if file_type:
                summaries.append(f"type={file_type}")

        elif tool_name in ("Bash", "bash", "shell"):
            command = tool_input.get("command", "")
            if len(command) > self.config.max_content_length:
                command = command[: self.config.max_content_length] + "..."
            command = self._shorten_path(command)
            summaries.append(command)

        elif tool_name in ("Write", "write_file", "Edit", "edit_file"):
            file_path = tool_input.get("file_path", tool_input.get("path", ""))
            file_path = self._shorten_path(file_path)
            summaries.append(file_path)

        else:
            for key, value in tool_input.items():
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                summaries.append(f"{key}={value}")
                if len(summaries) >= 3:
                    break

        return ", ".join(summaries) if summaries else ""

    def _extract_error_context(
        self, content: str, tool_use_result: dict[str, Any], block: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract detailed error context from tool result.

        Args:
            content: Raw content string from tool result
            tool_use_result: Structured tool result data
            block: The tool_result block

        Returns:
            Dictionary with error details including HTTP status codes, error messages, etc.
        """
        error_context = {}

        # Check for HTTP error codes in content
        http_patterns = [
            (r"\b401\b", "http_401_unauthorized"),
            (r"\b403\b", "http_403_forbidden"),
            (r"\b404\b", "http_404_not_found"),
            (r"\b500\b", "http_500_server_error"),
            (r"\b502\b", "http_502_bad_gateway"),
            (r"\b503\b", "http_503_unavailable"),
        ]

        content_str = str(content).lower()
        for pattern, error_type in http_patterns:
            if re.search(pattern, content_str):
                error_context["error_type"] = error_type
                error_context["http_error"] = True
                break

        # Check for common error keywords
        if "unauthorized" in content_str or "authentication" in content_str:
            error_context["auth_error"] = True
        if "timeout" in content_str:
            error_context["timeout_error"] = True
        if "connection" in content_str and ("refused" in content_str or "failed" in content_str):
            error_context["connection_error"] = True

        # Extract error from tool_use_result
        if isinstance(tool_use_result, dict):
            if "error" in tool_use_result:
                error_context["tool_error"] = tool_use_result["error"]
            if "stderr" in tool_use_result and tool_use_result["stderr"]:
                error_context["stderr"] = tool_use_result["stderr"]

        return error_context

    def _summarize_tool_result(
        self,
        content: str,
        tool_use_result: dict[str, Any],
        is_error: bool = False,
        error_context: dict[str, Any] | None = None,
    ) -> str:
        """Create a summary of tool result.

        Args:
            content: Raw content string
            tool_use_result: Structured tool result data
            is_error: Whether this is an error result
            error_context: Error context information from _extract_error_context

        Returns:
            Human-readable summary string
        """
        if error_context is None:
            error_context = {}

        # For errors, prioritize showing detailed error information
        if is_error:
            error_parts = []

            # Add HTTP error type if detected
            if error_context.get("http_error"):
                error_type = error_context.get("error_type", "http_error")
                if "401" in error_type:
                    error_parts.append("HTTP 401 Unauthorized - Check API credentials")
                elif "403" in error_type:
                    error_parts.append("HTTP 403 Forbidden - Check API permissions")
                elif "404" in error_type:
                    error_parts.append("HTTP 404 Not Found")
                elif "500" in error_type:
                    error_parts.append("HTTP 500 Internal Server Error")
                elif "502" in error_type:
                    error_parts.append("HTTP 502 Bad Gateway")
                elif "503" in error_type:
                    error_parts.append("HTTP 503 Service Unavailable")

            # Add authentication error context
            if error_context.get("auth_error") and not error_context.get("http_error"):
                error_parts.append("Authentication failed")

            # Add timeout context
            if error_context.get("timeout_error"):
                error_parts.append("Request timed out")

            # Add connection error context
            if error_context.get("connection_error"):
                error_parts.append("Connection failed")

            # Add tool-specific error
            if error_context.get("tool_error"):
                error_parts.append(f"Tool error: {error_context['tool_error']}")

            # Add stderr if available
            if error_context.get("stderr"):
                stderr = str(error_context["stderr"])[:200]
                error_parts.append(f"stderr: {stderr}")

            # Add content if we haven't found a specific error type
            if not error_parts and content:
                content_str = str(content)
                if len(content_str) > 300:
                    content_str = content_str[:300] + "..."
                error_parts.append(content_str)

            # If still no error details, flag it
            if not error_parts:
                error_parts.append(
                    "MCP tool returned error with no details (check MCP server logs)"
                )

            return "\n".join(error_parts)

        # For non-errors, use original logic
        if not isinstance(tool_use_result, dict):
            return str(tool_use_result)[:200] if tool_use_result else ""
        mode = tool_use_result.get("mode", "")

        if mode == "files_with_matches":
            filenames = tool_use_result.get("filenames", [])
            num_files = tool_use_result.get("numFiles", len(filenames))
            if filenames:
                shortened = [self._shorten_path(f) for f in filenames[:3]]
                result = f"Found {num_files} files: " + ", ".join(shortened)
                if num_files > 3:
                    result += f" (+{num_files - 3} more)"
                return result
            return f"Found {num_files} files"

        if "stdout" in tool_use_result:
            stdout = tool_use_result.get("stdout", "")
            if stdout:
                stdout = self._shorten_path(stdout)
                lines = stdout.split("\n")
                if len(lines) > self.config.max_file_lines:
                    return (
                        "\n".join(lines[: self.config.max_file_lines])
                        + f"\n... ({len(lines) - self.config.max_file_lines} more lines)"
                    )
                return stdout[: self.config.max_content_length]
            # Flag empty stdout more clearly
            return "(empty output - possible error)"

        if "file" in tool_use_result:
            file_info = tool_use_result.get("file", {})
            file_path = file_info.get("filePath", "")
            num_lines = file_info.get("numLines", 0)
            start_line = file_info.get("startLine", 1)
            return f"{self._shorten_path(file_path)} ({num_lines} lines from {start_line})"

        if isinstance(content, str):
            content = self._shorten_path(content)
            if len(content) > self.config.max_content_length:
                return content[: self.config.max_content_length] + "..."
            # Flag truly empty responses
            if not content or not content.strip():
                return "(empty response - check if MCP tool succeeded)"
            return content[:200]

        return "(no output)"

    def _shorten_path(self, text: str) -> str:
        """Replace long temp directory paths with $WORKDIR."""
        if self.config.workdir:
            workdir = self.config.workdir
            # Handle macOS /private prefix mismatch - text might have /private even if workdir doesn't
            if not workdir.startswith("/private"):
                text = text.replace(f"/private{workdir}", "$WORKDIR")
            text = text.replace(workdir, "$WORKDIR")

        text = self._temp_dir_pattern.sub("$WORKDIR/", text)
        return text

    def _shorten_task_id(self, task_id: str) -> str:
        """Shorten a task ID for display.

        Input: 'astropy__astropy-12907:mcp' -> 'astropy-12907:mcp'
        """
        if not self.config.compact_prefix:
            return task_id

        # Split off run type suffix (mcp/base) if present
        run_type = ""
        if ":" in task_id:
            task_id, run_type = task_id.rsplit(":", 1)
            run_type = f":{run_type}"

        # Handle format like 'repo__repo-issue' by extracting 'repo-issue'
        if "__" in task_id:
            parts = task_id.split("__")
            if len(parts) == 2:
                task_id = parts[1]

        return f"{task_id}{run_type}"

    def print_run_start(self, task_id: str, run_type: str) -> None:
        """Print a banner indicating the start of a run.

        Args:
            task_id: Task instance ID.
            run_type: Type of run ('mcp' or 'baseline').
        """
        if self.config.verbosity < 1:
            return

        timestamp = ""
        if self.config.show_timestamps:
            timestamp = datetime.now().strftime("%H:%M:%S ")

        short_id = self._shorten_task_id(task_id)
        run_label = run_type.upper()

        text = Text()
        text.append(timestamp, style="dim")
        text.append(f"[{run_label}] ", style="bold magenta")
        text.append(f"Starting {run_type} run for ", style="dim")
        text.append(short_id, style="cyan")
        self.console.print(text)

    def _print_event(
        self,
        prefix: str | None,
        label: str,
        content: str,
        style: str = "white",
        symbol: str = "",
    ) -> None:
        """Print a formatted event to the console."""
        timestamp = ""
        if self.config.show_timestamps:
            timestamp = datetime.now().strftime("%H:%M:%S ")

        short_prefix = self._shorten_task_id(prefix) if prefix else ""
        prefix_str = f"{short_prefix:20} " if short_prefix else ""

        text = Text()
        text.append(timestamp, style="dim")
        text.append(prefix_str, style="dim")

        if symbol:
            text.append(f"{symbol} ", style=f"bold {style}")

        if label:
            text.append(f"{label}", style=f"bold {style}")
            if content:
                text.append(" ", style=style)

        if content:
            first_line = content.split("\n")[0]
            text.append(first_line, style="dim" if not label else style)

        self.console.print(text)

        if content and "\n" in content and self.config.verbosity >= 2:
            base_indent = len(timestamp) + len(prefix_str) + (2 if symbol else 0)
            indent = " " * base_indent
            for line in content.split("\n")[1 : self.config.max_file_lines + 1]:
                self.console.print(f"{indent}{line}", style="dim")


def create_formatter(
    console: Console,
    verbosity: int = 1,
    workdir: str | None = None,
    log_file_path: Path | None = None,
) -> tuple[StreamEventFormatter, TextIO | None]:
    """Create a stream event formatter.

    Args:
        console: Rich console for output.
        verbosity: Verbosity level (0=silent, 1=summary, 2=detailed).
        workdir: Working directory path to shorten in output.
        log_file_path: Optional path to write raw JSON logs.

    Returns:
        Tuple of (formatter, log_file_handle). Caller should close the file handle.
    """
    log_file: TextIO | None = None
    if log_file_path:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_file_path, "w")

    config = FormatterConfig(
        verbosity=verbosity,
        workdir=workdir,
        show_timestamps=True,
    )

    formatter = StreamEventFormatter(console, config, log_file)
    return formatter, log_file


class InstanceLogWriter:
    """Writes per-instance log files with properly formatted JSON.

    Collects stream-json events and writes them as a formatted JSON file
    when closed.
    """

    def __init__(
        self,
        log_dir: Path,
        instance_id: str,
        run_type: str,
    ) -> None:
        """Initialize the instance log writer.

        Args:
            log_dir: Directory to write log files.
            instance_id: Task instance ID (e.g., 'astropy__astropy-12907').
            run_type: Type of run ('mcp' or 'baseline').
        """
        self.log_dir = log_dir
        self.instance_id = instance_id
        self.run_type = run_type
        self.events: list[dict[str, Any]] = []
        self._closed = False
        self._start_time = datetime.now()

    def write(self, line: str) -> None:
        """Write a line of stream-json output.

        Args:
            line: Raw JSON line from Claude CLI.
        """
        if self._closed:
            return

        line = line.strip()
        if not line:
            return

        try:
            event = json.loads(line)
            self.events.append(event)
        except json.JSONDecodeError:
            pass

    def flush(self) -> None:
        """Flush is a no-op; events are written on close."""
        pass

    def close(self) -> None:
        """Write the collected events to a formatted JSON file."""
        if self._closed:
            return

        self._closed = True

        self.log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = self._start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{self.instance_id}_{self.run_type}_{timestamp}.json"
        output_path = self.log_dir / filename

        output_data = {
            "instance_id": self.instance_id,
            "run_type": self.run_type,
            "events": self.events,
        }

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

    def __enter__(self) -> "InstanceLogWriter":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - writes the file."""
        self.close()
