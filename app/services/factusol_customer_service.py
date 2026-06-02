from typing import Any

from app.services.factusol_api_service import FactusolApiService
from app.schemas.normalized_customer import NormalizedCustomer
from app.services.factusol_write_service import FactusolWriteService


class FactusolCustomerService:
    """
    Servicio específico para consultas de clientes en FactuSOL.

    Usa FactusolApiService para lanzar consultas SELECT,
    pero aquí ya trabajamos con lógica de clientes.
    """

    def __init__(self) -> None:
        self.api = FactusolApiService()
        self.writer = FactusolWriteService()

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
    

    async def create_online_customer(
        self,
        customer: NormalizedCustomer,
    ) -> dict[str, Any]:
        """
        Crea un cliente nuevo online en FactuSOL.

        Importante:
        - Solo debe llamarse cuando la validación haya devuelto factusol_new_online.
        - Antes de crear, vuelve a comprobar que el NIF/CIF no existe.
        """

        if not customer.fiscal_id:
            raise ValueError("Cannot create FactuSOL customer without fiscal_id")

        existing_customer = await self.get_customer_by_fiscal_id(customer.fiscal_id)

        if existing_customer.get("found"):
            return {
                "created": False,
                "reason": "Customer already exists in FactuSOL",
                "customer": existing_customer.get("customer"),
            }

        next_customer_code = await self.get_next_customer_code()

        record = self._map_normalized_customer_to_factusol_record(
            customer=customer,
            customer_code=next_customer_code,
        )

        write_result = await self.writer.write_record(
            table="F_CLI",
            record=record,
        )

        created_lookup = await self.get_customer_by_fiscal_id(customer.fiscal_id)

        return {
            "created": True,
            "factusol_customer_code": next_customer_code,
            "write_result": write_result,
            "created_customer_lookup": created_lookup,
        }


    async def get_next_customer_code(self) -> int:
        consulta = """
        SELECT TOP 1 CODCLI
        FROM F_CLI
        ORDER BY CODCLI DESC
        """

        result = await self.api.launch_select_query(consulta)
        normalized_result = self._normalize_query_result(result)

        records = normalized_result["factusol_response"]["records"]

        if not records:
            return 1

        last_code = records[0].get("CODCLI")

        if last_code is None:
            return 1

        return int(last_code) + 1


    def _map_normalized_customer_to_factusol_record(
        self,
        customer: NormalizedCustomer,
        customer_code: int,
    ) -> list[dict[str, Any]]:
        """
        Mapea NormalizedCustomer a columnas conocidas de F_CLI.

        Solo usamos columnas ya inspeccionadas/confirmadas.
        """

        return self._remove_empty_values([
            {
                "columna": "CODCLI",
                "dato": customer_code,
            },
            {
                "columna": "NIFCLI",
                "dato": customer.fiscal_id,
            },
            {
                "columna": "NOFCLI",
                "dato": customer.fiscal_name,
            },
            {
                "columna": "NOCCLI",
                "dato": customer.commercial_name or customer.fiscal_name,
            },
            {
                "columna": "DOMCLI",
                "dato": customer.fiscal_address,
            },
            {
                "columna": "POBCLI",
                "dato": customer.fiscal_city,
            },
            {
                "columna": "CPOCLI",
                "dato": customer.fiscal_postal_code,
            },
            {
                "columna": "PROCLI",
                "dato": customer.fiscal_province,
            },
            {
                "columna": "TELCLI",
                "dato": customer.phone,
            },
            {
                "columna": "MOVCLI",
                "dato": customer.mobile_phone or customer.phone,
            },
            {
                "columna": "PCOCLI",
                "dato": customer.contact_person,
            },
            {
                "columna": "EMACLI",
                "dato": customer.email,
            },
            {
                "columna": "BANCLI",
                "dato": customer.bank_name,
            },
            {
                "columna": "SWFCLI",
                "dato": customer.iban,
            },
        ])


    @staticmethod
    def _remove_empty_values(record: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Evita mandar columnas con None o string vacío.
        """

        cleaned_record = []

        for item in record:
            value = item.get("dato")

            if value is None:
                continue

            if isinstance(value, str) and value.strip() == "":
                continue

            cleaned_record.append(item)

        return cleaned_record