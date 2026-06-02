from typing import Any

from app.services.factusol_api_service import FactusolApiService


class FactusolOrderInspectionService:
    """
    Servicio temporal para inspeccionar estructura real de pedidos,
    líneas de pedido, artículos y stock en FactuSOL.

    Solo lectura.
    """

    def __init__(self) -> None:
        self.api = FactusolApiService()

    async def get_customer_orders_sample(self) -> dict[str, Any]:
        consulta = """
        SELECT TOP 5 *
        FROM F_PCL
        ORDER BY CODPCL DESC
        """

        result = await self.api.launch_select_query(consulta)
        return self._normalize_query_result(result)

    async def get_customer_orders_by_customer_code(
        self,
        customer_code: int,
    ) -> dict[str, Any]:
        consulta = f"""
        SELECT TOP 5 *
        FROM F_PCL
        WHERE CLIPCL = {customer_code}
        ORDER BY CODPCL DESC
        """

        result = await self.api.launch_select_query(consulta)
        return self._normalize_query_result(result)

    async def get_articles_sample(self) -> dict[str, Any]:
        consulta = """
        SELECT TOP 5 *
        FROM F_ART
        """

        result = await self.api.launch_select_query(consulta)
        return self._normalize_query_result(result)

    async def get_article_by_code(
        self,
        article_code: str,
    ) -> dict[str, Any]:
        clean_code = self._clean_sql_value(article_code)

        consulta = f"""
        SELECT TOP 1 *
        FROM F_ART
        WHERE CODART = '{clean_code}'
        """

        result = await self.api.launch_select_query(consulta)
        return self._normalize_query_result(result)

    async def try_lines_table_sample(
        self,
        table_name: str,
    ) -> dict[str, Any]:
        """
        Permite probar posibles tablas de líneas de pedido.
        Ejemplo: F_LPC, F_LPL, F_LPE...
        """

        clean_table = self._clean_table_name(table_name)

        consulta = f"""
        SELECT TOP 5 *
        FROM {clean_table}
        """

        result = await self.api.launch_select_query(consulta)
        return self._normalize_query_result(result)

    async def try_order_lines_by_order_code(
        self,
        table_name: str,
        order_code: int,
    ) -> dict[str, Any]:
        """
        Prueba tabla candidata de líneas filtrando por posibles campos.
        Como no sabemos el nombre del campo de enlace, probaremos luego varias consultas.
        """

        clean_table = self._clean_table_name(table_name)

        # Primera hipótesis: CODLPC o PELLPC pueden variar.
        # Este método mejor lo usamos después de ver columnas.
        consulta = f"""
        SELECT TOP 10 *
        FROM {clean_table}
        """

        result = await self.api.launch_select_query(consulta)
        return self._normalize_query_result(result)

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
                "columns": list(normalized_records[0].keys()) if normalized_records else [],
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

    @staticmethod
    def _clean_table_name(value: str) -> str:
        clean_value = value.strip().upper()

        if not clean_value.startswith("F_"):
            raise ValueError("Only FactuSOL tables starting with F_ are allowed")

        forbidden_chars = [";", " ", "'", '"', "-", "/"]

        for char in forbidden_chars:
            if char in clean_value:
                raise ValueError(f"Invalid character in table name: {char}")

        return clean_value