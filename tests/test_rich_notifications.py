"""Tests for rich Slack notifications — enriched messages, file upload, Gist links."""

import json
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.notifications import (
    NotificationEvent,
    create_gist_report,
    send_slack_notification,
    upload_slack_file,
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
                    "total_calls": 30,
                    "successful_calls": 23,
                    "failed_calls": 7,
                    "failure_rate": 0.233,
                },
            }
        )
        send_slack_notification("https://hooks.slack.com/test", event)

        payload = mock_post.call_args[1]["json"]
        attachment = payload["attachments"][0]
        assert "text" in attachment
        assert "30" in attachment["text"]

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
# #396: Slack file upload
# ---------------------------------------------------------------------------


class TestSlackFileUpload:
    """Upload results.json to Slack via bot token."""

    @patch("mcpbr.notifications.requests.post")
    def test_uploads_file_content(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {"ok": True}

        upload_slack_file(
            bot_token="xoxb-test-token",
            channel="C12345",
            content=json.dumps(SAMPLE_RESULTS_DICT),
            filename="results.json",
            title="mcpbr results",
        )

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        # Should use files.upload endpoint or similar
        url = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("url", "")
        assert "slack.com" in url
        assert "files" in url

    @patch("mcpbr.notifications.requests.post")
    def test_includes_auth_header(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {"ok": True}

        upload_slack_file(
            bot_token="xoxb-test-token",
            channel="C12345",
            content="{}",
            filename="results.json",
        )

        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert "Bearer xoxb-test-token" in headers.get("Authorization", "")

    @patch("mcpbr.notifications.requests.post")
    def test_raises_on_slack_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {"ok": False, "error": "not_authed"}

        with pytest.raises(RuntimeError, match="not_authed"):
            upload_slack_file(
                bot_token="bad-token",
                channel="C12345",
                content="{}",
                filename="results.json",
            )


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
    """dispatch_notification passes extra data through."""

    @patch("mcpbr.notifications.send_slack_notification")
    def test_passes_results_dict_for_file_upload(self, mock_send):
        from mcpbr.notifications import dispatch_notification

        event = _make_event(extra={"results_json": '{"test": true}'})
        config = {"slack_webhook": "https://hooks.slack.com/test"}

        dispatch_notification(config, event)
        mock_send.assert_called_once()

    @patch("mcpbr.notifications.upload_slack_file")
    def test_uploads_file_when_bot_token_present(self, mock_upload):
        from mcpbr.notifications import dispatch_notification

        event = _make_event(extra={"results_json": '{"test": true}'})
        config = {
            "slack_webhook": "https://hooks.slack.com/test",
            "slack_bot_token": "xoxb-test",
            "slack_channel": "C12345",
        }

        with patch("mcpbr.notifications.send_slack_notification"):
            dispatch_notification(config, event)

        mock_upload.assert_called_once()
        call_kwargs = mock_upload.call_args[1]
        assert call_kwargs["bot_token"] == "xoxb-test"

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
        # Gist URL should be added to event before sending Slack
        sent_event = mock_send.call_args[0][1]
        assert sent_event.extra.get("gist_url") == "https://gist.github.com/user/abc123"
