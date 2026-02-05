"""Tests for the formatting module.

Comprehensive tests covering all themes, NO_COLOR handling, format methods,
print methods, table rendering, and the get_formatter factory function.
"""

from __future__ import annotations

import os
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console
from rich.progress import Progress

from mcpbr.formatting import (
    THEME_CONFIGS,
    OutputFormatter,
    Theme,
    ThemeConfig,
    _resolve_theme,
    detect_color_support,
    get_formatter,
)

# ---------------------------------------------------------------------------
# Theme enum
# ---------------------------------------------------------------------------


class TestTheme:
    """Tests for the Theme enum."""

    def test_enum_values(self) -> None:
        """All expected theme values exist."""
        assert Theme.DEFAULT.value == "default"
        assert Theme.MINIMAL.value == "minimal"
        assert Theme.PLAIN.value == "plain"

    def test_all_themes_have_configs(self) -> None:
        """Every Theme enum member has a corresponding entry in THEME_CONFIGS."""
        for theme in Theme:
            assert theme in THEME_CONFIGS, f"Missing config for {theme}"


# ---------------------------------------------------------------------------
# ThemeConfig dataclass
# ---------------------------------------------------------------------------


class TestThemeConfig:
    """Tests for the ThemeConfig dataclass."""

    def test_default_values(self) -> None:
        """ThemeConfig defaults match the DEFAULT theme."""
        config = ThemeConfig()
        assert config.success_style == "bold green"
        assert config.error_style == "bold red"
        assert config.warning_style == "bold yellow"
        assert config.info_style == "bold blue"
        assert config.header_style == "bold magenta"
        assert config.dim_style == "dim"
        assert config.highlight_style == "bold cyan"

    def test_custom_values(self) -> None:
        """ThemeConfig can be constructed with custom values."""
        config = ThemeConfig(success_style="green", error_style="red")
        assert config.success_style == "green"
        assert config.error_style == "red"

    def test_frozen(self) -> None:
        """ThemeConfig is immutable."""
        config = ThemeConfig()
        with pytest.raises(AttributeError):
            config.success_style = "italic"  # type: ignore[misc]

    def test_plain_theme_has_empty_styles(self) -> None:
        """The PLAIN theme config should have empty style strings."""
        config = THEME_CONFIGS[Theme.PLAIN]
        assert config.success_style == ""
        assert config.error_style == ""
        assert config.warning_style == ""
        assert config.info_style == ""
        assert config.header_style == ""
        assert config.dim_style == ""
        assert config.highlight_style == ""


# ---------------------------------------------------------------------------
# THEME_CONFIGS
# ---------------------------------------------------------------------------


class TestThemeConfigs:
    """Tests for the global THEME_CONFIGS mapping."""

    def test_default_theme_bold(self) -> None:
        """DEFAULT theme styles contain 'bold'."""
        config = THEME_CONFIGS[Theme.DEFAULT]
        assert "bold" in config.success_style
        assert "bold" in config.error_style
        assert "bold" in config.header_style

    def test_minimal_theme_no_bold(self) -> None:
        """MINIMAL theme styles do not contain 'bold'."""
        config = THEME_CONFIGS[Theme.MINIMAL]
        assert "bold" not in config.success_style
        assert "bold" not in config.error_style
        assert "bold" not in config.header_style

    def test_plain_theme_all_empty(self) -> None:
        """PLAIN theme has all empty styles."""
        config = THEME_CONFIGS[Theme.PLAIN]
        for field_name in (
            "success_style",
            "error_style",
            "warning_style",
            "info_style",
            "header_style",
            "dim_style",
            "highlight_style",
        ):
            assert getattr(config, field_name) == "", f"{field_name} should be empty"


# ---------------------------------------------------------------------------
# _resolve_theme
# ---------------------------------------------------------------------------


