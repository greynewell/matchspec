"""Tests for the general notifications module."""

from unittest.mock import MagicMock, patch

from mcpbr.notifications import (
    NotificationEvent,
    dispatch_notification,
    send_discord_notification,
    send_email_notification,
    send_slack_notification,
)


class TestNotificationEvent:
    """NotificationEvent dataclass."""

    def test_completion_event(self):
        event = NotificationEvent(
            event_type="completion",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=6,
            resolution_rate=0.6,
            total_cost=12.50,
            runtime_seconds=3600.0,
        )
        assert event.event_type == "completion"
        assert event.resolution_rate == 0.6

    def test_regression_event(self):
        event = NotificationEvent(
            event_type="regression",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=6,
            resolution_rate=0.6,
            regression_count=3,
            improvement_count=1,
        )
        assert event.event_type == "regression"
        assert event.regression_count == 3


class TestSlackNotification:
    """send_slack_notification POSTs correct payload."""

    @patch("mcpbr.notifications.requests.post")
    def test_posts_to_webhook(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = NotificationEvent(
            event_type="completion",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=8,
            resolution_rate=0.8,
        )
        send_slack_notification("https://hooks.slack.com/test", event)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "attachments" in payload
        assert payload["attachments"][0]["color"] == "good"

    @patch("mcpbr.notifications.requests.post")
    def test_low_resolution_shows_warning_color(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = NotificationEvent(
            event_type="completion",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=1,
            resolution_rate=0.1,
        )
        send_slack_notification("https://hooks.slack.com/test", event)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["attachments"][0]["color"] == "warning"


class TestDiscordNotification:
    """send_discord_notification POSTs correct embed."""

    @patch("mcpbr.notifications.requests.post")
    def test_posts_embed(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = NotificationEvent(
            event_type="completion",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=8,
            resolution_rate=0.8,
        )
        send_discord_notification("https://discord.com/api/webhooks/test", event)

        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "embeds" in payload
        # Green for good performance
        assert payload["embeds"][0]["color"] == 0x00FF00


class TestEmailNotification:
    """send_email_notification sends via SMTP."""

    @patch("mcpbr.notifications.smtplib.SMTP")
    def test_sends_email(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        event = NotificationEvent(
            event_type="completion",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=8,
            resolution_rate=0.8,
        )
        email_config = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "from_email": "test@example.com",
            "to_email": "admin@example.com",
        }
        send_email_notification(email_config, event)

        mock_smtp.send_message.assert_called_once()


class TestDispatchNotification:
    """dispatch_notification sends to all configured channels."""

    @patch("mcpbr.notifications.send_slack_notification")
    @patch("mcpbr.notifications.send_discord_notification")
    @patch("mcpbr.notifications.send_email_notification")
    def test_dispatches_to_all_channels(self, mock_email, mock_discord, mock_slack):
        event = NotificationEvent(
            event_type="completion",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=8,
            resolution_rate=0.8,
        )
        config = {
            "slack_webhook": "https://hooks.slack.com/test",
            "discord_webhook": "https://discord.com/api/webhooks/test",
            "email": {
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "from_email": "test@example.com",
                "to_email": "admin@example.com",
            },
        }
        dispatch_notification(config, event)

        mock_slack.assert_called_once()
        mock_discord.assert_called_once()
        mock_email.assert_called_once()

    @patch("mcpbr.notifications.send_slack_notification")
    def test_dispatches_slack_only(self, mock_slack):
        event = NotificationEvent(
            event_type="completion",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=8,
            resolution_rate=0.8,
        )
        config = {"slack_webhook": "https://hooks.slack.com/test"}
        dispatch_notification(config, event)

        mock_slack.assert_called_once()

    @patch("mcpbr.notifications.send_slack_notification")
    def test_failure_caught_and_logged(self, mock_slack):
        """Failures are caught and logged, never raise."""
        mock_slack.side_effect = Exception("network error")

        event = NotificationEvent(
            event_type="completion",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=8,
            resolution_rate=0.8,
        )
        config = {"slack_webhook": "https://hooks.slack.com/test"}

        # Should NOT raise
        dispatch_notification(config, event)

    def test_empty_config_does_nothing(self):
        event = NotificationEvent(
            event_type="completion",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            total_tasks=10,
            resolved_tasks=8,
            resolution_rate=0.8,
        )
        # Should not raise
        dispatch_notification({}, event)
