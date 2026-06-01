from typing import Any

import httpx

from app.core.config import settings


class FactusolApiService:
    """
    Servicio para conectar con la API de FactuSOL.

    Fase actual:
    - Autenticación contra FactuSOL.
    - Obtención interna de token.
    - No exponer token ni password en respuestas JSON.
    - Modo solo lectura.
    """

    def __init__(self) -> None:
        if not settings.factusol_base_url:
            raise ValueError("FACTUSOL_BASE_URL is not configured")

        self.base_url = settings.factusol_base_url.rstrip("/")
        self.login_path = settings.factusol_login_path

    async def authenticate(self) -> dict[str, Any]:
        """
        Realiza login contra FactuSOL.

        Devuelve información segura para debug, pero NO expone el token completo.
        """

        login_response = await self._login()

        token = self._extract_token(login_response["response_body"])

        return {
            "ok_http": login_response["ok_http"],
            "status_code": login_response["status_code"],
            "url": login_response["url"],
            "factusol_response": {
                "respuesta": self._get_response_status(login_response["response_body"]),
                "token_received": bool(token),
                "token_length": len(token) if token else 0,
                "token_preview": self._mask_value(token) if token else None,
            },
            "sent_payload_debug": login_response["sent_payload_debug"],
        }

    async def get_token(self) -> str:
        """
        Obtiene el token real para usarlo internamente en otras llamadas.

        Este método SÍ devuelve el token, pero solo para uso interno del servicio,
        nunca directamente en un endpoint debug.
        """

        login_response = await self._login()
        token = self._extract_token(login_response["response_body"])

        if not token:
            raise RuntimeError(
                f"FactuSOL login did not return token. Response: {login_response['response_body']}"
            )

        return token
    
    async def launch_select_query(self, consulta: str) -> dict[str, Any]:
        """
        Ejecuta una consulta SELECT contra FactuSOL usando /admin/LanzarConsulta.

        Este método es genérico:
        - No sabe si consulta clientes, artículos u otra tabla.
        - Solo lanza una SELECT validada.
        """

        self._validate_select_query(consulta)

        token = await self.get_token()

        url = f"{self.base_url}/{settings.factusol_query_path.lstrip('/')}"

        payload = {
            "ejercicio": settings.factusol_fiscal_year,
            "consulta": consulta,
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

        try:
            response_body = response.json()
        except Exception:
            response_body = response.text

        return {
            "ok_http": response.is_success,
            "status_code": response.status_code,
            "url": str(response.url),
            "query_debug": {
                "ejercicio": payload["ejercicio"],
                "consulta": consulta,
                "token_present": bool(token),
                "token_length": len(token),
            },
            "response": response_body,
        }

    def _validate_select_query(self, consulta: str) -> None:
        """
        Validación básica para evitar lanzar consultas peligrosas.
        Aunque la API diga que solo acepta SELECT, añadimos barrera propia.
        """

        normalized_query = consulta.strip().lower()

        if not normalized_query.startswith("select"):
            raise ValueError("Only SELECT queries are allowed")

        forbidden_words = [
            "insert",
            "update",
            "delete",
            "drop",
            "alter",
            "create",
            "truncate",
            "exec",
            "execute",
            "merge",
        ]

        for word in forbidden_words:
            if word in normalized_query:
                raise ValueError(f"Forbidden SQL keyword detected: {word}")

        if ";" in normalized_query:
            raise ValueError("Semicolons are not allowed in debug SQL queries")

    async def _login(self) -> dict[str, Any]:
        """
        Ejecuta la llamada real de login contra FactuSOL.
        """

        self._validate_login_settings()

        url = f"{self.base_url}/{self.login_path.lstrip('/')}"

        payload = {
            "codigoFabricante": settings.factusol_codigo_fabricante,
            "codigoCliente": settings.factusol_codigo_cliente,
            "baseDatosCliente": settings.factusol_base_datos_cliente,
            "password": settings.factusol_password_b64,
        }

        headers = {
            "Content-Type": "application/json",
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
            "sent_payload_debug": {
                "codigoFabricante": payload["codigoFabricante"],
                "codigoCliente": payload["codigoCliente"],
                "baseDatosCliente": payload["baseDatosCliente"],
                "password_present": bool(payload["password"]),
                "password_length": len(payload["password"]) if payload["password"] else 0,
            },
            "response_body": response_body,
        }

    def _validate_login_settings(self) -> None:
        """
        Valida que las variables necesarias estén configuradas.
        """

        missing_fields = []

        if settings.factusol_codigo_fabricante is None:
            missing_fields.append("FACTUSOL_CODIGO_FABRICANTE")

        if settings.factusol_codigo_cliente is None:
            missing_fields.append("FACTUSOL_CODIGO_CLIENTE")

        if not settings.factusol_base_datos_cliente:
            missing_fields.append("FACTUSOL_BASE_DATOS_CLIENTE")

        if not settings.factusol_password_b64:
            missing_fields.append("FACTUSOL_PASSWORD_B64")

        if missing_fields:
            raise ValueError(
                f"Missing FactuSOL settings: {', '.join(missing_fields)}"
            )

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return response.text

    @staticmethod
    def _get_response_status(response_body: Any) -> str | None:
        """
        Extrae el campo 'respuesta' de la respuesta de FactuSOL.
        """

        if isinstance(response_body, dict):
            return response_body.get("respuesta")

        return None

    @staticmethod
    def _extract_token(response_body: Any) -> str | None:
        """
        En el login de FactuSOL, el token parece venir en el campo 'resultado'
        cuando 'respuesta' es 'OK'.
        """

        if not isinstance(response_body, dict):
            return None

        if response_body.get("respuesta") != "OK":
            return None

        token = response_body.get("resultado")

        if not token:
            return None

        return str(token)

    @staticmethod
    def _mask_value(value: str | None) -> str | None:
        """
        Enmascara valores sensibles como tokens.
        """

        if not value:
            return None

        if len(value) <= 12:
            return "***"

        return f"{value[:6]}...{value[-6:]}"