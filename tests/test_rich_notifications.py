"""Tests for rich Slack notifications — enriched messages, file upload, Gist links."""

import json
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.notifications import (
    NotificationEvent,
    create_gist_report,
    post_slack_thread_reply,
    send_slack_bot_notification,
    send_slack_notification,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_event(**overrides):
    defaults = {
        "event_type": "completion",
        "benchmark": "swe-bench-verified",
        "model": "claude-sonnet-4-20250514",
        "total_tasks": 10,
        "resolved_tasks": 3,
        "resolution_rate": 0.3,
        "total_cost": 5.42,
        "runtime_seconds": 300.0,
    }
    defaults.update(overrides)
    return NotificationEvent(**defaults)


SAMPLE_RESULTS_DICT = {
    "metadata": {
        "config": {"benchmark": "swe-bench-verified", "model": "claude-sonnet-4-20250514"}
    },
    "summary": {
        "mcp": {"rate": 0.3, "total": 10, "resolved": 3, "total_cost": 5.42},
    },
    "tasks": [
        {"instance_id": "astropy__astropy-12907", "mcp": {"resolved": False, "cost": 0.54}},
        {"instance_id": "django__django-16379", "mcp": {"resolved": True, "cost": 0.32}},
        {"instance_id": "sympy__sympy-24152", "mcp": {"resolved": True, "cost": 0.61}},
    ],
}


# ---------------------------------------------------------------------------
# #395: Enriched Slack message
# ---------------------------------------------------------------------------


class TestEnrichedSlackMessage:
    """Slack notification includes per-task results and tool stats."""

    @patch("mcpbr.notifications.requests.post")
    def test_includes_per_task_results(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = _make_event(
            extra={
                "task_results": [
                    {"instance_id": "task-1", "resolved": True},
                    {"instance_id": "task-2", "resolved": False},
                ],
            }
        )
        send_slack_notification("https://hooks.slack.com/test", event)

        payload = mock_post.call_args[1]["json"]
        attachment = payload["attachments"][0]
        # Should have a text block with per-task results
        assert "text" in attachment
        assert "task-1" in attachment["text"]
        assert "task-2" in attachment["text"]

    @patch("mcpbr.notifications.requests.post")
    def test_includes_tool_stats(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = _make_event(
            extra={
                "tool_stats": {
                    "total_tool_calls": 30,
                    "total_failures": 7,
                    "failure_rate": 0.233,
                },
            }
        )
        send_slack_notification("https://hooks.slack.com/test", event)

        payload = mock_post.call_args[1]["json"]
        attachment = payload["attachments"][0]
        assert "text" in attachment
        assert "30" in attachment["text"]
        assert "23 ok" in attachment["text"]
        assert "7 failed" in attachment["text"]

    @patch("mcpbr.notifications.requests.post")
    def test_includes_gist_url(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = _make_event(extra={"gist_url": "https://gist.github.com/user/abc123"})
        send_slack_notification("https://hooks.slack.com/test", event)

        payload = mock_post.call_args[1]["json"]
        attachment = payload["attachments"][0]
        assert "text" in attachment
        assert "https://gist.github.com/user/abc123" in attachment["text"]

    @patch("mcpbr.notifications.requests.post")
    def test_includes_mcp_server_info(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = _make_event(
            extra={
                "mcp_server": "supermodel (npx -y @supermodeltools/mcp-server@0.9.0 {workdir})",
            }
        )
        send_slack_notification("https://hooks.slack.com/test", event)

        payload = mock_post.call_args[1]["json"]
        attachment = payload["attachments"][0]
        assert "text" in attachment
        assert "supermodel" in attachment["text"]
        assert "mcp-server@0.9.0" in attachment["text"]

    @patch("mcpbr.notifications.requests.post")
    def test_no_extra_omits_text_block(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        event = _make_event()
        send_slack_notification("https://hooks.slack.com/test", event)

        payload = mock_post.call_args[1]["json"]
        attachment = payload["attachments"][0]
        # No extra data means no text block
        assert "text" not in attachment or attachment["text"] == ""


# ---------------------------------------------------------------------------
# #396: Slack bot notification + threaded reply
# ---------------------------------------------------------------------------


class TestSlackBotNotification:
    """Send notification via bot API and post results as threaded reply."""

    @patch("slack_sdk.WebClient")
    def test_sends_message_and_returns_ts(self, mock_webclient_cls):
        mock_client = MagicMock()
        mock_webclient_cls.return_value = mock_client
        mock_client.chat_postMessage.return_value = {"ok": True, "ts": "1234.5678"}

        event = _make_event(extra={"mcp_server": "supermodel (npx mcp-server)"})
        ts = send_slack_bot_notification("xoxb-test", "C12345", event)

        assert ts == "1234.5678"
        mock_webclient_cls.assert_called_once_with(token="xoxb-test")
        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "C12345"
        assert "swe-bench-verified" in call_kwargs["text"]

    @patch("slack_sdk.WebClient")
    def test_message_includes_enriched_text(self, mock_webclient_cls):
        mock_client = MagicMock()
        mock_webclient_cls.return_value = mock_client
        mock_client.chat_postMessage.return_value = {"ok": True, "ts": "1234.5678"}

        event = _make_event(
            extra={
                "mcp_server": "supermodel",
                "task_results": [{"instance_id": "task-1", "resolved": True}],
                "tool_stats": {"total_tool_calls": 30, "total_failures": 7, "failure_rate": 0.233},
            }
        )
        send_slack_bot_notification("xoxb-test", "C12345", event)

        text = mock_client.chat_postMessage.call_args[1]["text"]
        assert "supermodel" in text
        assert "task-1" in text
        assert "30" in text

    @patch("slack_sdk.WebClient")
    def test_raises_on_error(self, mock_webclient_cls):
        mock_client = MagicMock()
        mock_webclient_cls.return_value = mock_client
        from slack_sdk.errors import SlackApiError

        mock_client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found", response=MagicMock()
        )

        with pytest.raises(SlackApiError):
            send_slack_bot_notification("xoxb-test", "C12345", _make_event())


class TestSlackThreadReply:
    """Upload results JSON as a file snippet in a Slack thread."""

    @patch("slack_sdk.WebClient")
    def test_uploads_snippet_in_thread(self, mock_webclient_cls):
        mock_client = MagicMock()
        mock_webclient_cls.return_value = mock_client

        post_slack_thread_reply("xoxb-test", "C12345", "1234.5678", '{"test": true}')

        mock_webclient_cls.assert_called_once_with(token="xoxb-test")
        mock_client.files_upload_v2.assert_called_once_with(
            channel="C12345",
            thread_ts="1234.5678",
            content='{"test": true}',
            filename="results.json",
            title="Evaluation Results",
            snippet_type="json",
        )

    @patch("slack_sdk.WebClient")
    def test_raises_on_error(self, mock_webclient_cls):
        mock_client = MagicMock()
        mock_webclient_cls.return_value = mock_client
        mock_client.files_upload_v2.side_effect = Exception("not_authed")

        with pytest.raises(Exception, match="not_authed"):
            post_slack_thread_reply("xoxb-bad", "C12345", "1234.5678", "{}")


# ---------------------------------------------------------------------------
# #397: GitHub Gist creation
# ---------------------------------------------------------------------------


class TestGistCreation:
    """Create a GitHub Gist with full report and return URL."""

    @patch("mcpbr.notifications.requests.post")
    def test_creates_gist_with_results(self, mock_post):
        mock_post.return_value = MagicMock(status_code=201)
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "html_url": "https://gist.github.com/user/abc123"
        }

        url = create_gist_report(
            github_token="ghp_test",
            results_json=json.dumps(SAMPLE_RESULTS_DICT),
            description="mcpbr swe-bench-verified results",
        )

        assert url == "https://gist.github.com/user/abc123"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "gist" in call_kwargs[0][0]
        payload = call_kwargs[1]["json"]
        assert "results.json" in payload["files"]

    @patch("mcpbr.notifications.requests.post")
    def test_gist_includes_auth_header(self, mock_post):
        mock_post.return_value = MagicMock(status_code=201)
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "html_url": "https://gist.github.com/user/abc123"
        }

        create_gist_report(
            github_token="ghp_test",
            results_json="{}",
            description="test",
        )

        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert "token ghp_test" in headers.get("Authorization", "")

    @patch("mcpbr.notifications.requests.post")
    def test_gist_returns_none_on_failure(self, mock_post):
        mock_post.side_effect = Exception("network error")

        url = create_gist_report(
            github_token="ghp_test",
            results_json="{}",
            description="test",
        )

        assert url is None


# ---------------------------------------------------------------------------
# dispatch_notification wiring
# ---------------------------------------------------------------------------


class TestDispatchWithExtras:
    """dispatch_notification wires bot notification + threaded reply."""

    @patch("mcpbr.notifications.send_slack_notification")
    def test_falls_back_to_webhook_without_bot_token(self, mock_send):
        from mcpbr.notifications import dispatch_notification

        event = _make_event(extra={"results_json": '{"test": true}'})
        config = {"slack_webhook": "https://hooks.slack.com/test"}

        dispatch_notification(config, event)
        mock_send.assert_called_once()

    @patch("mcpbr.notifications.post_slack_thread_reply")
    @patch("mcpbr.notifications.send_slack_bot_notification")
    def test_bot_sends_notification_and_thread_reply(self, mock_bot, mock_reply):
        from mcpbr.notifications import dispatch_notification

        mock_bot.return_value = "1234.5678"

        event = _make_event(extra={"results_json": '{"test": true}'})
        config = {
            "slack_bot_token": "xoxb-test",
            "slack_channel": "C12345",
        }

        dispatch_notification(config, event)

        mock_bot.assert_called_once()
        mock_reply.assert_called_once()
        call_kwargs = mock_reply.call_args[1]
        assert call_kwargs["thread_ts"] == "1234.5678"
        assert call_kwargs["content"] == '{"test": true}'

    @patch("mcpbr.notifications.post_slack_thread_reply")
    @patch("mcpbr.notifications.send_slack_bot_notification")
    def test_skips_thread_reply_without_results_json(self, mock_bot, mock_reply):
        from mcpbr.notifications import dispatch_notification

        mock_bot.return_value = "1234.5678"

        event = _make_event()
        config = {
            "slack_bot_token": "xoxb-test",
            "slack_channel": "C12345",
        }

        dispatch_notification(config, event)

        mock_bot.assert_called_once()
        mock_reply.assert_not_called()

    @patch("mcpbr.notifications.send_slack_bot_notification")
    @patch("mcpbr.notifications.send_slack_notification")
    def test_bot_takes_priority_over_webhook(self, mock_webhook, mock_bot):
        from mcpbr.notifications import dispatch_notification

        mock_bot.return_value = "1234.5678"

        event = _make_event()
        config = {
            "slack_webhook": "https://hooks.slack.com/test",
            "slack_bot_token": "xoxb-test",
            "slack_channel": "C12345",
        }

        dispatch_notification(config, event)

        mock_bot.assert_called_once()
        mock_webhook.assert_not_called()

    @patch("mcpbr.notifications.create_gist_report")
    @patch("mcpbr.notifications.send_slack_notification")
    def test_creates_gist_and_adds_url_to_event(self, mock_send, mock_gist):
        from mcpbr.notifications import dispatch_notification

        mock_gist.return_value = "https://gist.github.com/user/abc123"

        event = _make_event(extra={"results_json": '{"test": true}'})
        config = {
            "slack_webhook": "https://hooks.slack.com/test",
            "github_token": "ghp_test",
        }

        dispatch_notification(config, event)

        mock_gist.assert_called_once()
        sent_event = mock_send.call_args[0][1]
        assert sent_event.extra.get("gist_url") == "https://gist.github.com/user/abc123"

    @patch("mcpbr.notifications.post_slack_thread_reply")
    @patch("mcpbr.notifications.send_slack_bot_notification")
    def test_thread_reply_failure_is_caught(self, mock_bot, mock_reply):
        from mcpbr.notifications import dispatch_notification

        mock_bot.return_value = "1234.5678"
        mock_reply.side_effect = Exception("upload failed")

        event = _make_event(extra={"results_json": '{"test": true}'})
        config = {
            "slack_bot_token": "xoxb-test",
            "slack_channel": "C12345",
        }

        # Should not raise — failures are caught and logged
        dispatch_notification(config, event)

        mock_bot.assert_called_once()
        mock_reply.assert_called_once()

    @patch("mcpbr.notifications.send_slack_notification")
    @patch("mcpbr.notifications.send_slack_bot_notification")
    def test_falls_back_to_webhook_on_bot_failure(self, mock_bot, mock_webhook):
        from mcpbr.notifications import dispatch_notification

        mock_bot.side_effect = Exception("invalid token")

        event = _make_event()
        config = {
            "slack_webhook": "https://hooks.slack.com/test",
            "slack_bot_token": "xoxb-bad",
            "slack_channel": "C12345",
        }

        dispatch_notification(config, event)

        mock_bot.assert_called_once()
        mock_webhook.assert_called_once()
