import json

from fastapi import APIRouter, Body, Request


router = APIRouter(
    prefix="/webhooks/shopify",
    tags=["Shopify Webhooks"]
)


@router.post("/customers-create")
async def customers_create(request: Request):
    """
    Endpoint real para Shopify.
    Lee el body bruto porque más adelante necesitaremos validar HMAC.
    """
    raw_body = await request.body()

    if not raw_body:
        return {
            "received": False,
            "error": "Empty body received",
            "hint": "This endpoint expects Shopify to send a JSON webhook payload."
        }

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return {
            "received": False,
            "error": "Invalid JSON body",
            "raw_body": raw_body.decode("utf-8", errors="replace")
        }

    print("=== SHOPIFY CUSTOMERS_CREATE EVENT RECEIVED ===")
    print(payload)
    print("==============================================")

    return {
        "received": True,
        "event": "customers/create",
        "customer_id": payload.get("id"),
        "email": payload.get("email"),
        "admin_graphql_api_id": payload.get("admin_graphql_api_id"),
        "keys": list(payload.keys())
    }


@router.post("/customers-create/test")
async def customers_create_test(payload: dict = Body(...)):
    """
    Endpoint temporal para probar desde /docs.
    Este sí le dice a Swagger que debe enviar un JSON.
    """
    print("=== TEST CUSTOMERS_CREATE PAYLOAD ===")
    print(payload)
    print("=====================================")

    return {
        "received": True,
        "mode": "test_from_docs",
        "event": "customers/create",
        "customer_id": payload.get("id"),
        "email": payload.get("email"),
        "admin_graphql_api_id": payload.get("admin_graphql_api_id"),
        "keys": list(payload.keys())
    }