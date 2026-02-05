"""Tests for structured logging configuration."""

import json
import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mcpbr.logging_config import (
    HumanFormatter,
    LogContext,
    StructuredFormatter,
    get_logger,
    setup_logging,
)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self) -> None:
        """Test that get_logger returns a logging.Logger instance."""
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_uses_mcpbr_namespace(self) -> None:
        """Test that get_logger prefixes name with 'mcpbr.'."""
        logger = get_logger("evaluation")
        assert logger.name == "mcpbr.evaluation"

    def test_get_logger_different_names(self) -> None:
        """Test logger creation with different names."""
        logger_a = get_logger("alpha")
        logger_b = get_logger("beta")
        assert logger_a.name == "mcpbr.alpha"
        assert logger_b.name == "mcpbr.beta"
        assert logger_a is not logger_b

    def test_get_logger_consistent_instances(self) -> None:
        """Test that get_logger returns the same instance for the same name."""
        logger1 = get_logger("consistent")
        logger2 = get_logger("consistent")
        assert logger1 is logger2

    def test_get_logger_nested_name(self) -> None:
        """Test get_logger with dotted/nested names."""
        logger = get_logger("benchmarks.humaneval")
        assert logger.name == "mcpbr.benchmarks.humaneval"


class TestStructuredFormatter:
    """Tests for StructuredFormatter."""

    def test_format_produces_valid_json(self) -> None:
        """Test that formatter output is valid JSON."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="mcpbr.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "mcpbr.test"

    def test_format_includes_timestamp(self) -> None:
        """Test that formatted output includes a timestamp."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="mcpbr.test",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=1,
            msg="Timestamp check",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "timestamp" in data
        assert len(data["timestamp"]) > 0

    def test_format_includes_task_id(self) -> None:
        """Test that task_id is included when present on the record."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="mcpbr.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="With context",
            args=None,
            exc_info=None,
        )
        record.task_id = "django__django-12345"
        output = formatter.format(record)
        data = json.loads(output)
        assert data["task_id"] == "django__django-12345"

    def test_format_includes_benchmark(self) -> None:
        """Test that benchmark is included when present on the record."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="mcpbr.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Benchmark run",
            args=None,
            exc_info=None,
        )
        record.benchmark = "swebench"
        output = formatter.format(record)
        data = json.loads(output)
        assert data["benchmark"] == "swebench"

    def test_format_includes_exception_info(self) -> None:
        """Test that exception info is included when present."""
        formatter = StructuredFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="mcpbr.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=None,
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]
        assert "test error" in data["exception"]

    def test_format_without_optional_fields(self) -> None:
        """Test that optional fields are omitted when not present."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="mcpbr.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Plain message",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "task_id" not in data
        assert "benchmark" not in data
        assert "exception" not in data

    def test_format_all_log_levels(self) -> None:
        """Test formatting across all standard log levels."""
        formatter = StructuredFormatter()
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]
        for level, expected_name in levels:
            record = logging.LogRecord(
                name="mcpbr.test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg=f"Level {expected_name}",
                args=None,
                exc_info=None,
            )
            output = formatter.format(record)
            data = json.loads(output)
            assert data["level"] == expected_name


class TestHumanFormatter:
    """Tests for HumanFormatter."""

    def test_human_format_output(self) -> None:
        """Test that HumanFormatter produces human-readable output."""
        formatter = HumanFormatter()
        record = logging.LogRecord(
            name="mcpbr.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Human readable",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        assert "[INFO]" in output
        assert "mcpbr.test" in output
        assert "Human readable" in output

    def test_human_format_warning(self) -> None:
        """Test HumanFormatter with WARNING level."""
        formatter = HumanFormatter()
        record = logging.LogRecord(
            name="mcpbr.cli",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Something is wrong",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        assert "[WARNING]" in output
        assert "mcpbr.cli" in output


class TestSetupLogging:
    """Tests for setup_logging function."""

    def setup_method(self) -> None:
        """Reset the mcpbr root logger before each test."""
        mcpbr_logger = logging.getLogger("mcpbr")
        mcpbr_logger.handlers.clear()
        mcpbr_logger.setLevel(logging.WARNING)

    def teardown_method(self) -> None:
        """Clean up the mcpbr root logger after each test."""
        mcpbr_logger = logging.getLogger("mcpbr")
        mcpbr_logger.handlers.clear()
        mcpbr_logger.setLevel(logging.WARNING)

    def test_default_level_is_info(self) -> None:
        """Test that default log level is INFO."""
        setup_logging()
        mcpbr_logger = logging.getLogger("mcpbr")
        assert mcpbr_logger.level == logging.INFO

    def test_debug_mode_enables_debug_level(self) -> None:
        """Test that debug=True sets level to DEBUG."""
        setup_logging(debug=True)
        mcpbr_logger = logging.getLogger("mcpbr")
        assert mcpbr_logger.level == logging.DEBUG

    def test_quiet_mode_sets_warning_level(self) -> None:
        """Test that quiet=True suppresses below WARNING."""
        setup_logging(quiet=True)
        mcpbr_logger = logging.getLogger("mcpbr")
        assert mcpbr_logger.level == logging.WARNING

    def test_custom_level_string(self) -> None:
        """Test setting log level via string."""
        setup_logging(level="ERROR")
        mcpbr_logger = logging.getLogger("mcpbr")
        assert mcpbr_logger.level == logging.ERROR

    def test_structured_mode_uses_json_formatter(self) -> None:
        """Test that structured=True uses StructuredFormatter."""
        setup_logging(structured=True)
        mcpbr_logger = logging.getLogger("mcpbr")
        # Check that at least one handler uses StructuredFormatter
        has_structured = any(
            isinstance(h.formatter, StructuredFormatter) for h in mcpbr_logger.handlers
        )
        assert has_structured

    def test_non_structured_uses_human_formatter(self) -> None:
        """Test that structured=False uses HumanFormatter."""
        setup_logging(structured=False)
        mcpbr_logger = logging.getLogger("mcpbr")
        has_human = any(isinstance(h.formatter, HumanFormatter) for h in mcpbr_logger.handlers)
        assert has_human

    def test_log_file_output(self, tmp_path: Path) -> None:
        """Test that log_file parameter creates file handler."""
        log_file = tmp_path / "test.log"
        setup_logging(log_file=log_file)

        logger = get_logger("filetest")
        logger.info("File test message")

        # Flush handlers
        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text()
        assert "File test message" in content

    def test_log_file_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that log_file creates parent directories if needed."""
        log_file = tmp_path / "subdir" / "nested" / "test.log"
        setup_logging(log_file=log_file)

        logger = get_logger("nested")
        logger.info("Nested dir test")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        assert log_file.exists()

    def test_log_rotation_by_size(self, tmp_path: Path) -> None:
        """Test that log rotation is configured with max_bytes."""
        log_file = tmp_path / "rotate.log"
        # Use very small max_bytes to trigger rotation
        setup_logging(log_file=log_file, max_bytes=200, backup_count=3)

        mcpbr_logger = logging.getLogger("mcpbr")
        # Check that a RotatingFileHandler is present
        has_rotating = any(
            isinstance(h, logging.handlers.RotatingFileHandler) for h in mcpbr_logger.handlers
        )
        assert has_rotating

        # Check rotation parameters
        for handler in mcpbr_logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                assert handler.maxBytes == 200
                assert handler.backupCount == 3

    def test_env_var_override(self) -> None:
        """Test MCPBR_LOG_LEVEL env var overrides level parameter."""
        with patch.dict(os.environ, {"MCPBR_LOG_LEVEL": "DEBUG"}):
            setup_logging(level="ERROR")
            mcpbr_logger = logging.getLogger("mcpbr")
            assert mcpbr_logger.level == logging.DEBUG

    def test_env_var_not_set_uses_parameter(self) -> None:
        """Test that level parameter is used when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure the env var is not set
            os.environ.pop("MCPBR_LOG_LEVEL", None)
            setup_logging(level="WARNING")
            mcpbr_logger = logging.getLogger("mcpbr")
            assert mcpbr_logger.level == logging.WARNING

    def test_debug_overrides_level(self) -> None:
        """Test that debug=True overrides the level parameter."""
        setup_logging(level="ERROR", debug=True)
        mcpbr_logger = logging.getLogger("mcpbr")
        assert mcpbr_logger.level == logging.DEBUG

    def test_quiet_overrides_level(self) -> None:
        """Test that quiet=True overrides the level parameter."""
        setup_logging(level="DEBUG", quiet=True)
        mcpbr_logger = logging.getLogger("mcpbr")
        assert mcpbr_logger.level == logging.WARNING

    def test_console_handler_is_added(self) -> None:
        """Test that a console (stream) handler is always added."""
        setup_logging()
        mcpbr_logger = logging.getLogger("mcpbr")
        has_stream = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in mcpbr_logger.handlers
        )
        assert has_stream

    def test_structured_log_file(self, tmp_path: Path) -> None:
        """Test that structured mode writes JSON to log file."""
        log_file = tmp_path / "structured.log"
        setup_logging(log_file=log_file, structured=True)

        logger = get_logger("jsontest")
        logger.info("JSON file test")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        content = log_file.read_text().strip()
        # Each line should be valid JSON
        for line in content.splitlines():
            if line.strip():
                data = json.loads(line)
                assert "message" in data


class TestLogContext:
    """Tests for LogContext context manager."""

    def setup_method(self) -> None:
        """Reset the mcpbr root logger before each test."""
        mcpbr_logger = logging.getLogger("mcpbr")
        mcpbr_logger.handlers.clear()
        mcpbr_logger.setLevel(logging.WARNING)

    def teardown_method(self) -> None:
        """Clean up the mcpbr root logger after each test."""
        mcpbr_logger = logging.getLogger("mcpbr")
        mcpbr_logger.handlers.clear()
        mcpbr_logger.setLevel(logging.WARNING)

    def test_log_context_adds_fields(self, tmp_path: Path) -> None:
        """Test that LogContext adds context fields to log records."""
        log_file = tmp_path / "context.log"
        setup_logging(log_file=log_file, structured=True)

        logger = get_logger("ctx")

        with LogContext(logger, task_id="test-123", benchmark="swebench"):
            logger.info("Contextual message")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        content = log_file.read_text().strip()
        for line in content.splitlines():
            if line.strip():
                data = json.loads(line)
                if data["message"] == "Contextual message":
                    assert data["task_id"] == "test-123"
                    assert data["benchmark"] == "swebench"

    def test_log_context_removes_fields_on_exit(self, tmp_path: Path) -> None:
        """Test that LogContext removes fields after exiting context."""
        log_file = tmp_path / "context_exit.log"
        setup_logging(log_file=log_file, structured=True)

        logger = get_logger("ctx_exit")

        with LogContext(logger, task_id="inside-ctx"):
            logger.info("Inside context")

        logger.info("Outside context")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        content = log_file.read_text().strip()
        lines = [json.loads(line) for line in content.splitlines() if line.strip()]

        inside_lines = [entry for entry in lines if entry["message"] == "Inside context"]
        outside_lines = [entry for entry in lines if entry["message"] == "Outside context"]

        assert len(inside_lines) == 1
        assert inside_lines[0].get("task_id") == "inside-ctx"

        assert len(outside_lines) == 1
        assert "task_id" not in outside_lines[0]

    def test_log_context_with_multiple_fields(self, tmp_path: Path) -> None:
        """Test LogContext with multiple context fields."""
        log_file = tmp_path / "multi_ctx.log"
        setup_logging(log_file=log_file, structured=True)

        logger = get_logger("multi")

        with LogContext(logger, task_id="task-abc", benchmark="humaneval"):
            logger.info("Multi-field context")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        content = log_file.read_text().strip()
        for line in content.splitlines():
            if line.strip():
                data = json.loads(line)
                if data["message"] == "Multi-field context":
                    assert data["task_id"] == "task-abc"
                    assert data["benchmark"] == "humaneval"

    def test_log_context_exception_safety(self, tmp_path: Path) -> None:
        """Test that LogContext cleans up even when exception occurs."""
        log_file = tmp_path / "exc_ctx.log"
        setup_logging(log_file=log_file, structured=True)

        logger = get_logger("exc_safe")

        with pytest.raises(RuntimeError):
            with LogContext(logger, task_id="error-task"):
                logger.info("Before error")
                raise RuntimeError("test exception")

        # After exception, context should be cleaned up
        logger.info("After error")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        content = log_file.read_text().strip()
        lines = [json.loads(line) for line in content.splitlines() if line.strip()]

        after_lines = [entry for entry in lines if entry["message"] == "After error"]
        assert len(after_lines) == 1
        assert "task_id" not in after_lines[0]


class TestLogLevelConfiguration:
    """Tests for various log level configurations."""

    def setup_method(self) -> None:
        """Reset the mcpbr root logger before each test."""
        mcpbr_logger = logging.getLogger("mcpbr")
        mcpbr_logger.handlers.clear()
        mcpbr_logger.setLevel(logging.WARNING)

    def teardown_method(self) -> None:
        """Clean up the mcpbr root logger after each test."""
        mcpbr_logger = logging.getLogger("mcpbr")
        mcpbr_logger.handlers.clear()
        mcpbr_logger.setLevel(logging.WARNING)

    def test_debug_level_logs_debug_messages(self, tmp_path: Path) -> None:
        """Test that DEBUG level captures debug messages."""
        log_file = tmp_path / "debug.log"
        setup_logging(log_file=log_file, level="DEBUG")

        logger = get_logger("dbg")
        logger.debug("Debug message")
        logger.info("Info message")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        content = log_file.read_text()
        assert "Debug message" in content
        assert "Info message" in content

    def test_info_level_skips_debug(self, tmp_path: Path) -> None:
        """Test that INFO level skips debug messages."""
        log_file = tmp_path / "info.log"
        setup_logging(log_file=log_file, level="INFO")

        logger = get_logger("inf")
        logger.debug("Should be skipped")
        logger.info("Should be logged")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        content = log_file.read_text()
        assert "Should be skipped" not in content
        assert "Should be logged" in content

    def test_warning_level_skips_info(self, tmp_path: Path) -> None:
        """Test that WARNING level skips info and debug messages."""
        log_file = tmp_path / "warning.log"
        setup_logging(log_file=log_file, level="WARNING")

        logger = get_logger("warn")
        logger.debug("Debug skip")
        logger.info("Info skip")
        logger.warning("Warning logged")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        content = log_file.read_text()
        assert "Debug skip" not in content
        assert "Info skip" not in content
        assert "Warning logged" in content

    def test_error_level_skips_warning(self, tmp_path: Path) -> None:
        """Test that ERROR level skips warning and below."""
        log_file = tmp_path / "error.log"
        setup_logging(log_file=log_file, level="ERROR")

        logger = get_logger("err")
        logger.debug("Debug skip")
        logger.info("Info skip")
        logger.warning("Warning skip")
        logger.error("Error logged")

        mcpbr_logger = logging.getLogger("mcpbr")
        for handler in mcpbr_logger.handlers:
            handler.flush()

        content = log_file.read_text()
        assert "Debug skip" not in content
        assert "Info skip" not in content
        assert "Warning skip" not in content
        assert "Error logged" in content
