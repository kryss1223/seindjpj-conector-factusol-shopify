from typing import Any

import httpx

from app.core.config import settings


class EmailService:
    """
    Servicio de envío de emails usando Mailjet Send API v3.1.

    MVP:
    - Texto plano.
    - Destinatarios separados por coma en REPORT_EMAIL_TO.
    - Autenticación Basic Auth con MAILJET_API_KEY / MAILJET_SECRET_KEY.
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

        missing_settings = self._get_missing_settings(to=to)

        if missing_settings:
            return {
                "sent": False,
                "reason": "Missing Mailjet email settings",
                "missing_settings": missing_settings,
            }

        recipients = self._parse_recipients(to or settings.report_email_to)

        if not recipients:
            return {
                "sent": False,
                "reason": "No valid recipients configured",
            }

        payload = self._build_payload(
            subject=subject,
            body=body,
            recipients=recipients,
        )

        try:
            response = httpx.post(
                settings.mailjet_api_url,
                auth=(settings.mailjet_api_key, settings.mailjet_secret_key),
                headers={
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            response_json: dict[str, Any] | None

            try:
                response_json = response.json()
            except Exception:
                response_json = None

            if response.status_code < 200 or response.status_code >= 300:
                return {
                    "sent": False,
                    "reason": "Mailjet API returned non-success status",
                    "status_code": response.status_code,
                    "response": response_json or response.text,
                }

            mailjet_status = self._extract_mailjet_status(response_json)

            if mailjet_status != "success":
                return {
                    "sent": False,
                    "reason": "Mailjet did not return success status",
                    "status_code": response.status_code,
                    "mailjet_status": mailjet_status,
                    "response": response_json,
                }

            return {
                "sent": True,
                "provider": "mailjet",
                "status_code": response.status_code,
                "recipients": [recipient["Email"] for recipient in recipients],
                "subject": subject,
                "response": response_json,
            }

        except httpx.TimeoutException as exc:
            return {
                "sent": False,
                "reason": "Mailjet API request timed out",
                "exception_type": type(exc).__name__,
                "exception_detail": str(exc),
            }

        except Exception as exc:
            return {
                "sent": False,
                "reason": "Mailjet API send failed",
                "exception_type": type(exc).__name__,
                "exception_detail": str(exc),
            }

    def _get_missing_settings(self, to: str | None = None) -> list[str]:
        missing_settings: list[str] = []

        if not settings.mailjet_api_key:
            missing_settings.append("MAILJET_API_KEY")

        if not settings.mailjet_secret_key:
            missing_settings.append("MAILJET_SECRET_KEY")

        if not settings.mailjet_api_url:
            missing_settings.append("MAILJET_API_URL")

        if not settings.report_email_from:
            missing_settings.append("REPORT_EMAIL_FROM")

        if not to and not settings.report_email_to:
            missing_settings.append("REPORT_EMAIL_TO")

        return missing_settings

    def _parse_recipients(self, recipients_raw: str | None) -> list[dict[str, str]]:
        if not recipients_raw:
            return []

        recipients = []

        for email in recipients_raw.split(","):
            clean_email = email.strip()

            if not clean_email:
                continue

            recipients.append({
                "Email": clean_email,
            })

        return recipients

    def _build_payload(
        self,
        subject: str,
        body: str,
        recipients: list[dict[str, str]],
    ) -> dict[str, Any]:
        return {
            "Messages": [
                {
                    "From": {
                        "Email": settings.report_email_from,
                        "Name": settings.report_email_from_name,
                    },
                    "To": recipients,
                    "Subject": subject,
                    "TextPart": body,
                }
            ]
        }

    def _extract_mailjet_status(
        self,
        response_json: dict[str, Any] | None,
    ) -> str | None:
        if not response_json:
            return None

        messages = response_json.get("Messages")

        if not isinstance(messages, list) or not messages:
            return None

        first_message = messages[0]

        if not isinstance(first_message, dict):
            return None

        return first_message.get("Status")