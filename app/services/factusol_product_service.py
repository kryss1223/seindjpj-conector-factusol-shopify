from typing import Any

from app.services.factusol_api_service import FactusolApiService


class FactusolProductService:
    """
    Servicio específico para consultar artículos en FactuSOL.

    V1:
    - Shopify line_item.sku debe coincidir con F_ART.CODART.
    """

    def __init__(self) -> None:
        self.api = FactusolApiService()

    async def get_product_by_code(self, product_code: str) -> dict[str, Any]:
        clean_code = self._clean_sql_value(product_code)

        consulta = f"""
            SELECT TOP 1 *
            FROM F_ART
            WHERE CODART = '{clean_code}'
            OR REFART = '{clean_code}'
            OR EQUART = '{clean_code}'
            OR EANART = '{clean_code}'
        """

        result = await self.api.launch_select_query(consulta)
        normalized_result = self._normalize_query_result(result)

        records = normalized_result["factusol_response"]["records"]

        if not records:
            return {
                "found": False,
                "product": None,
                "raw_result": normalized_result,
                "lookup_strategy": "CODART_OR_REFART_OR_EQUART_OR_EANART",
                "searched_code": product_code,
            }

        product = records[0]

        return {
            "found": True,
            "product": product,
            "raw_result": normalized_result,
            "lookup_strategy": "CODART_OR_REFART_OR_EQUART_OR_EANART",
            "searched_code": product_code,
            "matched_factusol_codart": product.get("CODART"),
            "matched_factusol_refart": product.get("REFART"),
            "matched_factusol_equart": product.get("EQUART"),
            "matched_factusol_eanart": product.get("EANART"),
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
    def _clean_sql_value(value: str) -> str:
        return value.strip().replace("'", "''")