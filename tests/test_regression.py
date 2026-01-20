"""Tests for regression detection module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.regression import (
    RegressionReport,
    RegressionTask,
    detect_regressions,
    format_regression_report,
    load_baseline_results,
    send_discord_notification,
    send_email_notification,
    send_notification,
    send_slack_notification,
)


@pytest.fixture
def baseline_results():
    """Sample baseline results."""
    return {
        "tasks": [
            {
                "instance_id": "task-1",
                "mcp": {"resolved": True, "error": None},
            },
            {
                "instance_id": "task-2",
                "mcp": {"resolved": False, "error": "Test failed"},
            },
            {
                "instance_id": "task-3",
                "mcp": {"resolved": True, "error": None},
            },
            {
                "instance_id": "task-4",
                "mcp": {"resolved": False, "error": "Timeout"},
            },
        ]
    }


@pytest.fixture
def current_results_with_regressions():
    """Sample current results with regressions."""
    return {
        "tasks": [
            {
                "instance_id": "task-1",
                "mcp": {"resolved": False, "error": "New bug"},  # Regression
            },
            {
                "instance_id": "task-2",
                "mcp": {"resolved": True, "error": None},  # Improvement
            },
            {
                "instance_id": "task-3",
                "mcp": {"resolved": True, "error": None},  # Still passing
            },
            {
                "instance_id": "task-4",
                "mcp": {"resolved": False, "error": "Timeout"},  # Still failing
            },
        ]
    }


@pytest.fixture
def current_results_no_regressions():
    """Sample current results without regressions."""
    return {
        "tasks": [
            {
                "instance_id": "task-1",
                "mcp": {"resolved": True, "error": None},
            },
            {
                "instance_id": "task-2",
                "mcp": {"resolved": True, "error": None},  # Improvement
            },
            {
                "instance_id": "task-3",
                "mcp": {"resolved": True, "error": None},
            },
            {
                "instance_id": "task-4",
                "mcp": {"resolved": False, "error": "Timeout"},
            },
        ]
    }


def test_load_baseline_results():
    """Test loading baseline results from JSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"tasks": [{"instance_id": "test", "mcp": {"resolved": True}}]}, f)
        temp_path = Path(f.name)

    try:
        results = load_baseline_results(temp_path)
        assert "tasks" in results
        assert len(results["tasks"]) == 1
        assert results["tasks"][0]["instance_id"] == "test"
    finally:
        temp_path.unlink()


def test_load_baseline_results_file_not_found():
    """Test loading baseline results when file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        load_baseline_results(Path("/nonexistent/file.json"))


def test_load_baseline_results_invalid_json():
    """Test loading baseline results with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("invalid json {")
        temp_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_baseline_results(temp_path)
    finally:
        temp_path.unlink()


def test_detect_regressions(baseline_results, current_results_with_regressions):
    """Test regression detection with regressions present."""
    report = detect_regressions(current_results_with_regressions, baseline_results)

    assert report.total_tasks == 4
    assert report.regression_count == 1
    assert report.improvement_count == 1
    assert report.regression_rate == 0.25

    # Check regression details
    assert len(report.regressions) == 1
    regression = report.regressions[0]
    assert regression.instance_id == "task-1"
    assert regression.baseline_resolved is True
    assert regression.current_resolved is False
    assert regression.current_error == "New bug"

    # Check improvement details
    assert len(report.improvements) == 1
    improvement = report.improvements[0]
    assert improvement.instance_id == "task-2"
    assert improvement.baseline_resolved is False
    assert improvement.current_resolved is True


def test_detect_regressions_no_regressions(baseline_results, current_results_no_regressions):
    """Test regression detection without regressions."""
    report = detect_regressions(current_results_no_regressions, baseline_results)

    assert report.total_tasks == 4
    assert report.regression_count == 0
    assert report.improvement_count == 1
    assert report.regression_rate == 0.0


def test_detect_regressions_empty_tasks():
    """Test regression detection with empty task lists."""
    baseline = {"tasks": []}
    current = {"tasks": []}

    report = detect_regressions(current, baseline)

    assert report.total_tasks == 0
    assert report.regression_count == 0
    assert report.improvement_count == 0
    assert report.regression_rate == 0.0


