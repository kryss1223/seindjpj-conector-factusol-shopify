import json
import logging

from fastapi import APIRouter, Body, Request

from app.schemas.shopify_order import ShopifyOrderPayload
from app.services.shopify_order_normalizer import normalize_shopify_order_customer


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/webhooks/shopify",
    tags=["Shopify Webhooks"],
)


@router.post("/orders-create")
async def orders_create(request: Request):
    """
    Endpoint real para Shopify orders/create.

    De momento:
    - recibe el pedido
    - valida el payload
    - normaliza el cliente
    - NO llama a FactuSOL todavía
    """

    raw_body = await request.body()

    if not raw_body:
        return {
            "received": False,
            "event": "orders/create",
            "error": "Empty body received",
        }

    try:
        payload_dict = json.loads(raw_body)
    except json.JSONDecodeError:
        return {
            "received": False,
            "event": "orders/create",
            "error": "Invalid JSON body",
        }

    try:
        shopify_payload = ShopifyOrderPayload.model_validate(payload_dict)
    except Exception as exc:
        return {
            "received": False,
            "event": "orders/create",
            "error": "Invalid Shopify order payload",
            "details": str(exc),
        }

    normalized_customer = normalize_shopify_order_customer(shopify_payload)

    logger.info("Shopify orders/create received")
    logger.info("Order ID: %s", shopify_payload.id)
    logger.info("Order name: %s", shopify_payload.name)
    logger.info("Financial status: %s", shopify_payload.financial_status)
    logger.info("Fiscal ID: %s", normalized_customer.fiscal_id)

    return {
        "received": True,
        "event": "orders/create",
        "order_id": shopify_payload.id,
        "order_name": shopify_payload.name,
        "financial_status": shopify_payload.financial_status,
        "normalized_customer": normalized_customer.model_dump(),
        "line_items_count": len(shopify_payload.line_items),
    }


@router.post("/orders-create/test")
async def orders_create_test(payload: dict = Body(...)):
    """
    Endpoint temporal para probar desde /docs con un payload real de Shopify.

    No llama a FactuSOL.
    Solo valida el schema y normaliza el cliente.
    """

    try:
        shopify_payload = ShopifyOrderPayload.model_validate(payload)
    except Exception as exc:
        return {
            "received": False,
            "mode": "test_from_docs",
            "event": "orders/create",
            "error": "Invalid Shopify order payload",
            "details": str(exc),
        }

    normalized_customer = normalize_shopify_order_customer(shopify_payload)

    return {
        "received": True,
        "mode": "test_from_docs",
        "event": "orders/create",
        "order_id": shopify_payload.id,
        "order_name": shopify_payload.name,
        "financial_status": shopify_payload.financial_status,
        "normalized_customer": normalized_customer.model_dump(),
        "line_items_count": len(shopify_payload.line_items),
    }