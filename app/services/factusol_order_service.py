from datetime import datetime
from typing import Any

from app.schemas.normalized_customer import NormalizedCustomer
from app.schemas.shopify_order import ShopifyOrderPayload
from app.services.factusol_api_service import FactusolApiService
from app.services.factusol_write_service import FactusolWriteService


class FactusolOrderService:
    """
    Servicio para crear pedidos de cliente en FactuSOL.

    Tablas:
    - F_PCL: cabecera del pedido
    - F_LPC: líneas del pedido
    """

    def __init__(self) -> None:
        self.api = FactusolApiService()
        self.writer = FactusolWriteService()

    async def create_customer_order(
        self,
        shopify_payload: ShopifyOrderPayload,
        customer: NormalizedCustomer,
        factusol_customer_code: int,
        product_validation: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Crea un pedido de cliente en FactuSOL.

        Precondiciones:
        - Cliente validado o creado.
        - Productos verificados contra F_ART.
        """

        if product_validation.get("status") != "products_verified":
            return {
                "created": False,
                "reason": "Products are not verified. Order creation blocked.",
                "product_validation_status": product_validation.get("status"),
            }

        order_code = await self.get_next_order_code()
        totals = self._calculate_order_totals(product_validation)

        header_record = self._map_order_header(
            order_code=order_code,
            shopify_payload=shopify_payload,
            customer=customer,
            factusol_customer_code=factusol_customer_code,
            totals=totals,
        )

        header_write_result = await self.writer.write_record(
            table="F_PCL",
            record=header_record,
        )

        if not self._is_factusol_write_ok(header_write_result):
            return {
                "created": False,
                "step": "header",
                "reason": "FactuSOL rejected order header creation.",
                "factusol_order_code": order_code,
                "header_record": header_record,
                "header_write_result": header_write_result,
            }

        lines_write_results = []

        for position, item in enumerate(product_validation["items"], start=1):
            line_record = self._map_order_line(
                order_code=order_code,
                position=position,
                item=item,
            )

            line_write_result = await self.writer.write_record(
                table="F_LPC",
                record=line_record,
            )

            if not self._is_factusol_write_ok(line_write_result):
                return {
                    "created": False,
                    "step": "line",
                    "reason": "FactuSOL rejected order line creation.",
                    "factusol_order_code": order_code,
                    "line_position": position,
                    "line_record": line_record,
                    "line_write_result": line_write_result,
                    "header_write_result": header_write_result,
                    "previous_lines_write_results": lines_write_results,
                }

            lines_write_results.append(line_write_result)

        created_header_lookup = await self.get_order_by_code(order_code)
        created_lines_lookup = await self.get_order_lines_by_code(order_code)

        return {
            "created": True,
            "factusol_order_code": order_code,
            "shopify_order_id": shopify_payload.id,
            "shopify_order_name": shopify_payload.name,
            "header_write_result": header_write_result,
            "lines_write_results": lines_write_results,
            "created_header_lookup": created_header_lookup,
            "created_lines_lookup": created_lines_lookup,
        }
    async def get_next_order_code(self) -> int:
        consulta = """
        SELECT TOP 1 CODPCL
        FROM F_PCL
        ORDER BY CODPCL DESC
        """

        result = await self.api.launch_select_query(consulta)
        normalized = self._normalize_query_result(result)

        records = normalized["factusol_response"]["records"]

        if not records:
            return 1

        last_code = records[0].get("CODPCL")

        if last_code is None:
            return 1

        return int(last_code) + 1

    async def get_order_by_code(self, order_code: int) -> dict[str, Any]:
        consulta = f"""
        SELECT TOP 1 *
        FROM F_PCL
        WHERE CODPCL = {order_code}
        """

        result = await self.api.launch_select_query(consulta)
        return self._normalize_query_result(result)

    async def get_order_lines_by_code(self, order_code: int) -> dict[str, Any]:
        consulta = f"""
        SELECT TOP 20 *
        FROM F_LPC
        WHERE CODLPC = {order_code}
        """

        result = await self.api.launch_select_query(consulta)
        return self._normalize_query_result(result)

    def _map_order_header(
        self,
        order_code: int,
        shopify_payload: ShopifyOrderPayload,
        customer: NormalizedCustomer,
        factusol_customer_code: int,
        totals: dict[str, float],
    ) -> list[dict[str, Any]]:
        today = datetime.now().strftime("%Y-%m-%dT00:00:00")

        return self._remove_empty_values([
            {"columna": "TIPPCL", "dato": "1"},
            {"columna": "CODPCL", "dato": order_code},
            {"columna": "REFPCL", "dato": shopify_payload.name or f"Shopify {shopify_payload.id}"},
            {"columna": "FECPCL", "dato": today},

            {"columna": "CLIPCL", "dato": factusol_customer_code},
            {"columna": "CNOPCL", "dato": customer.fiscal_name},
            {"columna": "CDOPCL", "dato": customer.fiscal_address},
            {"columna": "CPOPCL", "dato": customer.fiscal_city},
            {"columna": "CCPPCL", "dato": customer.fiscal_postal_code},
            {"columna": "CPRPCL", "dato": customer.fiscal_province},
            {"columna": "CNIPCL", "dato": customer.fiscal_id},
            {"columna": "TELPCL", "dato": customer.phone},

            {"columna": "ESTPCL", "dato": 0},
            {"columna": "ALMPCL", "dato": "GEN"},

            {"columna": "NET1PCL", "dato": totals["net_amount"]},
            {"columna": "BAS1PCL", "dato": totals["net_amount"]},
            {"columna": "PIVA1PCL", "dato": 21},
            {"columna": "IIVA1PCL", "dato": totals["vat_amount"]},
            {"columna": "TOTPCL", "dato": totals["total_amount"]},

            {"columna": "FOPPCL", "dato": "004"},
            {"columna": "USUPCL", "dato": 1},
            {"columna": "USMPCL", "dato": 1},
            {"columna": "CEMPCL", "dato": customer.email},
        ])

    def _map_order_line(
        self,
        order_code: int,
        position: int,
        item: dict[str, Any],
    ) -> list[dict[str, Any]]:
        quantity = float(item.get("quantity") or 0)
        unit_price = float(item.get("price") or 0)

        line_net = round(quantity * unit_price, 2)
        line_total_with_vat = round(line_net * 1.21, 2)

        return self._remove_empty_values([
            {"columna": "TIPLPC", "dato": "1"},
            {"columna": "CODLPC", "dato": order_code},
            {"columna": "POSLPC", "dato": position},

            {"columna": "ARTLPC", "dato": item.get("factusol_product_code")},
            {"columna": "DESLPC", "dato": item.get("factusol_product_name") or item.get("title")},
            {"columna": "CANLPC", "dato": quantity},

            {"columna": "DT1LPC", "dato": 0},
            {"columna": "DT2LPC", "dato": 0},
            {"columna": "DT3LPC", "dato": 0},

            {"columna": "PRELPC", "dato": unit_price},
            {"columna": "TOTLPC", "dato": line_net},

            {"columna": "PENLPC", "dato": quantity},
            {"columna": "IVALPC", "dato": 0},
            {"columna": "IINLPC", "dato": 1},

            {"columna": "PIVLPC", "dato": line_total_with_vat},
            {"columna": "TIVLPC", "dato": line_total_with_vat},
        ])

    @staticmethod
    def _calculate_order_totals(product_validation: dict[str, Any]) -> dict[str, float]:
        net_amount = 0.0

        for item in product_validation.get("items", []):
            quantity = float(item.get("quantity") or 0)
            unit_price = float(item.get("price") or 0)
            net_amount += quantity * unit_price

        net_amount = round(net_amount, 2)
        vat_amount = round(net_amount * 0.21, 2)
        total_amount = round(net_amount + vat_amount, 2)

        return {
            "net_amount": net_amount,
            "vat_amount": vat_amount,
            "total_amount": total_amount,
        }

    def _normalize_query_result(self, result: dict[str, Any]) -> dict[str, Any]:
        response = result.get("response", {})

        if not isinstance(response, dict):
            raw_records = []
            respuesta = None
        else:
            raw_records = response.get("resultado") or []
            respuesta = response.get("respuesta")

        normalized_records = [
            self._row_to_dict(row)
            for row in raw_records
            if isinstance(row, list)
        ]

        return {
            "ok_http": result.get("ok_http"),
            "status_code": result.get("status_code"),
            "url": result.get("url"),
            "query_debug": result.get("query_debug"),
            "factusol_response": {
                "respuesta": respuesta,
                "records_count": len(normalized_records),
                "records": normalized_records,
            },
        }

    @staticmethod
    def _row_to_dict(row: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            item.get("columna"): item.get("dato")
            for item in row
            if isinstance(item, dict) and item.get("columna") is not None
        }

    @staticmethod
    def _remove_empty_values(record: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned_record = []

        for item in record:
            value = item.get("dato")

            if value is None:
                continue

            if isinstance(value, str) and value.strip() == "":
                continue

            cleaned_record.append(item)

        return cleaned_record
    
    @staticmethod
    def _is_factusol_write_ok(write_result: dict[str, Any]) -> bool:
        response = write_result.get("response")
        return isinstance(response, dict) and response.get("respuesta") == "OK"