"""Regression detection and alerting for MCP benchmarks."""

import json
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import requests


@dataclass
class RegressionTask:
    """Details about a regressed task."""

    instance_id: str
    baseline_resolved: bool
    current_resolved: bool
    baseline_error: str | None = None
    current_error: str | None = None


@dataclass
class RegressionReport:
    """Report of regression detection results."""

    total_tasks: int
    regressions: list[RegressionTask]
    improvements: list[RegressionTask]
    regression_count: int
    improvement_count: int
    regression_rate: float

    def has_regressions(self) -> bool:
        """Check if there are any regressions."""
        return self.regression_count > 0

    def exceeds_threshold(self, threshold: float) -> bool:
        """Check if regression rate exceeds threshold.

        Args:
            threshold: Maximum acceptable regression rate (0-1).

        Returns:
            True if regression rate exceeds threshold.
        """
        return self.regression_rate > threshold


def load_baseline_results(baseline_path: Path) -> dict[str, Any]:
    """Load baseline results from a JSON file.

    Args:
        baseline_path: Path to baseline results JSON file.

    Returns:
        Dictionary containing baseline results.

    Raises:
        FileNotFoundError: If baseline file doesn't exist.
        ValueError: If baseline file is invalid JSON.
    """
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline results not found: {baseline_path}")

    try:
        with open(baseline_path) as f:
            data: dict[str, Any] = json.load(f)
            return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in baseline file: {e}") from e


def detect_regressions(
    current_results: dict[str, Any], baseline_results: dict[str, Any]
) -> RegressionReport:
    """Detect regressions by comparing current results against baseline.

    A regression is when a task that passed in the baseline now fails.
    An improvement is when a task that failed in the baseline now passes.

    Args:
        current_results: Current evaluation results.
        baseline_results: Baseline evaluation results.

    Returns:
        RegressionReport with detected regressions and improvements.
    """
    # Build maps of instance_id -> task results
    baseline_map = {task["instance_id"]: task for task in baseline_results.get("tasks", [])}
    current_map = {task["instance_id"]: task for task in current_results.get("tasks", [])}

    regressions = []
    improvements = []

    # Compare tasks present in both runs
    for instance_id in baseline_map:
        if instance_id not in current_map:
            continue

        baseline_task = baseline_map[instance_id]
        current_task = current_map[instance_id]

        # Check MCP agent results
        baseline_resolved = baseline_task.get("mcp", {}).get("resolved", False)
        current_resolved = current_task.get("mcp", {}).get("resolved", False)

        baseline_error = baseline_task.get("mcp", {}).get("error")
        current_error = current_task.get("mcp", {}).get("error")

        # Regression: previously passed, now fails
        if baseline_resolved and not current_resolved:
            regressions.append(
                RegressionTask(
                    instance_id=instance_id,
                    baseline_resolved=baseline_resolved,
                    current_resolved=current_resolved,
                    baseline_error=baseline_error,
                    current_error=current_error,
                )
            )

        # Improvement: previously failed, now passes
        elif not baseline_resolved and current_resolved:
            improvements.append(
                RegressionTask(
                    instance_id=instance_id,
                    baseline_resolved=baseline_resolved,
                    current_resolved=current_resolved,
                    baseline_error=baseline_error,
                    current_error=current_error,
                )
            )

    total_tasks = len(baseline_map.keys() & current_map.keys())
    regression_rate = len(regressions) / total_tasks if total_tasks > 0 else 0.0

    return RegressionReport(
        total_tasks=total_tasks,
        regressions=regressions,
        improvements=improvements,
        regression_count=len(regressions),
        improvement_count=len(improvements),
        regression_rate=regression_rate,
    )


