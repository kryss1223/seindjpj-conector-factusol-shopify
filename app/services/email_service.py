import os
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
    - Limpia/formatea el reporte técnico antes de enviarlo por email.
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

        clean_body = self._format_report_body_for_email(body)

        payload = self._build_payload(
            subject=subject,
            body=clean_body,
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

    def _format_report_body_for_email(self, body: str) -> str:
        """
        Limpia el reporte técnico para hacerlo más entendible por negocio.

        Mantiene:
        - Cabecera
        - Fecha generación
        - Resumen
        - Detalle de pedidos
        - Acción recomendada

        Elimina:
        - Bloque técnico 'Motivo detectado'
        - error_message largo con código/debug
        """

        lines = body.splitlines()
        output: list[str] = []

        current_shopify_order_id: str | None = None
        skip_technical_reason = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("Shopify order id:"):
                current_shopify_order_id = stripped.replace("Shopify order id:", "").strip()

                output.append(f"ID pedido Shopify: {current_shopify_order_id}")
                output.append(
                    f"Link orden de compra: {self._build_shopify_order_url(current_shopify_order_id)}"
                )
                continue

            if stripped.startswith("Estado API:"):
                raw_status = stripped.replace("Estado API:", "").strip()
                output.append(f"Estado API: {self._translate_status(raw_status)}")
                continue

            if stripped == "Motivo detectado:":
                skip_technical_reason = True
                continue

            if skip_technical_reason:
                if stripped == "Acción recomendada:":
                    skip_technical_reason = False
                    output.append(line)
                continue

            output.append(line)

        return "\n".join(output)

    def _translate_status(self, status: str) -> str:
        status_map = {
            "manual_review_required": "Pendiente de revisión manual",
            "failed": "Fallido",
            "processing": "En procesamiento",
            "processed": "Procesado",
            "already_processed": "Ya procesado",
            "already_processing": "Ya en procesamiento",
        }

        return status_map.get(status, status)

    def _build_shopify_order_url(self, shopify_order_id: str | None) -> str:
        base_url = os.getenv("SHOPIFY_ADMIN_ORDER_BASE_URL")

        if not base_url:
            return "No configurado"

        if not shopify_order_id:
            return "No disponible"

        return f"{base_url.rstrip('/')}/{shopify_order_id}"