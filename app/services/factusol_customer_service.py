from typing import Any

from app.services.factusol_api_service import FactusolApiService


class FactusolCustomerService:
    """
    Servicio específico para consultas de clientes en FactuSOL.
    """

    def __init__(self) -> None:
        self.api = FactusolApiService()

    async def get_customers_sample(self) -> dict[str, Any]:
        """
        Obtiene una muestra pequeña de clientes para inspeccionar columnas reales.
        """

        consulta = "SELECT TOP 3 * FROM F_CLI"
        return await self.api.launch_select_query(consulta)