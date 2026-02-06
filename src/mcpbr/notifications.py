"""General notification system for evaluation events.

Supports Slack, Discord, and Email notifications for completion and regression
events. Failures are caught and logged — notifications never raise exceptions
to the caller.
"""

import logging
import smtplib
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class NotificationEvent:
    """Event payload for notifications."""

    event_type: str  # "completion" or "regression"
    benchmark: str
    model: str
    total_tasks: int
    resolved_tasks: int
    resolution_rate: float
    total_cost: float | None = None
    runtime_seconds: float | None = None
    regression_count: int | None = None
    improvement_count: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def send_slack_notification(webhook_url: str, event: NotificationEvent) -> None:
    """Send notification to Slack via webhook.

    Args:
        webhook_url: Slack webhook URL.
        event: Notification event payload.
    """
    color = "good" if event.resolution_rate >= 0.3 else "warning"
    if event.event_type == "regression" and event.regression_count:
        color = "danger"

    title = f"mcpbr {event.event_type.title()}: {event.benchmark}"

    fields = [
        {"title": "Model", "value": event.model, "short": True},
        {"title": "Resolution Rate", "value": f"{event.resolution_rate:.1%}", "short": True},
        {
            "title": "Tasks",
            "value": f"{event.resolved_tasks}/{event.total_tasks}",
            "short": True,
        },
    ]

    if event.total_cost is not None:
        fields.append({"title": "Cost", "value": f"${event.total_cost:.2f}", "short": True})

    if event.runtime_seconds is not None:
        mins = event.runtime_seconds / 60
        fields.append({"title": "Runtime", "value": f"{mins:.1f} min", "short": True})

    if event.regression_count is not None:
        fields.append({"title": "Regressions", "value": str(event.regression_count), "short": True})
    if event.improvement_count is not None:
        fields.append(
            {"title": "Improvements", "value": str(event.improvement_count), "short": True}
        )

    payload = {"attachments": [{"color": color, "title": title, "fields": fields}]}

    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()


def send_discord_notification(webhook_url: str, event: NotificationEvent) -> None:
    """Send notification to Discord via webhook.

    Args:
        webhook_url: Discord webhook URL.
        event: Notification event payload.
    """
    color = 0x00FF00 if event.resolution_rate >= 0.3 else 0xFFA500  # Green or Orange
    if event.event_type == "regression" and event.regression_count:
        color = 0xFF0000  # Red

    title = f"mcpbr {event.event_type.title()}: {event.benchmark}"

    description = (
        f"**Model:** {event.model}\n"
        f"**Resolution Rate:** {event.resolution_rate:.1%}\n"
        f"**Tasks:** {event.resolved_tasks}/{event.total_tasks}\n"
    )

    if event.total_cost is not None:
        description += f"**Cost:** ${event.total_cost:.2f}\n"

    if event.runtime_seconds is not None:
        mins = event.runtime_seconds / 60
        description += f"**Runtime:** {mins:.1f} min\n"

    embed_fields = []
    if event.regression_count is not None:
        embed_fields.append(
            {"name": "Regressions", "value": str(event.regression_count), "inline": True}
        )
    if event.improvement_count is not None:
        embed_fields.append(
            {"name": "Improvements", "value": str(event.improvement_count), "inline": True}
        )

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": embed_fields,
            }
        ]
    }

    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()


def send_email_notification(config: dict[str, Any], event: NotificationEvent) -> None:
    """Send notification via SMTP email.

    Args:
        config: Email configuration with smtp_host, smtp_port, from_email, to_email,
                and optional smtp_user, smtp_password, use_tls.
        event: Notification event payload.
    """
    subject = f"mcpbr {event.event_type.title()}: {event.benchmark} — {event.resolution_rate:.1%}"

    body_lines = [
        f"Benchmark: {event.benchmark}",
        f"Model: {event.model}",
        f"Resolution Rate: {event.resolution_rate:.1%}",
        f"Tasks: {event.resolved_tasks}/{event.total_tasks}",
    ]

    if event.total_cost is not None:
        body_lines.append(f"Cost: ${event.total_cost:.2f}")

    if event.runtime_seconds is not None:
        mins = event.runtime_seconds / 60
        body_lines.append(f"Runtime: {mins:.1f} min")

    if event.regression_count is not None:
        body_lines.append(f"Regressions: {event.regression_count}")
    if event.improvement_count is not None:
        body_lines.append(f"Improvements: {event.improvement_count}")

    body = "\n".join(body_lines)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config["from_email"]
    msg["To"] = config["to_email"]

    use_tls = config.get("use_tls", True)

    with smtplib.SMTP(config["smtp_host"], config.get("smtp_port", 587), timeout=30) as server:
        if use_tls:
            server.starttls()
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.send_message(msg)


def dispatch_notification(config: dict[str, Any], event: NotificationEvent) -> None:
    """Send notifications to all configured channels.

    Failures are caught and logged — never raises.

    Args:
        config: Notification configuration with optional keys:
                slack_webhook, discord_webhook, email (dict).
        event: Notification event payload.
    """
    if config.get("slack_webhook"):
        try:
            send_slack_notification(config["slack_webhook"], event)
        except Exception as e:
            logger.warning("Failed to send Slack notification: %s", e)

    if config.get("discord_webhook"):
        try:
            send_discord_notification(config["discord_webhook"], event)
        except Exception as e:
            logger.warning("Failed to send Discord notification: %s", e)

    if config.get("email"):
        try:
            send_email_notification(config["email"], event)
        except Exception as e:
            logger.warning("Failed to send email notification: %s", e)
