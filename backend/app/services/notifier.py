from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from ..config import settings


def send_alert_email(subject: str, body: str) -> bool:
    """
    Fire-and-forget SMTP email sender.
    Returns True if sent, False otherwise.
    """
    if not settings.alert_email_enabled:
        return False
    if not settings.alert_email_to or not settings.smtp_host or not settings.smtp_user:
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
