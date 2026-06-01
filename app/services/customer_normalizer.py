from app.schemas.normalized_customer import NormalizedCustomer
from app.schemas.shopify_order import ShopifyOrderPayload

"""
Legacy normalizer for Shopify customers/create.

The current FactuSOL integration flow is based on Shopify order webhooks,
not customer webhooks. This file is kept only for backwards compatibility.
"""

def normalize_shopify_customer(
    payload: ShopifyOrderPayload,
) -> NormalizedCustomer:
    address = payload.default_address

    full_name = " ".join(
        value for value in [payload.first_name, payload.last_name] if value
    ) or None

    return NormalizedCustomer(
        shopify_customer_id=str(payload.id),
        shopify_graphql_id=payload.admin_graphql_api_id,
        email=payload.email,
        phone=payload.phone or (address.phone if address else None),
        first_name=payload.first_name,
        last_name=payload.last_name,
        full_name=full_name,
        company=address.company if address else None,
        address1=address.address1 if address else None,
        address2=address.address2 if address else None,
        city=address.city if address else None,
        province=address.province if address else None,
        postal_code=address.zip if address else None,
        country=address.country if address else None,
    )