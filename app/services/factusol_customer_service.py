from typing import Any

from app.services.factusol_api_service import FactusolApiService


class FactusolCustomerService:
    """
    Servicio específico para consultas de clientes en FactuSOL.

    Usa FactusolApiService para lanzar consultas SELECT,
    pero aquí ya trabajamos con lógica de clientes.
    """

    def __init__(self) -> None:
        self.api = FactusolApiService()

    async def get_customers_sample(self) -> dict[str, Any]:
        """
        Obtiene una muestra pequeña de clientes para inspeccionar columnas reales.
        """

        consulta = """
        SELECT TOP 3
            CODCLI,
            NIFCLI,
            NOFCLI,
            NOCCLI,
            DOMCLI,
            POBCLI,
            CPOCLI,
            PROCLI,
            TELCLI,
            MOVCLI,
            PCOCLI,
            EMACLI,
            BANCLI,
            SWFCLI
        FROM F_CLI
        """

        result = await self.api.launch_select_query(consulta)
        return self._normalize_query_result(result)

    async def get_customer_by_fiscal_id(self, fiscal_id: str) -> dict[str, Any]:
        """
        Busca un cliente en FactuSOL por NIF/CIF.

        Devuelve:
        - found: true/false
        - customer: dict con columnas FactuSOL si existe
        """

        clean_fiscal_id = self._clean_sql_value(fiscal_id)

        consulta = f"""
        SELECT TOP 1
            CODCLI,
            NIFCLI,
            NOFCLI,
            NOCCLI,
            DOMCLI,
            POBCLI,
            CPOCLI,
            PROCLI,
            TELCLI,
            MOVCLI,
            PCOCLI,
            EMACLI,
            BANCLI,
            SWFCLI
        FROM F_CLI
        WHERE NIFCLI = '{clean_fiscal_id}'
        """

        result = await self.api.launch_select_query(consulta)
        normalized_result = self._normalize_query_result(result)

        records = normalized_result["factusol_response"]["records"]

        if not records:
            return {
                "found": False,
                "customer": None,
                "raw_result": normalized_result,
            }

        return {
            "found": True,
            "customer": records[0],
            "raw_result": normalized_result,
        }

    def _normalize_query_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """
        Convierte el resultado de FactuSOL de formato:
        [
          [{"columna": "NIFCLI", "dato": "B00000001"}]
        ]

        a:
        [
          {"NIFCLI": "B00000001"}
        ]
        """

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
        """
        Limpieza mínima para evitar romper la query.

        Importante:
        La API solo permite SELECT, pero igualmente evitamos comillas simples.
        """

        return value.strip().replace("'", "''")