from app.schemas.normalized_customer import NormalizedCustomer
from app.schemas.shopify_order import ShopifyOrderPayload
from app.services.shopify_attributes_extractor import extract_shopify_order_attributes


def normalize_shopify_order_customer(
    payload: ShopifyOrderPayload,
) -> NormalizedCustomer:
    """
    Normaliza el cliente de un pedido Shopify usando:
    - datos nativos del pedido
    - datos fiscales capturados en note_attributes/cart attributes
    """

    shopify_attributes = extract_shopify_order_attributes(payload)

    customer = payload.customer
    billing_address = payload.billing_address

    first_name = customer.first_name if customer else None
    last_name = customer.last_name if customer else None

    if not first_name and billing_address:
        first_name = billing_address.first_name

    if not last_name and billing_address:
        last_name = billing_address.last_name

    full_name = " ".join(
        value for value in [first_name, last_name] if value
    ) or None

    return NormalizedCustomer(
        shopify_customer_id=str(customer.id) if customer and customer.id else None,
        shopify_graphql_id=customer.admin_graphql_api_id if customer else None,
        shopify_order_id=str(payload.id),
        shopify_order_name=payload.name,

        email=(
            shopify_attributes.get("email")
            or payload.email
            or payload.contact_email
            or (customer.email if customer else None)
        ),
        phone=(
            shopify_attributes.get("phone")
            or payload.phone
            or (billing_address.phone if billing_address else None)
            or (customer.phone if customer else None)
        ),
        mobile_phone=shopify_attributes.get("mobile_phone"),
        contact_person=shopify_attributes.get("contact_person"),
        contact_phone=shopify_attributes.get("contact_phone"),

        first_name=first_name,
        last_name=last_name,
        full_name=full_name,

        fiscal_id=shopify_attributes.get("fiscal_id"),
        fiscal_name=shopify_attributes.get("fiscal_name"),
        commercial_name=shopify_attributes.get("commercial_name"),

        fiscal_address=shopify_attributes.get("fiscal_address"),
        fiscal_postal_code=shopify_attributes.get("fiscal_postal_code"),
        fiscal_city=shopify_attributes.get("fiscal_city"),
        fiscal_province=shopify_attributes.get("fiscal_province"),
        fiscal_country=shopify_attributes.get("fiscal_country"),

        company=billing_address.company if billing_address else None,
        address1=billing_address.address1 if billing_address else None,
        address2=billing_address.address2 if billing_address else None,
        city=billing_address.city if billing_address else None,
        province=billing_address.province if billing_address else None,
        postal_code=billing_address.zip if billing_address else None,
        country=billing_address.country if billing_address else None,

        iban=shopify_attributes.get("iban"),
        ccc=shopify_attributes.get("ccc"),
        bank_name=shopify_attributes.get("bank_name"),

        payment_method=shopify_attributes.get("payment_method"),
        payment_days=shopify_attributes.get("payment_days"),
        apply_tax=shopify_attributes.get("apply_tax"),
        tax_type=shopify_attributes.get("tax_type"),

        source="shopify",
    )