def test_detect_regressions_missing_tasks():
    """Test regression detection when tasks are missing from current run."""
    baseline = {
        "tasks": [
            {"instance_id": "task-1", "mcp": {"resolved": True}},
            {"instance_id": "task-2", "mcp": {"resolved": True}},
        ]
    }
    current = {
        "tasks": [
            {"instance_id": "task-1", "mcp": {"resolved": True}},
            # task-2 is missing
        ]
    }

    report = detect_regressions(current, baseline)

    # Only task-1 is compared (task-2 is ignored)
    assert report.total_tasks == 1
    assert report.regression_count == 0


def test_regression_report_has_regressions():
    """Test RegressionReport.has_regressions method."""
    report = RegressionReport(
        total_tasks=10,
        regressions=[RegressionTask("task-1", baseline_resolved=True, current_resolved=False)],
        improvements=[],
        regression_count=1,
        improvement_count=0,
        regression_rate=0.1,
    )

    assert report.has_regressions() is True

    report_no_regressions = RegressionReport(
        total_tasks=10,
        regressions=[],
        improvements=[],
        regression_count=0,
        improvement_count=0,
        regression_rate=0.0,
    )

    assert report_no_regressions.has_regressions() is False


def test_regression_report_exceeds_threshold():
    """Test RegressionReport.exceeds_threshold method."""
    report = RegressionReport(
        total_tasks=10,
        regressions=[],
        improvements=[],
        regression_count=3,
        improvement_count=0,
        regression_rate=0.3,
    )

    assert report.exceeds_threshold(0.2) is True
    assert report.exceeds_threshold(0.3) is False
    assert report.exceeds_threshold(0.4) is False


def test_format_regression_report():
    """Test formatting regression report."""
    report = RegressionReport(
        total_tasks=10,
        regressions=[
            RegressionTask(
                "task-1",
                baseline_resolved=True,
                current_resolved=False,
                current_error="New bug",
            ),
            RegressionTask(
                "task-2",
                baseline_resolved=True,
                current_resolved=False,
                current_error="A" * 100,  # Long error
            ),
        ],
        improvements=[RegressionTask("task-3", baseline_resolved=False, current_resolved=True)],
        regression_count=2,
        improvement_count=1,
        regression_rate=0.2,
    )

    formatted = format_regression_report(report)

    assert "REGRESSION DETECTION REPORT" in formatted
    assert "Total tasks compared: 10" in formatted
    assert "Regressions detected: 2" in formatted
    assert "Improvements detected: 1" in formatted
    assert "Regression rate: 20.0%" in formatted
    assert "task-1" in formatted
    assert "task-2" in formatted
    assert "task-3" in formatted
    assert "New bug" in formatted
    # Long error should be truncated
    assert "..." in formatted


@patch("mcpbr.regression.requests.post")
def test_send_slack_notification(mock_post):
    """Test sending Slack notification."""
    mock_post.return_value.status_code = 200

    report = RegressionReport(
        total_tasks=10,
        regressions=[RegressionTask("task-1", baseline_resolved=True, current_resolved=False)],
        improvements=[],
        regression_count=1,
        improvement_count=0,
        regression_rate=0.1,
    )

    send_slack_notification("https://hooks.slack.com/test", report)

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://hooks.slack.com/test"
    assert "attachments" in call_args[1]["json"]


@patch("mcpbr.regression.requests.post")
def test_send_slack_notification_no_regressions(mock_post):
    """Test sending Slack notification when there are no regressions."""
    mock_post.return_value.status_code = 200

    report = RegressionReport(
        total_tasks=10,
        regressions=[],
        improvements=[RegressionTask("task-1", baseline_resolved=False, current_resolved=True)],
        regression_count=0,
        improvement_count=1,
        regression_rate=0.0,
    )

    send_slack_notification("https://hooks.slack.com/test", report)

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    payload = call_args[1]["json"]
    assert payload["attachments"][0]["color"] == "good"


