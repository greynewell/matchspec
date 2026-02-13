"""Integration tests for harness notification dispatch points."""

import time
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.harness import (
    _build_notify_config,
    _describe_mcp_server,
    _dispatch_lifecycle_event,
    _ProgressTracker,
)

pytestmark = pytest.mark.integration


class TestBuildNotifyConfig:
    """Tests for _build_notify_config helper."""

    def test_returns_empty_when_no_channels(self) -> None:
        config = MagicMock(spec=[])
        result = _build_notify_config(config)
        assert result == {}

    def test_returns_slack_webhook(self) -> None:
        config = MagicMock()
        config.notify_slack_webhook = "https://hooks.slack.com/test"
        config.notify_discord_webhook = None
        config.notify_email = None
        config.slack_bot_token = None
        config.slack_channel = None
        config.github_token = None
        result = _build_notify_config(config)
        assert result["slack_webhook"] == "https://hooks.slack.com/test"

    def test_returns_multiple_keys(self) -> None:
        config = MagicMock()
        config.notify_slack_webhook = "https://hooks.slack.com/test"
        config.notify_discord_webhook = "https://discord.com/api/webhooks/test"
        config.notify_email = None
        config.slack_bot_token = "xoxb-token"
        config.slack_channel = "#evals"
        config.github_token = None
        result = _build_notify_config(config)
        assert result["slack_webhook"] == "https://hooks.slack.com/test"
        assert result["discord_webhook"] == "https://discord.com/api/webhooks/test"
        assert result["slack_bot_token"] == "xoxb-token"
        assert result["slack_channel"] == "#evals"


class TestDescribeMcpServer:
    """Tests for _describe_mcp_server helper."""

    def test_command_server(self) -> None:
        config = MagicMock()
        config.comparison_mode = False
        srv = MagicMock()
        srv.name = "test-server"
        srv.command = "npx"
        srv.args = ["-y", "@test/server"]
        config.mcp_server = srv
        result = _describe_mcp_server(config)
        assert "npx" in result
        assert "test-server" in result

    def test_server_without_command(self) -> None:
        config = MagicMock()
        config.comparison_mode = False
        srv = MagicMock()
        srv.name = "my-server"
        srv.command = None
        config.mcp_server = srv
        result = _describe_mcp_server(config)
        assert "my-server" in result

    def test_no_server(self) -> None:
        config = MagicMock()
        config.comparison_mode = False
        config.mcp_server = None
        result = _describe_mcp_server(config)
        assert result == "unknown"


class TestDispatchLifecycleEvent:
    """Tests for _dispatch_lifecycle_event helper."""

    @patch("mcpbr.notifications.dispatch_notification")
    def test_dispatches_event(self, mock_dispatch: MagicMock) -> None:
        notify_config = {"slack_webhook": "https://test"}
        config = MagicMock()
        config.benchmark = "swe-bench-verified"
        config.model = "claude-sonnet-4-5-20250929"
        _dispatch_lifecycle_event(notify_config, config, "eval_started", extra={"total_tasks": 10})
        mock_dispatch.assert_called_once()
        # First positional arg is notify_config dict, second is the event
        call_args = mock_dispatch.call_args
        event = call_args[0][1] if len(call_args[0]) > 1 else call_args[0][0]
        assert event.event_type == "eval_started"
        assert event.extra["total_tasks"] == 10

    @patch("mcpbr.notifications.dispatch_notification")
    def test_suppresses_exceptions(self, mock_dispatch: MagicMock) -> None:
        mock_dispatch.side_effect = RuntimeError("boom")
        notify_config = {"slack_webhook": "https://test"}
        config = MagicMock()
        config.benchmark = "swe-bench-verified"
        config.model = "claude-sonnet-4-5-20250929"
        # Should not raise
        _dispatch_lifecycle_event(notify_config, config, "eval_started", extra={})


class TestProgressTracker:
    """Tests for _ProgressTracker."""

    def test_disabled_when_zero(self) -> None:
        tracker = _ProgressTracker(task_interval=0, time_interval_minutes=0, start_time=time.time())
        assert not tracker.should_notify(5, time.time())

    def test_task_interval(self) -> None:
        now = time.time()
        tracker = _ProgressTracker(task_interval=5, time_interval_minutes=0, start_time=now)
        assert not tracker.should_notify(3, now)
        assert tracker.should_notify(5, now)
        tracker.mark_notified(5, now)
        assert not tracker.should_notify(7, now)
        assert tracker.should_notify(10, now)

    def test_time_interval(self) -> None:
        past = time.time() - 120  # 2 minutes ago
        tracker = _ProgressTracker(task_interval=0, time_interval_minutes=1, start_time=past)
        # last_notified_time is set to start_time (2 min ago), so should trigger
        assert tracker.should_notify(1, time.time())

    def test_no_notification_before_interval(self) -> None:
        now = time.time()
        tracker = _ProgressTracker(task_interval=0, time_interval_minutes=5, start_time=now)
        # Only 1 second has passed, should not trigger
        assert not tracker.should_notify(1, now + 1)
