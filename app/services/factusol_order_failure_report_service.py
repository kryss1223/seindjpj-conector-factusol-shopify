from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


class FactusolOrderFailureReportService:
    """
    Genera un reporte operativo de pedidos Shopify que no se han insertado
    correctamente en FactuSOL.

    MVP:
    - Lee processed_shopify_orders.
    - Filtra estados problemáticos.
    - Devuelve asunto + cuerpo de email en texto plano.
    - No envía email todavía.
    """

    def __init__(self) -> None:
        self.database_url = settings.database_url

    def build_report_preview(self, limit: int = 50) -> dict[str, Any]:
        orders = self._get_failed_or_pending_orders(limit=limit)

        subject = self._build_subject(orders)
        body = self._build_body(orders)

        return {
            "ok": True,
            "count": len(orders),
            "subject": subject,
            "body": body,
            "orders": orders,
        }

    def _get_failed_or_pending_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured")

        safe_limit = max(1, min(limit, 200))

        query = query = """
                SELECT
                    shopify_order_id,
                    shopify_order_name,
                    status,
                    factusol_order_code,
                    error_message,
                    created_at,
                    updated_at
                FROM processed_shopify_orders
                WHERE updated_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                AND (
                        status IN ('manual_review_required', 'failed')
                        OR (
                            status = 'processing'
                            AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 minutes'
                        )
                )
                ORDER BY updated_at DESC
                LIMIT %s
            """

        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (safe_limit,))
                rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def _build_subject(self, orders: list[dict[str, Any]]) -> str:
        if not orders:
            return "[SEIND Shopify] Reporte FactuSOL - Sin incidencias"

        return (
            f"[SEIND Shopify] Reporte FactuSOL - "
            f"{len(orders)} pedido(s) no procesado(s)"
        )

    def _build_body(self, orders: list[dict[str, Any]]) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines: list[str] = []

        lines.append("REPORTE DIARIO - PEDIDOS NO INSERTADOS EN FACTUSOL")
        lines.append("=================================================")
        lines.append("")
        lines.append(f"Fecha de generación: {now}")
        lines.append(f"Pedidos detectados: {len(orders)}")
        lines.append("")

        if not orders:
            lines.append("No se han detectado pedidos pendientes, fallidos o bloqueados.")
            return "\n".join(lines)

        summary = self._build_summary(orders)

        lines.append("RESUMEN")
        lines.append("-------")
        lines.append(f"Manual review required: {summary.get('manual_review_required', 0)}")
        lines.append(f"Failed: {summary.get('failed', 0)}")
        lines.append(f"Processing antiguo: {summary.get('processing', 0)}")
        lines.append("")

        lines.append("DETALLE DE PEDIDOS")
        lines.append("------------------")

        for index, order in enumerate(orders, start=1):
            lines.extend(self._build_order_block(index=index, order=order))

        lines.append("")
        lines.append("ACCIONES GENERALES RECOMENDADAS")
        lines.append("-------------------------------")
        lines.append(
            "- Si el error indica product_not_found_in_factusol, revisar que el SKU "
            "de Shopify exista en FactuSOL como CODART, REFART, EQUART o EANART."
        )
        lines.append(
            "- Si el error indica customer_ready=False, revisar los datos fiscales "
            "del cliente en Shopify y FactuSOL."
        )
        lines.append(
            "- Si el pedido aparece como processing antiguo, revisar logs de Render "
            "y reintentar el procesamiento si procede."
        )
        lines.append(
            "- Una vez corregida la causa, reintentar el pedido o generar uno nuevo "
            "según el procedimiento operativo definido."
        )

        return "\n".join(lines)

    def _build_summary(self, orders: list[dict[str, Any]]) -> dict[str, int]:
        summary: dict[str, int] = {}

        for order in orders:
            status = str(order.get("status") or "unknown")
            summary[status] = summary.get(status, 0) + 1

        return summary

    def _build_order_block(
        self,
        index: int,
        order: dict[str, Any],
    ) -> list[str]:
        shopify_order_name = order.get("shopify_order_name") or "N/A"
        shopify_order_id = order.get("shopify_order_id") or "N/A"
        status = order.get("status") or "N/A"
        factusol_order_code = order.get("factusol_order_code") or "No creado"
        created_at = self._format_datetime(order.get("created_at"))
        updated_at = self._format_datetime(order.get("updated_at"))
        error_message = order.get("error_message") or "Sin detalle de error"

        recommended_action = self._infer_recommended_action(error_message)

        return [
            "",
            f"{index}) Pedido {shopify_order_name}",
            "-" * (len(f"{index}) Pedido {shopify_order_name}")),
            f"Shopify order id: {shopify_order_id}",
            f"Estado API: {status}",
            f"Código pedido FactuSOL: {factusol_order_code}",
            f"Fecha registro API: {created_at}",
            f"Última actualización: {updated_at}",
            "",
            "Motivo detectado:",
            error_message,
            "",
            "Acción recomendada:",
            recommended_action,
            "",
        ]

    def _infer_recommended_action(self, error_message: str) -> str:
        normalized_error = error_message.lower()

        if "product_not_found_in_factusol" in normalized_error:
            return (
                "Revisar el SKU del producto en Shopify y confirmar que existe "
                "en FactuSOL como CODART, REFART, EQUART o EANART."
            )

        if "products_ready=false" in normalized_error:
            return (
                "Revisar la validación de productos. Puede haber SKU vacío, "
                "producto inexistente en FactuSOL o mapeo incorrecto."
            )

        if "customer_ready=false" in normalized_error:
            return (
                "Revisar los datos fiscales/contacto del cliente y su coincidencia "
                "con FactuSOL."
            )

        if "processing" in normalized_error:
            return (
                "Revisar si el pedido quedó bloqueado en procesamiento. Consultar logs "
                "y resetear/reintentar si procede."
            )

        return (
            "Revisar el detalle técnico del error y contrastar el pedido en Shopify, "
            "FactuSOL y logs de Render."
        )

    def _format_datetime(self, value: Any) -> str:
        if value is None:
            return "N/A"

        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")

        return str(value)