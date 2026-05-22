from fastapi import FastAPI
from app.api.routes import health, shopify_webhooks
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Middleware API for Shopify and FactuSOL customer synchronization"
)

app.include_router(health.router)
app.include_router(shopify_webhooks.router)