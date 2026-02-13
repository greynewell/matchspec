"""General notification system for evaluation events.

Supports Slack, Discord, and Email notifications for completion, regression,
and lifecycle events (eval_started, progress, failure, infra_provisioned,
infra_teardown). Failures are caught and logged — notifications never raise
exceptions to the caller.
"""

import logging
import smtplib
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Event types that represent lifecycle events (not completion/regression)
LIFECYCLE_EVENT_TYPES = frozenset(
    {"eval_started", "progress", "failure", "infra_provisioned", "infra_teardown"}
)


@dataclass
class NotificationEvent:
    """Event payload for notifications."""

    event_type: str  # "completion", "regression", or lifecycle types
    benchmark: str
    model: str
    total_tasks: int = 0
    resolved_tasks: int = 0
    resolution_rate: float = 0.0
    total_cost: float | None = None
    runtime_seconds: float | None = None
    regression_count: int | None = None
    improvement_count: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _build_slack_text(event: NotificationEvent) -> str:
    """Build the text block for enriched Slack notifications.

    Includes per-task results, tool stats, and Gist link when available
    in event.extra.
    """
    sections = []

    # MCP server info
    mcp_server = event.extra.get("mcp_server")
    if mcp_server:
        sections.append(f"*MCP Server:* `{mcp_server}`")

    # Per-task results
    task_results = event.extra.get("task_results")
    if task_results:
        lines = ["*Per-Task Results:*"]
        for t in task_results:
            status = "\u2705" if t.get("resolved") else "\u274c"
            lines.append(f"  {status} `{t['instance_id']}`")
        sections.append("\n".join(lines))

    # Tool stats
    tool_stats = event.extra.get("tool_stats")
    if tool_stats:
        total = tool_stats.get("total_tool_calls", 0)
        failed = tool_stats.get("total_failures", 0)
        success = total - failed
        rate = tool_stats.get("failure_rate", 0)
        sections.append(
            f"*Tool Usage:* {total} calls ({success} ok, {failed} failed, {rate:.0%} failure rate)"
        )

    # Gist link
    gist_url = event.extra.get("gist_url")
    if gist_url:
        sections.append(f"*Full Report:* <{gist_url}|View on GitHub Gist>")

    return "\n\n".join(sections)


def _format_lifecycle_slack_text(event: NotificationEvent) -> str:
    """Build Slack text for lifecycle events (non-completion).

    Formats eval_started, progress, failure, infra_provisioned, and
    infra_teardown events using fields from event.extra.
    """
    extra = event.extra
    et = event.event_type

    if et == "eval_started":
        parts = [f"\U0001f680 *Eval Started:* {event.benchmark}"]
        parts.append(f"*Model:* {event.model}")
        if extra.get("total_tasks"):
            parts.append(f"*Tasks:* {extra['total_tasks']}")
        if extra.get("max_concurrent"):
            parts.append(f"*Concurrency:* {extra['max_concurrent']}")
        if extra.get("infrastructure_mode"):
            parts.append(f"*Infra:* {extra['infrastructure_mode']}")
        if extra.get("mcp_server"):
            parts.append(f"*MCP Server:* `{extra['mcp_server']}`")
        return "\n".join(parts)

    if et == "infra_provisioned":
        parts = ["\U0001f5a5\ufe0f *Infrastructure Provisioned*"]
        if extra.get("vm_name"):
            parts.append(f"*VM:* {extra['vm_name']}")
        if extra.get("ip"):
            parts.append(f"*IP:* {extra['ip']}")
        if extra.get("region"):
            parts.append(f"*Region:* {extra['region']}")
        if extra.get("provisioning_time"):
            parts.append(f"*Provisioning Time:* {extra['provisioning_time']:.1f}s")
        if extra.get("ssh_cmd"):
            parts.append(f"*SSH:* `{extra['ssh_cmd']}`")
        return "\n".join(parts)

    if et == "infra_teardown":
        parts = ["\u2b07\ufe0f *Infrastructure Teardown*"]
        parts.append(f"*Benchmark:* {event.benchmark}")
        if extra.get("vm_name"):
            parts.append(f"*VM:* {extra['vm_name']}")
        return "\n".join(parts)

    if et == "progress":
        completed = extra.get("completed", 0)
        total = extra.get("total", 0)
        parts = [f"\U0001f4ca *Progress:* {event.benchmark}"]
        parts.append(f"*Completed:* {completed}/{total}")
        if extra.get("elapsed_seconds"):
            mins = extra["elapsed_seconds"] / 60
            parts.append(f"*Elapsed:* {mins:.1f} min")
        if extra.get("estimated_remaining_seconds"):
            mins = extra["estimated_remaining_seconds"] / 60
            parts.append(f"*ETA:* {mins:.1f} min remaining")
        if extra.get("running_cost") is not None:
            parts.append(f"*Cost so far:* ${extra['running_cost']:.2f}")
        return "\n".join(parts)

    if et == "failure":
        parts = ["\u274c *Evaluation Failed*"]
        parts.append(f"*Benchmark:* {event.benchmark}")
        parts.append(f"*Model:* {event.model}")
        if extra.get("error"):
            parts.append(f"*Error:* {extra['error']}")
        if extra.get("completed_tasks") is not None:
            total = extra.get("total_tasks", "?")
            parts.append(f"*Completed:* {extra['completed_tasks']}/{total}")
        if extra.get("last_successful_task"):
            parts.append(f"*Last Successful:* `{extra['last_successful_task']}`")
        return "\n".join(parts)

    return ""


