from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional
import requests

from ..config import settings


def alert_webhook_provider() -> str:
    provider = str(settings.alert_webhook_provider or "").strip().lower()
    return provider if provider in {"generic", "slack", "telegram"} else "generic"


def alert_webhook_channel_label() -> str:
    mapping = {
        "generic": "Webhook",
        "slack": "Slack",
        "telegram": "Telegram",
    }
    return mapping.get(alert_webhook_provider(), "Webhook")


def alert_email_ready() -> bool:
    return bool(
        settings.alert_email_enabled
        and settings.alert_email_to
        and settings.smtp_host
        and settings.smtp_user
    )


def alert_slack_ready() -> bool:
    return bool(
        settings.alert_slack_enabled
        and settings.alert_slack_webhook_url.strip()
    )


def alert_telegram_ready() -> bool:
    return bool(
        settings.alert_telegram_enabled
        and settings.alert_telegram_bot_token.strip()
        and settings.alert_telegram_chat_id.strip()
    )


def alert_webhook_ready() -> bool:
    if not settings.alert_webhook_enabled:
        return False
    provider = alert_webhook_provider()
    if provider == "telegram":
        return bool(
            settings.alert_telegram_bot_token.strip()
            and settings.alert_telegram_chat_id.strip()
        )
    return bool(settings.alert_webhook_url.strip())


