"""Small SMTP adapter used for account verification and password recovery."""

import smtplib
from email.message import EmailMessage

from backend.app.core.smtp_credentials import get_smtp_configuration


def is_configured() -> bool:
    try:
        config = get_smtp_configuration()
    except RuntimeError:
        return False
    return bool(config["host"] and config["from_email"])


def send_security_email(recipient: str, subject: str, body: str) -> None:
    config = get_smtp_configuration()
    if not config["host"] or not config["from_email"]:
        raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL (or SMTP_USER) must be configured.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["from_email"]
    message["To"] = recipient
    message.set_content(body)
    with smtplib.SMTP(config["host"], config["port"], timeout=15) as server:
        if config["use_tls"]:
            server.starttls()
        if config["username"]:
            server.login(config["username"], config["password"])
        server.send_message(message)
