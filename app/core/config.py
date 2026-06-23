from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    app_name: str = "Shopify FactuSOL Connector"
    environment: str = "local"

    shopify_client_id: str | None = None
    shopify_api_secret: str | None = None
    shopify_admin_order_base_url: str | None = None
    shopify_webhook_secret: str | None = None
    shopify_access_token: str | None = None
    shopify_shop_domain: str | None = None
    shopify_api_version: str = "2026-04"

    factusol_base_url: str | None = None
    factusol_login_path: str = "/login/autenticar"
    factusol_codigo_fabricante: int | None = None
    factusol_codigo_cliente: int | None = None
    factusol_base_datos_cliente: str | None = None
    factusol_password_b64: str | None = None
    factusol_read_only: bool = False
    factusol_query_path: str = "/admin/LanzarConsulta"
    factusol_write_path: str = "/admin/EscribirRegistro"
    factusol_fiscal_year: str = "2026"

    admin_debug_token: str | None = None
    enable_debug_routes: bool = False
    debug_responses: bool = False
    database_url: str | None = None
    sqlite_idempotency_path: str = "data/idempotency.db"

    report_email_enabled: bool = False
    report_email_from: str | None = None
    report_email_from_name: str = "SEIND Shopify Reports"
    report_email_to: str | None = None

    mailjet_api_key: str | None = None
    mailjet_secret_key: str | None = None
    mailjet_api_url: str = "https://api.mailjet.com/v3.1/send"


settings = Settings()