@patch("mcpbr.regression.requests.post")
def test_send_discord_notification(mock_post):
    """Test sending Discord notification."""
    mock_post.return_value.status_code = 200

    report = RegressionReport(
        total_tasks=10,
        regressions=[RegressionTask("task-1", baseline_resolved=True, current_resolved=False)],
        improvements=[],
        regression_count=1,
        improvement_count=0,
        regression_rate=0.1,
    )

    send_discord_notification("https://discord.com/api/webhooks/test", report)

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://discord.com/api/webhooks/test"
    assert "embeds" in call_args[1]["json"]


@patch("mcpbr.regression.smtplib.SMTP")
def test_send_email_notification(mock_smtp):
    """Test sending email notification."""
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    report = RegressionReport(
        total_tasks=10,
        regressions=[RegressionTask("task-1", baseline_resolved=True, current_resolved=False)],
        improvements=[],
        regression_count=1,
        improvement_count=0,
        regression_rate=0.1,
    )

    send_email_notification(
        smtp_host="smtp.example.com",
        smtp_port=587,
        from_email="sender@example.com",
        to_email="recipient@example.com",
        report=report,
        smtp_user="user",
        smtp_password="password",
        use_tls=True,
    )

    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user", "password")
    mock_server.send_message.assert_called_once()


@patch("mcpbr.regression.send_slack_notification")
@patch("mcpbr.regression.send_discord_notification")
@patch("mcpbr.regression.send_email_notification")
def test_send_notification_all_channels(mock_email, mock_discord, mock_slack):
    """Test sending notifications to all configured channels."""
    report = RegressionReport(
        total_tasks=10,
        regressions=[],
        improvements=[],
        regression_count=0,
        improvement_count=0,
        regression_rate=0.0,
    )

    email_config = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "from_email": "sender@example.com",
        "to_email": "recipient@example.com",
    }

    send_notification(
        report,
        slack_webhook="https://hooks.slack.com/test",
        discord_webhook="https://discord.com/api/webhooks/test",
        email_config=email_config,
    )

    mock_slack.assert_called_once()
    mock_discord.assert_called_once()
    mock_email.assert_called_once()


@patch("mcpbr.regression.send_slack_notification")
def test_send_notification_handles_errors(mock_slack, capsys):
    """Test that send_notification handles errors gracefully."""
    mock_slack.side_effect = Exception("Connection failed")

    report = RegressionReport(
        total_tasks=10,
        regressions=[],
        improvements=[],
        regression_count=0,
        improvement_count=0,
        regression_rate=0.0,
    )

    # Should not raise exception
    send_notification(report, slack_webhook="https://hooks.slack.com/test")

    captured = capsys.readouterr()
    assert "Warning: Failed to send Slack notification" in captured.out


def test_regression_task_dataclass():
    """Test RegressionTask dataclass."""
    task = RegressionTask(
        instance_id="test-1",
        baseline_resolved=True,
        current_resolved=False,
        baseline_error=None,
        current_error="Test failed",
    )

    assert task.instance_id == "test-1"
    assert task.baseline_resolved is True
    assert task.current_resolved is False
    assert task.baseline_error is None
    assert task.current_error == "Test failed"


def test_detect_regressions_handles_missing_mcp_data():
    """Test regression detection handles tasks without MCP data."""
    baseline = {
        "tasks": [
            {"instance_id": "task-1", "mcp": {"resolved": True}},
            {"instance_id": "task-2"},  # Missing mcp data
        ]
    }
    current = {
        "tasks": [
            {"instance_id": "task-1", "mcp": {"resolved": False}},
            {"instance_id": "task-2", "mcp": {"resolved": True}},
        ]
    }

    report = detect_regressions(current, baseline)

    # task-1 should be detected as regression
    # task-2 should be detected as improvement (False -> True)
    assert report.regression_count == 1
    assert report.improvement_count == 1


def test_format_regression_report_truncates_long_lists():
    """Test that regression report truncates long lists of tasks."""
    regressions = [
        RegressionTask(f"task-{i}", baseline_resolved=True, current_resolved=False)
        for i in range(15)
    ]

    report = RegressionReport(
        total_tasks=20,
        regressions=regressions,
        improvements=[],
        regression_count=15,
        improvement_count=0,
        regression_rate=0.75,
    )

    formatted = format_regression_report(report)

    # All regressions should be listed (no truncation in text format)
    for i in range(15):
        assert f"task-{i}" in formatted