def _format_lifecycle_discord_description(event: NotificationEvent) -> str:
    """Build Discord embed description for lifecycle events."""
    extra = event.extra
    et = event.event_type

    if et == "eval_started":
        parts = [f"**Model:** {event.model}"]
        if extra.get("total_tasks"):
            parts.append(f"**Tasks:** {extra['total_tasks']}")
        if extra.get("max_concurrent"):
            parts.append(f"**Concurrency:** {extra['max_concurrent']}")
        if extra.get("infrastructure_mode"):
            parts.append(f"**Infra:** {extra['infrastructure_mode']}")
        if extra.get("mcp_server"):
            parts.append(f"**MCP Server:** `{extra['mcp_server']}`")
        return "\n".join(parts)

    if et == "infra_provisioned":
        parts = []
        if extra.get("vm_name"):
            parts.append(f"**VM:** {extra['vm_name']}")
        if extra.get("ip"):
            parts.append(f"**IP:** {extra['ip']}")
        if extra.get("region"):
            parts.append(f"**Region:** {extra['region']}")
        if extra.get("provisioning_time"):
            parts.append(f"**Provisioning Time:** {extra['provisioning_time']:.1f}s")
        if extra.get("ssh_cmd"):
            parts.append(f"**SSH:** `{extra['ssh_cmd']}`")
        return "\n".join(parts)

    if et == "infra_teardown":
        parts = [f"**Benchmark:** {event.benchmark}"]
        if extra.get("vm_name"):
            parts.append(f"**VM:** {extra['vm_name']}")
        return "\n".join(parts)

    if et == "progress":
        completed = extra.get("completed", 0)
        total = extra.get("total", 0)
        parts = [f"**Completed:** {completed}/{total}"]
        if extra.get("elapsed_seconds"):
            mins = extra["elapsed_seconds"] / 60
            parts.append(f"**Elapsed:** {mins:.1f} min")
        if extra.get("estimated_remaining_seconds"):
            mins = extra["estimated_remaining_seconds"] / 60
            parts.append(f"**ETA:** {mins:.1f} min remaining")
        if extra.get("running_cost") is not None:
            parts.append(f"**Cost so far:** ${extra['running_cost']:.2f}")
        return "\n".join(parts)

    if et == "failure":
        parts = [f"**Benchmark:** {event.benchmark}", f"**Model:** {event.model}"]
        if extra.get("error"):
            parts.append(f"**Error:** {extra['error']}")
        if extra.get("completed_tasks") is not None:
            total = extra.get("total_tasks", "?")
            parts.append(f"**Completed:** {extra['completed_tasks']}/{total}")
        if extra.get("last_successful_task"):
            parts.append(f"**Last Successful:** `{extra['last_successful_task']}`")
        return "\n".join(parts)

    return ""


