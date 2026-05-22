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
    shopify_access_token: str | None = None
    shopify_shop_domain: str | None = None
    shopify_api_version: str = "2026-04"


settings = Settings()