def format_regression_report(report: RegressionReport) -> str:
    """Format regression report as human-readable text.

    Args:
        report: Regression report to format.

    Returns:
        Formatted report string.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("REGRESSION DETECTION REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Total tasks compared: {report.total_tasks}")
    lines.append(f"Regressions detected: {report.regression_count}")
    lines.append(f"Improvements detected: {report.improvement_count}")
    lines.append(f"Regression rate: {report.regression_rate:.1%}")
    lines.append("")

    if report.regressions:
        lines.append("REGRESSIONS (previously passed, now failed):")
        lines.append("-" * 70)
        for reg in report.regressions:
            lines.append(f"  - {reg.instance_id}")
            if reg.current_error:
                error_preview = (
                    reg.current_error[:60] + "..."
                    if len(reg.current_error) > 60
                    else reg.current_error
                )
                lines.append(f"    Error: {error_preview}")
        lines.append("")

    if report.improvements:
        lines.append("IMPROVEMENTS (previously failed, now passed):")
        lines.append("-" * 70)
        for imp in report.improvements:
            lines.append(f"  - {imp.instance_id}")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def send_slack_notification(webhook_url: str, report: RegressionReport) -> None:
    """Send regression report to Slack via webhook.

    Args:
        webhook_url: Slack webhook URL.
        report: Regression report to send.

    Raises:
        requests.RequestException: If webhook request fails.
    """
    color = "danger" if report.has_regressions() else "good"
    title = (
        f"Regression Alert: {report.regression_count} tasks regressed"
        if report.has_regressions()
        else f"No Regressions: {report.improvement_count} improvements"
    )

    regression_list = "\n".join([f"• {r.instance_id}" for r in report.regressions[:10]])
    if len(report.regressions) > 10:
        regression_list += f"\n... and {len(report.regressions) - 10} more"

    improvement_list = "\n".join([f"• {i.instance_id}" for i in report.improvements[:10]])
    if len(report.improvements) > 10:
        improvement_list += f"\n... and {len(report.improvements) - 10} more"

    fields = [
        {
            "title": "Total Tasks",
            "value": str(report.total_tasks),
            "short": True,
        },
        {
            "title": "Regressions",
            "value": str(report.regression_count),
            "short": True,
        },
        {
            "title": "Improvements",
            "value": str(report.improvement_count),
            "short": True,
        },
        {
            "title": "Regression Rate",
            "value": f"{report.regression_rate:.1%}",
            "short": True,
        },
    ]

    if report.regressions:
        fields.append(
            {
                "title": "Regressed Tasks",
                "value": regression_list,
                "short": False,
            }
        )

    if report.improvements:
        fields.append(
            {
                "title": "Improved Tasks",
                "value": improvement_list,
                "short": False,
            }
        )

    payload = {
        "attachments": [
            {
                "color": color,
                "title": title,
                "fields": fields,
            }
        ]
    }

    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()


def send_discord_notification(webhook_url: str, report: RegressionReport) -> None:
    """Send regression report to Discord via webhook.

    Args:
        webhook_url: Discord webhook URL.
        report: Regression report to send.

    Raises:
        requests.RequestException: If webhook request fails.
    """
    color = 0xFF0000 if report.has_regressions() else 0x00FF00  # Red or Green

    title = (
        f"Regression Alert: {report.regression_count} tasks regressed"
        if report.has_regressions()
        else f"No Regressions: {report.improvement_count} improvements"
    )

    description = f"**Total Tasks:** {report.total_tasks}\n"
    description += f"**Regressions:** {report.regression_count}\n"
    description += f"**Improvements:** {report.improvement_count}\n"
    description += f"**Regression Rate:** {report.regression_rate:.1%}\n"

    fields = []

    if report.regressions:
        regression_list = "\n".join([f"• {r.instance_id}" for r in report.regressions[:10]])
        if len(report.regressions) > 10:
            regression_list += f"\n... and {len(report.regressions) - 10} more"
        fields.append(
            {
                "name": "Regressed Tasks",
                "value": regression_list,
                "inline": False,
            }
        )

    if report.improvements:
        improvement_list = "\n".join([f"• {i.instance_id}" for i in report.improvements[:10]])
        if len(report.improvements) > 10:
            improvement_list += f"\n... and {len(report.improvements) - 10} more"
        fields.append(
            {
                "name": "Improved Tasks",
                "value": improvement_list,
                "inline": False,
            }
        )

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields,
            }
        ]
    }

    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()


def send_email_notification(
    smtp_host: str,
    smtp_port: int,
    from_email: str,
    to_email: str,
    report: RegressionReport,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    use_tls: bool = True,
) -> None:
    """Send regression report via email.

    Args:
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port.
        from_email: Sender email address.
        to_email: Recipient email address.
        report: Regression report to send.
        smtp_user: SMTP username (if authentication required).
        smtp_password: SMTP password (if authentication required).
        use_tls: Whether to use TLS encryption.

    Raises:
        smtplib.SMTPException: If email sending fails.
    """
    subject = (
        f"Regression Alert: {report.regression_count} tasks regressed"
        if report.has_regressions()
        else f"No Regressions: {report.improvement_count} improvements"
    )

    body = format_regression_report(report)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        if use_tls:
            server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.send_message(msg)


def send_notification(
    report: RegressionReport,
    slack_webhook: str | None = None,
    discord_webhook: str | None = None,
    email_config: dict[str, Any] | None = None,
) -> None:
    """Send notifications via configured channels.

    Args:
        report: Regression report to send.
        slack_webhook: Slack webhook URL (optional).
        discord_webhook: Discord webhook URL (optional).
        email_config: Email configuration dict (optional).
    """
    if slack_webhook:
        try:
            send_slack_notification(slack_webhook, report)
        except Exception as e:
            print(f"Warning: Failed to send Slack notification: {e}")

    if discord_webhook:
        try:
            send_discord_notification(discord_webhook, report)
        except Exception as e:
            print(f"Warning: Failed to send Discord notification: {e}")

    if email_config:
        try:
            send_email_notification(report=report, **email_config)
        except Exception as e:
            print(f"Warning: Failed to send email notification: {e}")
