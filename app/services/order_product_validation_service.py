from typing import Any

from app.schemas.shopify_order import ShopifyOrderPayload
from app.services.factusol_product_service import FactusolProductService


async def validate_order_products_against_factusol(
    payload: ShopifyOrderPayload,
) -> dict[str, Any]:
    product_service = FactusolProductService()

    items_result = []
    has_errors = False

    for item in payload.line_items:
        sku = item.sku

        if not sku:
            has_errors = True
            items_result.append({
                "shopify_line_item_id": item.id,
                "shopify_product_id": item.product_id,
                "shopify_variant_id": item.variant_id,
                "title": item.title or item.name,
                "quantity": item.quantity,
                "price": item.price,
                "sku": None,
                "status": "product_missing_sku",
                "found_in_factusol": False,
                "reason": "Shopify line item has no SKU. Cannot map to FactuSOL article.",
            })
            continue

        lookup = await product_service.get_product_by_code(sku)

        if not lookup.get("found"):
            has_errors = True
            items_result.append({
                "shopify_line_item_id": item.id,
                "shopify_product_id": item.product_id,
                "shopify_variant_id": item.variant_id,
                "title": item.title or item.name,
                "quantity": item.quantity,
                "price": item.price,
                "sku": sku,
                "status": "product_not_found_in_factusol",
                "found_in_factusol": False,
                "reason": "No FactuSOL article found with Shopify SKU/CODART.",
            })
            continue

        factusol_product = lookup["product"]

        items_result.append({
            "shopify_line_item_id": item.id,
            "shopify_product_id": item.product_id,
            "shopify_variant_id": item.variant_id,
            "title": item.title or item.name,
            "quantity": item.quantity,
            "price": item.price,
            "sku": sku,
            "status": "product_verified",
            "found_in_factusol": True,
            "factusol_product_code": factusol_product.get("CODART"),
            "factusol_product_name": factusol_product.get("DESART"),
            "factusol_product_long_name": factusol_product.get("DLAART"),
            "ready_for_factusol_order_line": True,
        })

    return {
        "status": "products_review_required" if has_errors else "products_verified",
        "items_count": len(payload.line_items),
        "items": items_result,
    }