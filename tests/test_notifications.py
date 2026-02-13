"""Tests for the general notifications module."""

from unittest.mock import MagicMock, patch

from mcpbr.notifications import (
    LIFECYCLE_EVENT_TYPES,
    NotificationEvent,
    _format_lifecycle_discord_description,
    _format_lifecycle_email_body,
    _format_lifecycle_slack_text,
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

    @patch("mcpbr.notifications.send_slack_notification")
    @patch("mcpbr.notifications.create_gist_report")
    def test_lifecycle_event_skips_gist_creation(self, mock_gist, mock_slack):
        """Lifecycle events should not create Gists or post results."""
        event = NotificationEvent(
            event_type="eval_started",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            extra={"total_tasks": 10, "results_json": '{"test": true}'},
        )
        config = {
            "slack_webhook": "https://hooks.slack.com/test",
            "github_token": "ghp_fake",
        }
        dispatch_notification(config, event)

        mock_slack.assert_called_once()
        mock_gist.assert_not_called()


class TestEvalStartedEvent:
    """Tests for eval_started lifecycle event (#413)."""

    def test_event_creation(self):
        event = NotificationEvent(
            event_type="eval_started",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "total_tasks": 50,
                "max_concurrent": 4,
                "infrastructure_mode": "azure",
                "mcp_server": "my-server (npx my-server)",
            },
        )
        assert event.event_type == "eval_started"
        assert event.extra["total_tasks"] == 50
        assert event.extra["infrastructure_mode"] == "azure"

    def test_slack_format(self):
        event = NotificationEvent(
            event_type="eval_started",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "total_tasks": 50,
                "max_concurrent": 4,
                "infrastructure_mode": "local",
                "mcp_server": "test-server",
            },
        )
        text = _format_lifecycle_slack_text(event)
        assert "Eval Started" in text
        assert "swe-bench-verified" in text
        assert "50" in text
        assert "test-server" in text

    def test_discord_format(self):
        event = NotificationEvent(
            event_type="eval_started",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            extra={"total_tasks": 10, "max_concurrent": 2},
        )
        desc = _format_lifecycle_discord_description(event)
        assert "claude-sonnet-4-5-20250929" in desc
        assert "10" in desc

    def test_email_format(self):
        event = NotificationEvent(
            event_type="eval_started",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            extra={"total_tasks": 10, "infrastructure_mode": "azure"},
        )
        body = _format_lifecycle_email_body(event)
        assert "Eval Started" in body
        assert "azure" in body

    @patch("mcpbr.notifications.requests.post")
    def test_slack_webhook_lifecycle(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = NotificationEvent(
            event_type="eval_started",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            extra={"total_tasks": 10},
        )
        send_slack_notification("https://hooks.slack.com/test", event)

        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["attachments"][0]["color"] == "#439FE0"

    @patch("mcpbr.notifications.requests.post")
    def test_discord_webhook_lifecycle(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = NotificationEvent(
            event_type="eval_started",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            extra={"total_tasks": 10},
        )
        send_discord_notification("https://discord.com/api/webhooks/test", event)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["embeds"][0]["color"] == 0x439FE0

    @patch("mcpbr.notifications.smtplib.SMTP")
    def test_email_lifecycle(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        event = NotificationEvent(
            event_type="eval_started",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            extra={"total_tasks": 10},
        )
        email_config = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "from_email": "test@example.com",
            "to_email": "admin@example.com",
        }
        send_email_notification(email_config, event)
        mock_smtp.send_message.assert_called_once()


class TestInfraEvents:
    """Tests for infra_provisioned and infra_teardown events (#414)."""

    def test_infra_provisioned_slack_format(self):
        event = NotificationEvent(
            event_type="infra_provisioned",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "vm_name": "mcpbr-vm-001",
                "ip": "10.0.0.5",
                "region": "eastus",
                "provisioning_time": 120.5,
                "ssh_cmd": "ssh user@10.0.0.5",
            },
        )
        text = _format_lifecycle_slack_text(event)
        assert "Infrastructure Provisioned" in text
        assert "mcpbr-vm-001" in text
        assert "10.0.0.5" in text
        assert "ssh user@10.0.0.5" in text
        assert "120.5" in text

    def test_infra_teardown_slack_format(self):
        event = NotificationEvent(
            event_type="infra_teardown",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={"vm_name": "mcpbr-vm-001"},
        )
        text = _format_lifecycle_slack_text(event)
        assert "Teardown" in text
        assert "mcpbr-vm-001" in text

    def test_infra_provisioned_discord_format(self):
        event = NotificationEvent(
            event_type="infra_provisioned",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "vm_name": "mcpbr-vm-001",
                "ip": "10.0.0.5",
                "region": "eastus",
                "ssh_cmd": "ssh user@10.0.0.5",
            },
        )
        desc = _format_lifecycle_discord_description(event)
        assert "mcpbr-vm-001" in desc
        assert "ssh user@10.0.0.5" in desc

    def test_infra_provisioned_email_format(self):
        event = NotificationEvent(
            event_type="infra_provisioned",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "vm_name": "mcpbr-vm-001",
                "ip": "10.0.0.5",
                "ssh_cmd": "ssh user@10.0.0.5",
            },
        )
        body = _format_lifecycle_email_body(event)
        assert "Infrastructure Provisioned" in body
        assert "mcpbr-vm-001" in body
        assert "ssh user@10.0.0.5" in body

    @patch("mcpbr.notifications.requests.post")
    def test_infra_provisioned_sends_slack(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = NotificationEvent(
            event_type="infra_provisioned",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={"vm_name": "test-vm"},
        )
        send_slack_notification("https://hooks.slack.com/test", event)
        mock_post.assert_called_once()


class TestProgressEvent:
    """Tests for progress lifecycle event (#415)."""

    def test_progress_slack_format(self):
        event = NotificationEvent(
            event_type="progress",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "completed": 25,
                "total": 100,
                "elapsed_seconds": 1800.0,
                "estimated_remaining_seconds": 5400.0,
                "running_cost": 15.50,
            },
        )
        text = _format_lifecycle_slack_text(event)
        assert "Progress" in text
        assert "25/100" in text
        assert "30.0 min" in text
        assert "90.0 min remaining" in text
        assert "$15.50" in text

    def test_progress_discord_format(self):
        event = NotificationEvent(
            event_type="progress",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "completed": 25,
                "total": 100,
                "elapsed_seconds": 1800.0,
                "running_cost": 15.50,
            },
        )
        desc = _format_lifecycle_discord_description(event)
        assert "25/100" in desc
        assert "$15.50" in desc

    def test_progress_email_format(self):
        event = NotificationEvent(
            event_type="progress",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "completed": 25,
                "total": 100,
                "elapsed_seconds": 1800.0,
            },
        )
        body = _format_lifecycle_email_body(event)
        assert "Progress" in body
        assert "25/100" in body

    @patch("mcpbr.notifications.requests.post")
    def test_progress_sends_slack(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = NotificationEvent(
            event_type="progress",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            extra={"completed": 5, "total": 10},
        )
        send_slack_notification("https://hooks.slack.com/test", event)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["attachments"][0]["color"] == "#439FE0"


class TestFailureEvent:
    """Tests for failure lifecycle event (#416)."""

    def test_failure_slack_format(self):
        event = NotificationEvent(
            event_type="failure",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "error": "Docker daemon not responding",
                "completed_tasks": 15,
                "total_tasks": 50,
                "last_successful_task": "django__django-12345",
            },
        )
        text = _format_lifecycle_slack_text(event)
        assert "Failed" in text
        assert "Docker daemon not responding" in text
        assert "15/50" in text
        assert "django__django-12345" in text

    def test_failure_discord_format(self):
        event = NotificationEvent(
            event_type="failure",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "error": "OOM killed",
                "completed_tasks": 10,
                "total_tasks": 50,
            },
        )
        desc = _format_lifecycle_discord_description(event)
        assert "OOM killed" in desc
        assert "10/50" in desc

    def test_failure_email_format(self):
        event = NotificationEvent(
            event_type="failure",
            benchmark="swe-bench-verified",
            model="claude-sonnet-4-5-20250929",
            extra={
                "error": "API rate limit exceeded",
                "completed_tasks": 5,
                "total_tasks": 20,
                "last_successful_task": "astropy__astropy-001",
            },
        )
        body = _format_lifecycle_email_body(event)
        assert "Failed" in body
        assert "API rate limit exceeded" in body
        assert "astropy__astropy-001" in body

    @patch("mcpbr.notifications.requests.post")
    def test_failure_sends_slack_with_danger_color(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = NotificationEvent(
            event_type="failure",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            extra={"error": "crash"},
        )
        send_slack_notification("https://hooks.slack.com/test", event)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["attachments"][0]["color"] == "danger"

    @patch("mcpbr.notifications.requests.post")
    def test_failure_sends_discord_with_red_color(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = NotificationEvent(
            event_type="failure",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
            extra={"error": "crash"},
        )
        send_discord_notification("https://discord.com/api/webhooks/test", event)

        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["embeds"][0]["color"] == 0xFF0000


class TestLifecycleEventTypes:
    """Tests for LIFECYCLE_EVENT_TYPES constant."""

    def test_all_lifecycle_types_present(self):
        expected = {"eval_started", "progress", "failure", "infra_provisioned", "infra_teardown"}
        assert expected == LIFECYCLE_EVENT_TYPES

    def test_completion_is_not_lifecycle(self):
        assert "completion" not in LIFECYCLE_EVENT_TYPES

    def test_regression_is_not_lifecycle(self):
        assert "regression" not in LIFECYCLE_EVENT_TYPES

    def test_lifecycle_event_defaults(self):
        """Lifecycle events can be created with minimal fields."""
        event = NotificationEvent(
            event_type="eval_started",
            benchmark="humaneval",
            model="claude-sonnet-4-5-20250929",
        )
        assert event.total_tasks == 0
        assert event.resolved_tasks == 0
        assert event.resolution_rate == 0.0