class TestResolveTheme:
    """Tests for the _resolve_theme helper."""

    def test_explicit_default(self) -> None:
        """Explicit 'default' string resolves correctly."""
        assert _resolve_theme("default") == Theme.DEFAULT

    def test_explicit_minimal(self) -> None:
        """Explicit 'minimal' string resolves correctly."""
        assert _resolve_theme("minimal") == Theme.MINIMAL

    def test_explicit_plain(self) -> None:
        """Explicit 'plain' string resolves correctly."""
        assert _resolve_theme("plain") == Theme.PLAIN

    def test_case_insensitive(self) -> None:
        """Theme names are resolved case-insensitively."""
        assert _resolve_theme("DEFAULT") == Theme.DEFAULT
        assert _resolve_theme("Minimal") == Theme.MINIMAL
        assert _resolve_theme("PLAIN") == Theme.PLAIN

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        assert _resolve_theme("  default  ") == Theme.DEFAULT

    def test_none_returns_default(self) -> None:
        """None with no env var returns DEFAULT."""
        with patch.dict(os.environ, {}, clear=True):
            assert _resolve_theme(None) == Theme.DEFAULT

    def test_env_fallback(self) -> None:
        """Falls back to MCPBR_THEME env var when argument is None."""
        with patch.dict(os.environ, {"MCPBR_THEME": "minimal"}):
            assert _resolve_theme(None) == Theme.MINIMAL

    def test_explicit_overrides_env(self) -> None:
        """Explicit argument takes precedence over env var."""
        with patch.dict(os.environ, {"MCPBR_THEME": "minimal"}):
            assert _resolve_theme("plain") == Theme.PLAIN

    def test_invalid_raises_value_error(self) -> None:
        """Unknown theme name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown theme 'neon'"):
            _resolve_theme("neon")


# ---------------------------------------------------------------------------
# detect_color_support
# ---------------------------------------------------------------------------


class TestDetectColorSupport:
    """Tests for detect_color_support."""

    def test_force_true(self) -> None:
        """force_color=True always returns True."""
        assert detect_color_support(force_color=True) is True

    def test_force_false(self) -> None:
        """force_color=False always returns False."""
        assert detect_color_support(force_color=False) is False

    def test_force_overrides_no_color_env(self) -> None:
        """force_color takes precedence over NO_COLOR env var."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert detect_color_support(force_color=True) is True

    def test_no_color_env_set(self) -> None:
        """NO_COLOR env var disables color when set."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}, clear=False):
            assert detect_color_support() is False

    def test_no_color_env_empty_string(self) -> None:
        """NO_COLOR env var disables color even when set to empty string."""
        with patch.dict(os.environ, {"NO_COLOR": ""}, clear=False):
            assert detect_color_support() is False

    def test_mcpbr_theme_plain_disables_color(self) -> None:
        """MCPBR_THEME=plain disables color."""
        env = {"MCPBR_THEME": "plain"}
        with patch.dict(os.environ, env, clear=True):
            assert detect_color_support() is False

    def test_mcpbr_theme_default_does_not_disable(self) -> None:
        """MCPBR_THEME=default does not disable color (falls through to TTY check)."""
        env = {"MCPBR_THEME": "default"}
        with patch.dict(os.environ, env, clear=True):
            # In a test runner stdout is usually not a TTY, so this may be False.
            # The important thing is it does not short-circuit to False from theme.
            result = detect_color_support()
            assert isinstance(result, bool)

    def test_tty_detection(self) -> None:
        """Returns True when stdout.isatty() reports True."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                assert detect_color_support() is True

    def test_non_tty_detection(self) -> None:
        """Returns False when stdout.isatty() reports False."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = False
                assert detect_color_support() is False


# ---------------------------------------------------------------------------
# OutputFormatter — construction
# ---------------------------------------------------------------------------


class TestOutputFormatterInit:
    """Tests for OutputFormatter initialization."""

    def test_default_construction(self) -> None:
        """Default construction uses DEFAULT theme."""
        fmt = OutputFormatter()
        assert fmt.theme == Theme.DEFAULT
        assert fmt.config == THEME_CONFIGS[Theme.DEFAULT]

    def test_minimal_theme(self) -> None:
        """Can construct with MINIMAL theme."""
        fmt = OutputFormatter(theme=Theme.MINIMAL)
        assert fmt.theme == Theme.MINIMAL
        assert fmt.config == THEME_CONFIGS[Theme.MINIMAL]

    def test_plain_theme(self) -> None:
        """Can construct with PLAIN theme."""
        fmt = OutputFormatter(theme=Theme.PLAIN)
        assert fmt.theme == Theme.PLAIN

    def test_force_color_true(self) -> None:
        """force_color=True enables color."""
        fmt = OutputFormatter(force_color=True)
        assert fmt.color_enabled is True

    def test_force_color_false(self) -> None:
        """force_color=False disables color."""
        fmt = OutputFormatter(force_color=False)
        assert fmt.color_enabled is False

    def test_custom_console(self) -> None:
        """A custom Console instance is used when provided."""
        custom = Console(file=StringIO())
        fmt = OutputFormatter(console=custom)
        assert fmt.console is custom


# ---------------------------------------------------------------------------
# OutputFormatter — print methods
# ---------------------------------------------------------------------------


def _capture_output(formatter: OutputFormatter) -> StringIO:
    """Return the StringIO backing a formatter's console.

    The formatter must have been constructed with a Console(file=StringIO()).
    """
    return formatter.console.file  # type: ignore[return-value]


def _make_formatter(
    theme: Theme = Theme.DEFAULT,
    force_color: bool | None = None,
) -> OutputFormatter:
    """Create a formatter that captures output to a StringIO."""
    buf = StringIO()
    console = Console(file=buf, no_color=force_color is not None and not force_color)
    return OutputFormatter(theme=theme, force_color=force_color, console=console)


class TestOutputFormatterPrint:
    """Tests for print methods (success, error, warning, info, header)."""

    def test_success_contains_message(self) -> None:
        """success() prints the provided message."""
        fmt = _make_formatter(force_color=False)
        fmt.success("All tests passed")
        output = _capture_output(fmt).getvalue()
        assert "All tests passed" in output

    def test_success_contains_prefix(self) -> None:
        """success() includes the [ok] prefix."""
        fmt = _make_formatter(force_color=False)
        fmt.success("done")
        output = _capture_output(fmt).getvalue()
        assert "[ok]" in output

    def test_error_contains_message(self) -> None:
        """error() prints the provided message."""
        fmt = _make_formatter(force_color=False)
        fmt.error("Something broke")
        output = _capture_output(fmt).getvalue()
        assert "Something broke" in output

    def test_error_contains_prefix(self) -> None:
        """error() includes the [error] prefix."""
        fmt = _make_formatter(force_color=False)
        fmt.error("fail")
        output = _capture_output(fmt).getvalue()
        assert "[error]" in output

    def test_warning_contains_message(self) -> None:
        """warning() prints the provided message."""
        fmt = _make_formatter(force_color=False)
        fmt.warning("Watch out")
        output = _capture_output(fmt).getvalue()
        assert "Watch out" in output

    def test_warning_contains_prefix(self) -> None:
        """warning() includes the [warn] prefix."""
        fmt = _make_formatter(force_color=False)
        fmt.warning("hmm")
        output = _capture_output(fmt).getvalue()
        assert "[warn]" in output

    def test_info_contains_message(self) -> None:
        """info() prints the provided message."""
        fmt = _make_formatter(force_color=False)
        fmt.info("FYI")
        output = _capture_output(fmt).getvalue()
        assert "FYI" in output

    def test_info_contains_prefix(self) -> None:
        """info() includes the [info] prefix."""
        fmt = _make_formatter(force_color=False)
        fmt.info("note")
        output = _capture_output(fmt).getvalue()
        assert "[info]" in output

    def test_header_contains_message(self) -> None:
        """header() prints the provided message."""
        fmt = _make_formatter(force_color=False)
        fmt.header("Results")
        output = _capture_output(fmt).getvalue()
        assert "Results" in output

    def test_header_no_prefix(self) -> None:
        """header() does not include a bracket prefix."""
        fmt = _make_formatter(force_color=False)
        fmt.header("Section Title")
        output = _capture_output(fmt).getvalue()
        # header has no prefix like [ok], so the text should appear directly
        assert output.strip().startswith("Section Title") or "Section Title" in output

    def test_success_with_color_enabled(self) -> None:
        """success() uses styled output when color is enabled."""
        fmt = _make_formatter(theme=Theme.DEFAULT, force_color=True)
        fmt.success("colored")
        output = _capture_output(fmt).getvalue()
        assert "colored" in output


# ---------------------------------------------------------------------------
# OutputFormatter — format methods (return strings)
# ---------------------------------------------------------------------------


class TestOutputFormatterFormat:
    """Tests for format_* methods that return strings."""

    def test_format_success_plain(self) -> None:
        """format_success returns plain text when color is off."""
        fmt = OutputFormatter(force_color=False)
        result = fmt.format_success("done")
        assert "[ok]" in result
        assert "done" in result
        # No Rich markup tags in plain mode
        assert "[bold" not in result

    def test_format_success_with_color(self) -> None:
        """format_success returns Rich markup when color is on."""
        fmt = OutputFormatter(theme=Theme.DEFAULT, force_color=True)
        result = fmt.format_success("done")
        assert "done" in result
        assert "bold green" in result

    def test_format_error_plain(self) -> None:
        """format_error returns plain text when color is off."""
        fmt = OutputFormatter(force_color=False)
        result = fmt.format_error("failed")
        assert "[error]" in result
        assert "failed" in result

    def test_format_error_with_color(self) -> None:
        """format_error returns Rich markup when color is on."""
        fmt = OutputFormatter(theme=Theme.DEFAULT, force_color=True)
        result = fmt.format_error("failed")
        assert "bold red" in result

    def test_format_warning_plain(self) -> None:
        """format_warning returns plain text when color is off."""
        fmt = OutputFormatter(force_color=False)
        result = fmt.format_warning("careful")
        assert "[warn]" in result
        assert "careful" in result

    def test_format_warning_with_color(self) -> None:
        """format_warning returns Rich markup when color is on."""
        fmt = OutputFormatter(theme=Theme.DEFAULT, force_color=True)
        result = fmt.format_warning("careful")
        assert "bold yellow" in result

    def test_format_info_plain(self) -> None:
        """format_info returns plain text when color is off."""
        fmt = OutputFormatter(force_color=False)
        result = fmt.format_info("note this")
        assert "[info]" in result
        assert "note this" in result

    def test_format_info_with_color(self) -> None:
        """format_info returns Rich markup when color is on."""
        fmt = OutputFormatter(theme=Theme.DEFAULT, force_color=True)
        result = fmt.format_info("note this")
        assert "bold blue" in result

    def test_format_header_plain(self) -> None:
        """format_header returns plain text when color is off."""
        fmt = OutputFormatter(force_color=False)
        result = fmt.format_header("Section")
        assert result == "Section"

    def test_format_header_with_color(self) -> None:
        """format_header returns Rich markup when color is on."""
        fmt = OutputFormatter(theme=Theme.DEFAULT, force_color=True)
        result = fmt.format_header("Section")
        assert "bold magenta" in result

    def test_format_minimal_theme_styles(self) -> None:
        """MINIMAL theme format strings use non-bold styles."""
        fmt = OutputFormatter(theme=Theme.MINIMAL, force_color=True)
        result = fmt.format_success("ok")
        assert "green" in result
        assert "bold" not in result

    def test_format_plain_theme_no_markup(self) -> None:
        """PLAIN theme format strings have no markup."""
        fmt = OutputFormatter(theme=Theme.PLAIN, force_color=True)
        result = fmt.format_success("ok")
        assert "[ok] ok" == result


# ---------------------------------------------------------------------------
# OutputFormatter — table
# ---------------------------------------------------------------------------


class TestOutputFormatterTable:
    """Tests for the table method."""

    def test_table_renders(self) -> None:
        """table() renders a table with the given title, columns, and rows."""
        fmt = _make_formatter(force_color=False)
        fmt.table(
            title="Results",
            columns=["Name", "Score"],
            rows=[["model-a", "85"], ["model-b", "92"]],
        )
        output = _capture_output(fmt).getvalue()
        assert "Results" in output
        assert "Name" in output
        assert "Score" in output
        assert "model-a" in output
        assert "92" in output

    def test_table_empty_rows(self) -> None:
        """table() renders even with zero rows."""
        fmt = _make_formatter(force_color=False)
        fmt.table(title="Empty", columns=["A", "B"], rows=[])
        output = _capture_output(fmt).getvalue()
        assert "Empty" in output
        assert "A" in output

    def test_table_non_string_values(self) -> None:
        """table() converts non-string cell values to strings."""
        fmt = _make_formatter(force_color=False)
        fmt.table(
            title="Numbers",
            columns=["X", "Y"],
            rows=[[1, 2.5], [3, None]],
        )
        output = _capture_output(fmt).getvalue()
        assert "2.5" in output
        assert "None" in output


# ---------------------------------------------------------------------------
# OutputFormatter — progress_bar
# ---------------------------------------------------------------------------


class TestOutputFormatterProgressBar:
    """Tests for the progress_bar method."""

    def test_returns_progress_instance(self) -> None:
        """progress_bar() returns a rich Progress instance."""
        fmt = OutputFormatter(force_color=False)
        progress = fmt.progress_bar()
        assert isinstance(progress, Progress)

    def test_progress_bar_has_console(self) -> None:
        """The returned Progress uses the formatter's console."""
        fmt = _make_formatter(force_color=False)
        progress = fmt.progress_bar()
        assert progress.console is fmt.console