def send_alert_slack(text: str) -> bool:
    if not alert_slack_ready():
        return False
    try:
        response = requests.post(
            settings.alert_slack_webhook_url.strip(),
            json={"text": str(text or "").strip()},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        return 200 <= int(response.status_code) < 300
    except Exception:
        return False


def send_alert_telegram(text: str) -> bool:
    if not alert_telegram_ready():
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{settings.alert_telegram_bot_token.strip()}/sendMessage",
            json={
                "chat_id": settings.alert_telegram_chat_id.strip(),
                "text": str(text or "").strip(),
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return 200 <= int(response.status_code) < 300
    except Exception:
        return False


def send_alert_email(subject: str, body: str) -> bool:
    """
    Fire-and-forget SMTP email sender.
    Returns True if sent, False otherwise.
    """
    if not alert_email_ready():
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = settings.alert_email_to
    msg.set_content(body)

    try:
        if settings.smtp_use_tls:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        return True
    except Exception:
        return False


def send_alert_webhook(payload: dict) -> bool:
    if not alert_webhook_ready():
        return False
    provider = alert_webhook_provider()
    headers = {"Content-Type": "application/json"}
    try:
        if provider == "telegram":
            response = requests.post(
                f"https://api.telegram.org/bot{settings.alert_telegram_bot_token.strip()}/sendMessage",
                json={
                    "chat_id": settings.alert_telegram_chat_id.strip(),
                    "text": str(payload.get("text") or "").strip(),
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
        elif provider == "slack":
            if not settings.alert_webhook_url.strip():
                return False
            response = requests.post(
                settings.alert_webhook_url.strip(),
                json={
                    "text": str(payload.get("text") or "").strip(),
                },
                headers=headers,
                timeout=10,
            )
        else:
            secret = settings.alert_webhook_secret.strip()
            if secret:
                headers["X-Alert-Secret"] = secret
            response = requests.post(
                settings.alert_webhook_url.strip(),
                json=payload,
                headers=headers,
                timeout=10,
            )
        return 200 <= int(response.status_code) < 300
    except Exception:
        return False


def format_circuit_email(
    *,
    reason: str,
    keyword: str,
    last_error: str,
    consecutive_errors: int,
    consecutive_403: int,
) -> tuple[str, str]:
    subject = f"[CardFlip Monitor] Circuit open: {reason}"
    lines = [
        f"Reason: {reason}",
        f"Keyword: {keyword}",
        f"Last error: {last_error}",
        f"Consecutive errors: {consecutive_errors}",
        f"Consecutive 403: {consecutive_403}",
    ]
    return subject, "\n".join(lines)


def format_autotrade_alert_email(
    *,
    ready: bool,
    blocking_reasons: list[str],
    alert_summary: dict,
    alerts: list[dict],
    portfolio: dict,
    execution_readiness: dict,
    operating_state: dict,
) -> tuple[str, str]:
    alert_count = int(alert_summary.get("count") or 0)
    subject = f"[CardFlip Autotrade] {alert_count} active alert(s)"
    lines = [
        f"Ready: {ready}",
        f"Alert count: {alert_count}",
        f"Blocking reasons: {', '.join(blocking_reasons) if blocking_reasons else 'none'}",
        f"Execution ready: {bool(execution_readiness.get('live_ready'))}",
        f"Operating state: {str(operating_state.get('state') or 'normal')}",
        (
            "Portfolio: remaining "
            f"{round(float(portfolio.get('remaining_capital') or 0.0), 2)} / "
            f"deployed {round(float(portfolio.get('deployed_capital') or 0.0), 2)}"
        ),
        "",
        "Alerts:",
    ]
    if not alerts:
        lines.append("- no active alerts")
    else:
        for item in alerts[:12]:
            severity = str(item.get("severity") or "info").upper()
            title = str(item.get("title") or "Alert").strip()
            message = str(item.get("message") or "").strip()
            target = str(item.get("target") or "").strip()
            suffix = f" ({target})" if target else ""
            lines.append(f"- [{severity}] {title}{suffix}: {message}")
        remaining = len(alerts) - 12
        if remaining > 0:
            lines.append(f"- ... and {remaining} more")
    return subject, "\n".join(lines)


def format_cockpit_alert_email(*, cockpit: dict) -> tuple[str, str]:
    alerts = list(cockpit.get("alerts") or [])
    alert_summary = cockpit.get("alert_summary") or {}
    portfolio = cockpit.get("portfolio") or {}
    blocking_reasons = list(cockpit.get("blocking_reasons") or [])

    highest_severity = "info"
    if any(str(item.get("severity") or "") == "error" for item in alerts):
        highest_severity = "error"
    elif any(str(item.get("severity") or "") == "warning" for item in alerts):
        highest_severity = "warning"

    subject = (
        f"[CardFlip Autotrade] {highest_severity.upper()} "
        f"{int(alert_summary.get('count') or len(alerts))} active alerts"
    )
    lines = [
        f"Ready: {bool(cockpit.get('ready'))}",
        f"Alert count: {int(alert_summary.get('count') or len(alerts))}",
        f"Blocking reasons: {', '.join(blocking_reasons) if blocking_reasons else 'none'}",
        (
            "Portfolio: "
            f"remaining={float(portfolio.get('remaining_capital') or 0.0):.2f}, "
            f"deployed={float(portfolio.get('deployed_capital') or 0.0):.2f}, "
            f"limit={float(portfolio.get('capital_limit') or 0.0):.2f}"
        ),
        "",
        "Alerts:",
    ]
    if alerts:
        for item in alerts:
            priority = str(item.get("incident_priority") or "").strip().lower()
            priority_prefix = f"[{priority.upper()}] " if priority else ""
            lines.append(
                "- "
                f"[{str(item.get('severity') or 'info').upper()}] "
                f"{priority_prefix}{str(item.get('title') or 'Alert')}: "
                f"{str(item.get('message') or '').strip() or str(item.get('code') or '')}"
            )
    else:
        lines.append("- No active alerts")
    return subject, "\n".join(lines)


def format_cockpit_alert_webhook(*, cockpit: dict, alerts: list[dict] | None = None) -> dict:
    selected_alerts = list(alerts if alerts is not None else (cockpit.get("alerts") or []))
    text_lines = []
    for item in selected_alerts[:10]:
        priority = str(item.get("incident_priority") or "").strip().upper()
        priority_prefix = f"[{priority}] " if priority else ""
        text_lines.append(
            f"[{str(item.get('effective_severity') or item.get('severity') or 'info').upper()}] "
            f"{priority_prefix}"
            f"{str(item.get('title') or 'Alert')}: "
            f"{str(item.get('message') or '').strip()}"
        )
    return {
        "kind": "autotrade_alert_escalation",
        "channel": alert_webhook_provider(),
        "channel_label": alert_webhook_channel_label(),
        "ready": bool(cockpit.get("ready")),
        "blocking_reasons": list(cockpit.get("blocking_reasons") or []),
        "alert_summary": dict(cockpit.get("alert_summary") or {}),
        "portfolio": dict(cockpit.get("portfolio") or {}),
        "execution_readiness": dict(cockpit.get("execution_readiness") or {}),
        "operating_state": dict(cockpit.get("operating_state") or {}),
        "alerts": selected_alerts,
        "text": "\n".join(text_lines) if text_lines else "No active alerts",
    }
