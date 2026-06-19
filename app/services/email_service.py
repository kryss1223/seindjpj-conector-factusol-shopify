import smtplib
from email.message import EmailMessage
from typing import Any

from app.core.config import settings


class EmailService:
    """
    Servicio simple de envío de emails por SMTP.

    MVP:
    - Texto plano.
    - Destinatarios separados por coma.
    - Usa variables de entorno.
    """

    def send_plain_text_email(
        self,
        subject: str,
        body: str,
        to: str | None = None,
    ) -> dict[str, Any]:
        if not settings.report_email_enabled:
            return {
                "sent": False,
                "reason": "REPORT_EMAIL_ENABLED is false",
            }

        smtp_host = settings.smtp_host
        smtp_port = settings.smtp_port
        smtp_user = settings.smtp_user
        smtp_password = settings.smtp_password
        sender = settings.report_email_from
        recipients_raw = to or settings.report_email_to

        missing_settings = []

        if not smtp_host:
            missing_settings.append("SMTP_HOST")

        if not smtp_port:
            missing_settings.append("SMTP_PORT")

        if not smtp_user:
            missing_settings.append("SMTP_USER")

        if not smtp_password:
            missing_settings.append("SMTP_PASSWORD")

        if not sender:
            missing_settings.append("REPORT_EMAIL_FROM")

        if not recipients_raw:
            missing_settings.append("REPORT_EMAIL_TO")

        if missing_settings:
            return {
                "sent": False,
                "reason": "Missing email settings",
                "missing_settings": missing_settings,
            }

        recipients = [
            email.strip()
            for email in recipients_raw.split(",")
            if email.strip()
        ]

        if not recipients:
            return {
                "sent": False,
                "reason": "No valid recipients configured",
            }

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message.set_content(body)

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                if settings.smtp_use_tls:
                    server.starttls()

                server.login(smtp_user, smtp_password)
                server.send_message(message)

            return {
                "sent": True,
                "recipients": recipients,
                "subject": subject,
            }

        except Exception as exc:
            return {
                "sent": False,
                "reason": "SMTP send failed",
                "exception_type": type(exc).__name__,
                "exception_detail": str(exc),
            }