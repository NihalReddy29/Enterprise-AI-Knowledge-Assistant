"""Async-friendly email sending via SMTP."""

import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True on success, False if SMTP is not configured."""
    settings = get_settings()
    if not _smtp_configured():
        logger.info("SMTP not configured; skipping email to %s: %s", to, subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_team_invite_email(
    to: str,
    team_name: str,
    inviter_name: str,
    invite_url: str,
) -> bool:
    """Send a team invitation email."""
    subject = f"You've been invited to join {team_name}"
    body = (
        f"Hi,\n\n"
        f"{inviter_name} has invited you to join the team \"{team_name}\" "
        f"on Enterprise AI Knowledge Assistant.\n\n"
        f"Open this link to respond:\n{invite_url}\n\n"
        f"This invitation expires in {get_settings().team_invite_expire_days} days."
    )
    return send_email(to, subject, body)