def _format_lifecycle_email_body(event: NotificationEvent) -> str:
    """Build plain-text email body for lifecycle events."""
    extra = event.extra
    et = event.event_type

    if et == "eval_started":
        lines = [f"Eval Started: {event.benchmark}", f"Model: {event.model}"]
        if extra.get("total_tasks"):
            lines.append(f"Tasks: {extra['total_tasks']}")
        if extra.get("max_concurrent"):
            lines.append(f"Concurrency: {extra['max_concurrent']}")
        if extra.get("infrastructure_mode"):
            lines.append(f"Infrastructure: {extra['infrastructure_mode']}")
        if extra.get("mcp_server"):
            lines.append(f"MCP Server: {extra['mcp_server']}")
        return "\n".join(lines)

    if et == "infra_provisioned":
        lines = ["Infrastructure Provisioned"]
        for key in ("vm_name", "ip", "region", "ssh_cmd"):
            if extra.get(key):
                lines.append(f"{key}: {extra[key]}")
        if extra.get("provisioning_time"):
            lines.append(f"Provisioning Time: {extra['provisioning_time']:.1f}s")
        return "\n".join(lines)

    if et == "infra_teardown":
        lines = ["Infrastructure Teardown", f"Benchmark: {event.benchmark}"]
        if extra.get("vm_name"):
            lines.append(f"VM: {extra['vm_name']}")
        return "\n".join(lines)

    if et == "progress":
        completed = extra.get("completed", 0)
        total = extra.get("total", 0)
        lines = [f"Progress: {event.benchmark}", f"Completed: {completed}/{total}"]
        if extra.get("elapsed_seconds"):
            mins = extra["elapsed_seconds"] / 60
            lines.append(f"Elapsed: {mins:.1f} min")
        if extra.get("estimated_remaining_seconds"):
            mins = extra["estimated_remaining_seconds"] / 60
            lines.append(f"ETA: {mins:.1f} min remaining")
        if extra.get("running_cost") is not None:
            lines.append(f"Cost so far: ${extra['running_cost']:.2f}")
        return "\n".join(lines)

    if et == "failure":
        lines = [f"Evaluation Failed: {event.benchmark}", f"Model: {event.model}"]
        if extra.get("error"):
            lines.append(f"Error: {extra['error']}")
        if extra.get("completed_tasks") is not None:
            total = extra.get("total_tasks", "?")
            lines.append(f"Completed: {extra['completed_tasks']}/{total}")
        if extra.get("last_successful_task"):
            lines.append(f"Last Successful: {extra['last_successful_task']}")
        return "\n".join(lines)

    return ""


def _lifecycle_slack_color(event: NotificationEvent) -> str:
    """Return Slack attachment color for lifecycle events."""
    return {
        "eval_started": "#439FE0",  # Blue
        "infra_provisioned": "#439FE0",
        "infra_teardown": "#808080",  # Grey
        "progress": "#439FE0",
        "failure": "danger",
    }.get(event.event_type, "#808080")


def _lifecycle_discord_color(event: NotificationEvent) -> int:
    """Return Discord embed color for lifecycle events."""
    return {
        "eval_started": 0x439FE0,
        "infra_provisioned": 0x439FE0,
        "infra_teardown": 0x808080,
        "progress": 0x439FE0,
        "failure": 0xFF0000,
    }.get(event.event_type, 0x808080)


def send_slack_notification(webhook_url: str, event: NotificationEvent) -> None:
    """Send notification to Slack via webhook.

    Args:
        webhook_url: Slack webhook URL.
        event: Notification event payload.
    """
    # Lifecycle events use a separate formatting path
    if event.event_type in LIFECYCLE_EVENT_TYPES:
        title = f"mcpbr {event.event_type.replace('_', ' ').title()}: {event.benchmark}"
        color = _lifecycle_slack_color(event)
        text = _format_lifecycle_slack_text(event)
        attachment: dict[str, Any] = {"color": color, "title": title}
        if text:
            attachment["text"] = text
        payload = {"attachments": [attachment]}
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        return

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

    attachment = {"color": color, "title": title, "fields": fields}

    # Add enriched text block when extra data is available
    text = _build_slack_text(event)
    if text:
        attachment["text"] = text

    payload = {"attachments": [attachment]}

    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()


def send_slack_bot_notification(
    bot_token: str,
    channel: str,
    event: NotificationEvent,
) -> str | None:
    """Send notification via Slack Bot API and return the message timestamp.

    Uses chat.postMessage so we can thread replies (e.g. results JSON).
    Returns the message ``ts`` on success, or ``None`` on failure.

    Args:
        bot_token: Slack bot token (xoxb-...).
        channel: Slack channel ID.
        event: Notification event payload.
    """
    # Lifecycle events use dedicated formatter
    if event.event_type in LIFECYCLE_EVENT_TYPES:
        title = f"*mcpbr {event.event_type.replace('_', ' ').title()}: {event.benchmark}*"
        text = _format_lifecycle_slack_text(event)
        message_text = f"{title}\n\n{text}" if text else title

        from slack_sdk import WebClient  # pip install mcpbr[slack]

        client = WebClient(token=bot_token)
        response = client.chat_postMessage(channel=channel, text=message_text)
        ts: str | None = response.get("ts")
        return ts

    color_emoji = "\u2705" if event.resolution_rate >= 0.3 else "\u26a0\ufe0f"
    if event.event_type == "regression" and event.regression_count:
        color_emoji = "\ud83d\udea8"

    title = f"*mcpbr {event.event_type.title()}: {event.benchmark}*"

    lines = [title, ""]

    text = _build_slack_text(event)
    if text:
        lines.append(text)
        lines.append("")

    summary_parts = [
        f"*Model:* {event.model}",
        f"*Resolution Rate:* {color_emoji} {event.resolution_rate:.1%}",
        f"*Tasks:* {event.resolved_tasks}/{event.total_tasks}",
    ]
    if event.total_cost is not None:
        summary_parts.append(f"*Cost:* ${event.total_cost:.2f}")
    if event.runtime_seconds is not None:
        mins = event.runtime_seconds / 60
        summary_parts.append(f"*Runtime:* {mins:.1f} min")
    lines.append(" | ".join(summary_parts))

    message_text = "\n".join(lines)

    from slack_sdk import WebClient  # pip install mcpbr[slack]

    client = WebClient(token=bot_token)
    response = client.chat_postMessage(channel=channel, text=message_text)
    result_ts: str | None = response.get("ts")
    return result_ts


