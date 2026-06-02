import json
import logging

from fastapi import APIRouter, Body, Request

from app.schemas.shopify_order import ShopifyOrderPayload
from app.services.shopify_order_normalizer import normalize_shopify_order_customer
from app.services.factusol_customer_service import FactusolCustomerService
from app.services.customer_validation_service import validate_customer_against_factusol_lookup

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
    - busca el cliente en FactuSOL por NIF/CIF
    - NO crea ni modifica nada en FactuSOL
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

    if normalized_customer.fiscal_id:
        factusol_customer_service = FactusolCustomerService()
        factusol_lookup = await factusol_customer_service.get_customer_by_fiscal_id(
            normalized_customer.fiscal_id
        )
    else:
        factusol_lookup = {
            "found": False,
            "customer": None,
            "reason": "Missing fiscal_id in normalized customer",
        }

    validation_result = validate_customer_against_factusol_lookup(
    customer=normalized_customer,
    factusol_lookup=factusol_lookup,
)

    logger.info("Shopify orders/create received")
    logger.info("Order ID: %s", shopify_payload.id)
    logger.info("Order name: %s", shopify_payload.name)
    logger.info("Financial status: %s", shopify_payload.financial_status)
    logger.info("Fiscal ID: %s", normalized_customer.fiscal_id)
    logger.info("FactuSOL customer found: %s", factusol_lookup.get("found"))

    return {
        "received": True,
        "event": "orders/create",
        "order_id": shopify_payload.id,
        "order_name": shopify_payload.name,
        "financial_status": shopify_payload.financial_status,
        "normalized_customer": normalized_customer.model_dump(),
        "factusol_lookup": factusol_lookup,
        "line_items_count": len(shopify_payload.line_items),
        "customer_validation": validation_result,
    }

