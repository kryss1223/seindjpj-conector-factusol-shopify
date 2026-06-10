import logging

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.shopify_webhooks import router as shopify_webhooks_router
from app.core.config import settings

logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Middleware API for Shopify and FactuSOL customer synchronization",
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Shopify FactuSOL Connector API running",
    }

app.include_router(health_router)
app.include_router(shopify_webhooks_router)

if settings.enable_debug_routes and settings.environment != "production":
    try:
        from app.api.routes.debug_factusol import router as debug_factusol_router
        from app.api.routes.debug_shopify import router as debug_shopify_router

        app.include_router(debug_factusol_router)
        app.include_router(debug_shopify_router)
    except ModuleNotFoundError:
        logger.warning("Debug routes are enabled but debug route modules are not present")


