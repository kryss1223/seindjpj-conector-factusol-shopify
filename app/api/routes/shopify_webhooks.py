import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.schemas.shopify_order import ShopifyOrderPayload
from app.services.shopify_order_processor import ShopifyOrderProcessor
from app.services.shopify_security_service import verify_shopify_hmac

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/webhooks/shopify",
    tags=["Shopify Webhooks"],
)

@router.post("/orders-create")
async def orders_create(request: Request):
    """
    Precheck para Shopify orders/create.

    No crea pedidos en FactuSOL. Sirve para validar datos fiscales,
    cliente y productos antes de que el pedido quede pagado.
    """

    shopify_payload = await _parse_shopify_order_payload(
        request=request,
        event_name="orders/create",
        verify_hmac=settings.environment == "production",
    )

    result = await ShopifyOrderProcessor().precheck_order(shopify_payload)

    logger.info("Shopify orders/create precheck received")
    logger.info("Order ID: %s", shopify_payload.id)
    logger.info("Order name: %s", shopify_payload.name)
    logger.info("Financial status: %s", shopify_payload.financial_status)

    return {
        "received": True,
        "event": "orders/create",
        "order_id": shopify_payload.id,
        "order_name": shopify_payload.name,
        "status": result.get("status"),
        "result": result,
    }


@router.post("/orders-paid")
async def orders_paid(request: Request):
    """
    Endpoint productivo para Shopify orders/paid.

    Este es el camino que crea cliente/pedido en FactuSOL cuando el pedido
    ya esta pagado o aprobado manualmente como pagado en Shopify.
    """

    shopify_payload = await _parse_shopify_order_payload(
        request=request,
        event_name="orders/paid",
        verify_hmac=True,
    )

    if shopify_payload.financial_status and shopify_payload.financial_status != "paid":
        logger.warning(
            "orders/paid received with unexpected financial_status=%s",
            shopify_payload.financial_status,
        )

    result = await ShopifyOrderProcessor().process_paid_order(shopify_payload)

    logger.info("Shopify orders/paid received")
    logger.info("Order ID: %s", shopify_payload.id)
    logger.info("Order name: %s", shopify_payload.name)
    logger.info("Processing status: %s", result.get("status"))

    return {
        "received": True,
        "event": "orders/paid",
        "order_id": shopify_payload.id,
        "order_name": shopify_payload.name,
        "status": result.get("status"),
        "created": result.get("created"),
        "factusol_order_code": result.get("factusol_order_code"),
    }


async def _parse_shopify_order_payload(
    request: Request,
    event_name: str,
    verify_hmac: bool,
) -> ShopifyOrderPayload:
    raw_body = await request.body()

    if not raw_body:
        raise HTTPException(
            status_code=400,
            detail=f"Empty body received for {event_name}",
        )

    if verify_hmac:
        received_hmac = request.headers.get("X-Shopify-Hmac-Sha256")

        if not verify_shopify_hmac(raw_body, received_hmac):
            raise HTTPException(
                status_code=401,
                detail="Invalid Shopify webhook signature",
            )

    try:
        payload_dict = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON body for {event_name}",
        ) from exc

    try:
        return ShopifyOrderPayload.model_validate(payload_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid Shopify order payload for {event_name}: {exc}",
        ) from exc

