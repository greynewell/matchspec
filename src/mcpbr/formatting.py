"""Color and formatting options for CLI output.

Provides configurable themes and formatting utilities for consistent CLI output
across the mcpbr tool. Supports the NO_COLOR convention (https://no-color.org/)
and configurable themes via the MCPBR_THEME environment variable or CLI flags.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text


class Theme(Enum):
    """Available output themes.

    Attributes:
        DEFAULT: Rich colors with bold styles for maximum readability.
        MINIMAL: Subdued colors for less visual noise.
        PLAIN: No formatting or color at all.
    """

    DEFAULT = "default"
    MINIMAL = "minimal"
    PLAIN = "plain"


@dataclass(frozen=True)
class ThemeConfig:
    """Style configuration for a theme.

    Each field is a Rich markup style string used to format the corresponding
    message category (e.g., ``"bold green"`` for success messages).

    Attributes:
        success_style: Style for success messages.
        error_style: Style for error messages.
        warning_style: Style for warning messages.
        info_style: Style for informational messages.
        header_style: Style for section headers.
        dim_style: Style for secondary/dimmed text.
        highlight_style: Style for highlighted/emphasized text.
    """

    success_style: str = "bold green"
    error_style: str = "bold red"
    warning_style: str = "bold yellow"
    info_style: str = "bold blue"
    header_style: str = "bold magenta"
    dim_style: str = "dim"
    highlight_style: str = "bold cyan"


THEME_CONFIGS: dict[Theme, ThemeConfig] = {
    Theme.DEFAULT: ThemeConfig(
        success_style="bold green",
        error_style="bold red",
        warning_style="bold yellow",
        info_style="bold blue",
        header_style="bold magenta",
        dim_style="dim",
        highlight_style="bold cyan",
    ),
    Theme.MINIMAL: ThemeConfig(
        success_style="green",
        error_style="red",
        warning_style="yellow",
        info_style="blue",
        header_style="magenta",
        dim_style="dim",
        highlight_style="cyan",
    ),
    Theme.PLAIN: ThemeConfig(
        success_style="",
        error_style="",
        warning_style="",
        info_style="",
        header_style="",
        dim_style="",
        highlight_style="",
    ),
}


def _resolve_theme(theme_name: str | None = None) -> Theme:
    """Resolve a theme name string to a Theme enum value.

    Checks the provided name first, then the MCPBR_THEME environment variable,
    and falls back to ``Theme.DEFAULT``.

    Args:
        theme_name: Optional theme name (case-insensitive). One of
            ``"default"``, ``"minimal"``, or ``"plain"``.

    Returns:
        The resolved Theme enum value.

    Raises:
        ValueError: If the theme name is not recognized.
    """
    name = theme_name or os.environ.get("MCPBR_THEME")
    if name is None:
        return Theme.DEFAULT

    try:
        return Theme(name.strip().lower())
    except ValueError:
        valid = ", ".join(t.value for t in Theme)
        raise ValueError(f"Unknown theme '{name}'. Valid themes: {valid}") from None


def detect_color_support(force_color: bool | None = None) -> bool:
    """Determine whether the current environment supports color output.

    Resolution order:
        1. ``force_color`` parameter (explicit override).
        2. ``NO_COLOR`` environment variable -- if set (any value), colors are
           disabled per https://no-color.org/.
        3. ``MCPBR_THEME`` environment variable -- if set to ``"plain"``, colors
           are disabled.
        4. Terminal detection -- colors are enabled when stdout is a TTY.

    Args:
        force_color: Explicit override. ``True`` forces colors on, ``False``
            forces them off, ``None`` uses auto-detection.

    Returns:
        ``True`` if color output should be used, ``False`` otherwise.
    """
    if force_color is not None:
        return force_color

    # NO_COLOR convention: any value (including empty string) disables color
    if "NO_COLOR" in os.environ:
        return False

    # MCPBR_THEME=plain disables color
    theme_env = os.environ.get("MCPBR_THEME", "").strip().lower()
    if theme_env == "plain":
        return False

    # Auto-detect: color only when stdout is a TTY
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class OutputFormatter:
    """Formatted output for CLI messages.

    Provides methods to print and format success, error, warning, info, and
    header messages using Rich markup styles. Also supports table and progress
    bar rendering.

    Args:
        theme: The theme to use for formatting. Defaults to ``Theme.DEFAULT``.
        force_color: Explicit color override. ``True`` forces colors on,
            ``False`` forces them off, ``None`` uses auto-detection.
        console: Optional Rich Console instance. If not provided, one is
            created based on color support settings.
    """

    def __init__(
        self,
        theme: Theme = Theme.DEFAULT,
        force_color: bool | None = None,
        console: Console | None = None,
    ) -> None:
        self._theme = theme
        self._config = THEME_CONFIGS[theme]
        self._color_enabled = detect_color_support(force_color)

        if console is not None:
            self._console = console
        else:
            # When color is disabled, use no_color=True so Rich strips markup
            self._console = Console(no_color=not self._color_enabled)

    @property
    def theme(self) -> Theme:
        """The active theme."""
        return self._theme

    @property
    def config(self) -> ThemeConfig:
        """The active theme configuration."""
        return self._config

    @property
    def color_enabled(self) -> bool:
        """Whether color output is enabled."""
        return self._color_enabled

    @property
    def console(self) -> Console:
        """The underlying Rich console."""
        return self._console

    # ------------------------------------------------------------------
    # Print methods (write directly to console)
    # ------------------------------------------------------------------

    def success(self, message: str) -> None:
        """Print a success message.

        Args:
            message: The message text.
        """
        self._print_styled(message, self._config.success_style, prefix="[ok]")

    def error(self, message: str) -> None:
        """Print an error message.

        Args:
            message: The message text.
        """
        self._print_styled(message, self._config.error_style, prefix="[error]")

    def warning(self, message: str) -> None:
        """Print a warning message.

        Args:
            message: The message text.
        """
        self._print_styled(message, self._config.warning_style, prefix="[warn]")

    def info(self, message: str) -> None:
        """Print an informational message.

        Args:
            message: The message text.
        """
        self._print_styled(message, self._config.info_style, prefix="[info]")

    def header(self, message: str) -> None:
        """Print a section header.

        Args:
            message: The header text.
        """
        self._print_styled(message, self._config.header_style)

    # ------------------------------------------------------------------
    # Format methods (return styled strings without printing)
    # ------------------------------------------------------------------

    def format_success(self, message: str) -> str:
        """Return a Rich-markup formatted success string.

        Args:
            message: The message text.

        Returns:
            Formatted string with Rich markup tags, or plain text when
            colors are disabled.
        """
        return self._format_styled(message, self._config.success_style, prefix="[ok]")

    def format_error(self, message: str) -> str:
        """Return a Rich-markup formatted error string.

        Args:
            message: The message text.

        Returns:
            Formatted string with Rich markup tags, or plain text when
            colors are disabled.
        """
        return self._format_styled(message, self._config.error_style, prefix="[error]")

    def format_warning(self, message: str) -> str:
        """Return a Rich-markup formatted warning string.

        Args:
            message: The message text.

        Returns:
            Formatted string with Rich markup tags, or plain text when
            colors are disabled.
        """
        return self._format_styled(message, self._config.warning_style, prefix="[warn]")

    def format_info(self, message: str) -> str:
        """Return a Rich-markup formatted info string.

        Args:
            message: The message text.

        Returns:
            Formatted string with Rich markup tags, or plain text when
            colors are disabled.
        """
        return self._format_styled(message, self._config.info_style, prefix="[info]")

    def format_header(self, message: str) -> str:
        """Return a Rich-markup formatted header string.

        Args:
            message: The message text.

        Returns:
            Formatted string with Rich markup tags, or plain text when
            colors are disabled.
        """
        return self._format_styled(message, self._config.header_style)

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def table(
        self,
        title: str,
        columns: list[str],
        rows: list[list[Any]],
    ) -> None:
        """Print a formatted Rich table.

        Args:
            title: Table title displayed above the table.
            columns: List of column header names.
            rows: List of rows, where each row is a list of cell values.
                Values are converted to strings automatically.
        """
        tbl = Table(title=title, show_header=True, header_style=self._config.header_style)
        for col in columns:
            tbl.add_column(col)
        for row in rows:
            tbl.add_row(*(str(cell) for cell in row))
        self._console.print(tbl)

    # ------------------------------------------------------------------
    # Progress bar
    # ------------------------------------------------------------------

    def progress_bar(self) -> Progress:
        """Return a configured Rich Progress instance.

        Returns:
            A ``rich.progress.Progress`` object with spinner, description,
            bar, completion count, elapsed time, and remaining time columns.
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self._console,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _print_styled(self, message: str, style: str, prefix: str = "") -> None:
        """Print a message with a Rich style and optional prefix.

        Uses ``rich.text.Text`` objects throughout to prevent Rich from
        interpreting bracket-style prefixes (e.g. ``[ok]``) as markup tags.

        Args:
            message: The message text.
            style: Rich style string (e.g., ``"bold green"``).
            prefix: Optional prefix tag like ``"[ok]"`` or ``"[error]"``.
        """
        text = Text()
        if not self._color_enabled or not style:
            if prefix:
                text.append(f"{prefix} ")
            text.append(message)
        else:
            if prefix:
                text.append(f"{prefix} ", style=style)
            text.append(message, style=style)
        self._console.print(text)

    def _format_styled(self, message: str, style: str, prefix: str = "") -> str:
        """Return a message formatted with Rich markup.

        When colors are disabled or the style is empty, returns plain text.

        Args:
            message: The message text.
            style: Rich style string.
            prefix: Optional prefix tag.

        Returns:
            Formatted string.
        """
        if not self._color_enabled or not style:
            return f"{prefix} {message}" if prefix else message

        if prefix:
            return f"[{style}]{prefix} {message}[/{style}]"
        return f"[{style}]{message}[/{style}]"


def get_formatter(
    theme: str | None = None,
    no_color: bool = False,
    console: Console | None = None,
) -> OutputFormatter:
    """Factory function to create a configured OutputFormatter.

    This is the primary entry point for obtaining a formatter instance.
    It resolves the theme from the provided argument, the ``MCPBR_THEME``
    environment variable, or the default theme. It also respects the
    ``NO_COLOR`` environment variable and the ``no_color`` parameter.

    Args:
        theme: Theme name (``"default"``, ``"minimal"``, or ``"plain"``).
            Falls back to the ``MCPBR_THEME`` environment variable, then
            ``"default"``.
        no_color: If ``True``, forces color off regardless of other settings.
        console: Optional Rich Console instance to use.

    Returns:
        A configured ``OutputFormatter`` instance.

    Raises:
        ValueError: If the theme name is not recognized.
    """
    resolved_theme = _resolve_theme(theme)
    force_color: bool | None = None
    if no_color:
        force_color = False

    return OutputFormatter(theme=resolved_theme, force_color=force_color, console=console)