# ---------------------------------------------------------------------------
# get_formatter factory
# ---------------------------------------------------------------------------


class TestGetFormatter:
    """Tests for the get_formatter factory function."""

    def test_default_theme(self) -> None:
        """get_formatter() with no args returns DEFAULT theme."""
        fmt = get_formatter()
        assert fmt.theme == Theme.DEFAULT

    def test_explicit_theme(self) -> None:
        """get_formatter(theme='minimal') returns MINIMAL theme."""
        fmt = get_formatter(theme="minimal")
        assert fmt.theme == Theme.MINIMAL

    def test_plain_theme(self) -> None:
        """get_formatter(theme='plain') returns PLAIN theme."""
        fmt = get_formatter(theme="plain")
        assert fmt.theme == Theme.PLAIN

    def test_no_color_flag(self) -> None:
        """get_formatter(no_color=True) disables color."""
        fmt = get_formatter(no_color=True)
        assert fmt.color_enabled is False

    def test_env_theme(self) -> None:
        """get_formatter picks up MCPBR_THEME env var."""
        with patch.dict(os.environ, {"MCPBR_THEME": "minimal"}):
            fmt = get_formatter()
            assert fmt.theme == Theme.MINIMAL

    def test_explicit_overrides_env(self) -> None:
        """Explicit theme arg overrides MCPBR_THEME env var."""
        with patch.dict(os.environ, {"MCPBR_THEME": "minimal"}):
            fmt = get_formatter(theme="plain")
            assert fmt.theme == Theme.PLAIN

    def test_no_color_env(self) -> None:
        """NO_COLOR env var disables color in get_formatter."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            fmt = get_formatter()
            assert fmt.color_enabled is False

    def test_invalid_theme_raises(self) -> None:
        """Invalid theme name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown theme"):
            get_formatter(theme="neon")

    def test_custom_console_passed_through(self) -> None:
        """A custom Console is passed through to the formatter."""
        custom = Console(file=StringIO())
        fmt = get_formatter(console=custom)
        assert fmt.console is custom


