from typing import Any

import httpx

from app.core.config import settings
from app.services.factusol_api_service import FactusolApiService


class FactusolWriteService:
    """
    Servicio genérico para operaciones de escritura en FactuSOL.

    Importante:
    - No contiene lógica de cliente, pedido o artículo.
    - Solo sabe escribir registros en una tabla.
    - Usa FactusolApiService para obtener token.
    """

    def __init__(self) -> None:
        if not settings.factusol_base_url:
            raise ValueError("FACTUSOL_BASE_URL is not configured")

        self.base_url = settings.factusol_base_url.rstrip("/")
        self.api = FactusolApiService()

    async def write_record(
        self,
        table: str,
        record: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Inserta un registro en FactuSOL usando /admin/EscribirRegistro.

        Ejemplo de record:
        [
            {"columna": "CODCLI", "dato": 3},
            {"columna": "NIFCLI", "dato": "B00000003"},
            {"columna": "NOFCLI", "dato": "CLIENTE TEST S.L."}
        ]
        """

        self._validate_write_allowed()
        self._validate_table(table)
        self._validate_record(record)

        token = await self.api.get_token()

        url = f"{self.base_url}/{settings.factusol_write_path.lstrip('/')}"

        payload = {
            "ejercicio": settings.factusol_fiscal_year,
            "tabla": table,
            "registro": record,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
            )

        response_body = self._safe_json(response)

        return {
            "ok_http": response.is_success,
            "status_code": response.status_code,
            "url": str(response.url),
            "write_debug": {
                "ejercicio": payload["ejercicio"],
                "tabla": table,
                "columns": [item.get("columna") for item in record],
                "record_items_count": len(record),
                "token_present": bool(token),
                "token_length": len(token),
            },
            "response": response_body,
        }

    def _validate_write_allowed(self) -> None:
        """
        Bloquea escrituras si el entorno está en modo solo lectura.
        """

        if settings.factusol_read_only:
            raise RuntimeError(
                "FactuSOL is configured as read-only. Write operation blocked."
            )

    @staticmethod
    def _validate_table(table: str) -> None:
        if not table or not table.strip():
            raise ValueError("FactuSOL table is required")

        forbidden_chars = [";", " ", "'", '"']

        for char in forbidden_chars:
            if char in table:
                raise ValueError(f"Invalid character in FactuSOL table name: {char}")

    @staticmethod
    def _validate_record(record: list[dict[str, Any]]) -> None:
        if not record:
            raise ValueError("FactuSOL record cannot be empty")

        for item in record:
            if not isinstance(item, dict):
                raise ValueError("Each FactuSOL record item must be a dictionary")

            if "columna" not in item:
                raise ValueError("Each FactuSOL record item must include 'columna'")

            if "dato" not in item:
                raise ValueError("Each FactuSOL record item must include 'dato'")

            column = item.get("columna")

            if not column or not isinstance(column, str):
                raise ValueError("FactuSOL column name must be a non-empty string")

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return response.text