def post_slack_thread_reply(
    bot_token: str,
    channel: str,
    thread_ts: str,
    content: str,
) -> None:
    """Upload a results file as a snippet in a Slack thread.

    Uses the Slack SDK ``files_upload_v2`` which handles the three-step
    external upload flow (getUploadURL → PUT → completeUpload) and shares
    the file to the channel as a threaded reply.

    Args:
        bot_token: Slack bot token (xoxb-...).
        channel: Slack channel ID.
        thread_ts: Parent message timestamp to reply to.
        content: Text content to upload as a JSON snippet.
    """
    from slack_sdk import WebClient  # pip install mcpbr[slack]

    client = WebClient(token=bot_token)
    client.files_upload_v2(
        channel=channel,
        thread_ts=thread_ts,
        content=content,
        filename="results.json",
        title="Evaluation Results",
        snippet_type="json",
    )


def create_gist_report(
    github_token: str,
    results_json: str,
    description: str = "mcpbr evaluation results",
) -> str | None:
    """Create a GitHub Gist with evaluation results.

    Args:
        github_token: GitHub personal access token with gist scope.
        results_json: JSON string of evaluation results.
        description: Gist description.

    Returns:
        Gist HTML URL, or None on failure.
    """
    try:
        response = requests.post(
            "https://api.github.com/gists",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "description": description,
                "public": False,
                "files": {
                    "results.json": {"content": results_json},
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        url: str | None = response.json().get("html_url")
        return url
    except Exception as e:
        logger.warning("Failed to create GitHub Gist: %s", e)
        return None


def send_discord_notification(webhook_url: str, event: NotificationEvent) -> None:
    """Send notification to Discord via webhook.

    Args:
        webhook_url: Discord webhook URL.
        event: Notification event payload.
    """
    # Lifecycle events use a separate formatting path
    if event.event_type in LIFECYCLE_EVENT_TYPES:
        title = f"mcpbr {event.event_type.replace('_', ' ').title()}: {event.benchmark}"
        color = _lifecycle_discord_color(event)
        description = _format_lifecycle_discord_description(event)
        payload = {"embeds": [{"title": title, "description": description, "color": color}]}
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        return

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
    # Lifecycle events use a separate formatting path
    if event.event_type in LIFECYCLE_EVENT_TYPES:
        label = event.event_type.replace("_", " ").title()
        subject = f"mcpbr {label}: {event.benchmark}"
        body = _format_lifecycle_email_body(event)
    else:
        subject = (
            f"mcpbr {event.event_type.title()}: {event.benchmark}"
            f" \u2014 {event.resolution_rate:.1%}"
        )

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
                slack_webhook, discord_webhook, email (dict),
                slack_bot_token, slack_channel, github_token.
        event: Notification event payload.
    """
    is_lifecycle = event.event_type in LIFECYCLE_EVENT_TYPES

    # Create Gist first so the URL can be included in notifications
    # (only for completion/regression events that have results)
    if not is_lifecycle and config.get("github_token") and event.extra.get("results_json"):
        try:
            gist_url = create_gist_report(
                github_token=config["github_token"],
                results_json=event.extra["results_json"],
                description=f"mcpbr {event.benchmark} results — {event.model}",
            )
            if gist_url:
                event.extra["gist_url"] = gist_url
        except Exception as e:
            logger.warning("Failed to create Gist: %s", e)

    # Prefer bot API (supports threaded results reply); fall back to webhook
    slack_sent = False
    slack_ts: str | None = None
    if config.get("slack_bot_token") and config.get("slack_channel"):
        try:
            slack_ts = send_slack_bot_notification(
                bot_token=config["slack_bot_token"],
                channel=config["slack_channel"],
                event=event,
            )
            slack_sent = True
        except Exception as e:
            logger.warning("Failed to send Slack bot notification: %s", e)

        # Post results JSON as a threaded reply (completion events only)
        if not is_lifecycle and slack_ts and event.extra.get("results_json"):
            try:
                post_slack_thread_reply(
                    bot_token=config["slack_bot_token"],
                    channel=config["slack_channel"],
                    thread_ts=slack_ts,
                    content=event.extra["results_json"],
                )
            except Exception as e:
                logger.warning("Failed to post Slack thread reply: %s", e)

    if not slack_sent and config.get("slack_webhook"):
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