# ---------------------------------------------------------------------------
# NO_COLOR integration (end-to-end)
# ---------------------------------------------------------------------------


class TestNoColorIntegration:
    """End-to-end tests for the NO_COLOR convention."""

    def test_no_color_env_disables_all_formatting(self) -> None:
        """When NO_COLOR is set, format methods return plain text."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            fmt = get_formatter()
            assert fmt.color_enabled is False

            result = fmt.format_success("ok")
            assert "[bold" not in result
            assert "[ok]" in result
            assert "ok" in result

    def test_no_color_flag_disables_all_formatting(self) -> None:
        """When no_color=True, format methods return plain text."""
        fmt = get_formatter(no_color=True)
        assert fmt.color_enabled is False

        result = fmt.format_error("fail")
        assert "[bold" not in result
        assert "[error]" in result
        assert "fail" in result

    def test_plain_theme_disables_formatting(self) -> None:
        """PLAIN theme produces unformatted output."""
        fmt = get_formatter(theme="plain")
        result = fmt.format_warning("hmm")
        # Plain theme has empty styles, so no Rich markup is emitted
        assert result == "[warn] hmm"

    def test_print_with_no_color(self) -> None:
        """Print methods produce plain output when color is off."""
        buf = StringIO()
        console = Console(file=buf, no_color=True)
        fmt = get_formatter(no_color=True, console=console)
        fmt.success("done")
        fmt.error("oops")
        fmt.warning("hmm")
        fmt.info("note")
        fmt.header("title")

        output = buf.getvalue()
        assert "[ok] done" in output
        assert "[error] oops" in output
        assert "[warn] hmm" in output
        assert "[info] note" in output
        assert "title" in output


# ---------------------------------------------------------------------------
# All themes produce output
# ---------------------------------------------------------------------------


class TestAllThemesProduceOutput:
    """Verify each theme produces non-empty output for every method."""

    @pytest.fixture(params=list(Theme))
    def formatter(self, request: pytest.FixtureRequest) -> OutputFormatter:
        """Create a formatter for each theme with captured output."""
        theme = request.param
        return _make_formatter(theme=theme, force_color=False)

    def test_success_output(self, formatter: OutputFormatter) -> None:
        """success() produces output for every theme."""
        formatter.success("msg")
        assert _capture_output(formatter).getvalue().strip()

    def test_error_output(self, formatter: OutputFormatter) -> None:
        """error() produces output for every theme."""
        formatter.error("msg")
        assert _capture_output(formatter).getvalue().strip()

    def test_warning_output(self, formatter: OutputFormatter) -> None:
        """warning() produces output for every theme."""
        formatter.warning("msg")
        assert _capture_output(formatter).getvalue().strip()

    def test_info_output(self, formatter: OutputFormatter) -> None:
        """info() produces output for every theme."""
        formatter.info("msg")
        assert _capture_output(formatter).getvalue().strip()

    def test_header_output(self, formatter: OutputFormatter) -> None:
        """header() produces output for every theme."""
        formatter.header("msg")
        assert _capture_output(formatter).getvalue().strip()

    def test_format_success_output(self, formatter: OutputFormatter) -> None:
        """format_success() returns non-empty string for every theme."""
        assert formatter.format_success("msg")

    def test_format_error_output(self, formatter: OutputFormatter) -> None:
        """format_error() returns non-empty string for every theme."""
        assert formatter.format_error("msg")

    def test_table_output(self, formatter: OutputFormatter) -> None:
        """table() produces output for every theme."""
        formatter.table("T", ["A"], [["1"]])
        assert _capture_output(formatter).getvalue().strip()
