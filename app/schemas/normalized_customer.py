from pydantic import BaseModel


class NormalizedCustomer(BaseModel):
    # Shopify identity
    shopify_customer_id: str | None = None
    shopify_graphql_id: str | None = None
    shopify_order_id: str | None = None
    shopify_order_name: str | None = None

    # Basic contact
    email: str | None = None
    phone: str | None = None
    mobile_phone: str | None = None
    contact_person: str | None = None
    contact_phone: str | None = None

    # Personal/shopify fields
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None

    # Fiscal/customer identity
    fiscal_id: str | None = None
    fiscal_name: str | None = None
    commercial_name: str | None = None

    # Fiscal address
    fiscal_address: str | None = None
    fiscal_postal_code: str | None = None
    fiscal_city: str | None = None
    fiscal_province: str | None = None
    fiscal_country: str | None = None

    # Shopify billing/shipping fallback
    company: str | None = None
    address1: str | None = None
    address2: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    country: str | None = None

    # Bank/admin data
    iban: str | None = None
    ccc: str | None = None
    bank_name: str | None = None

    # Default commercial rules
    payment_method: str | None = None
    payment_days: int | None = None
    apply_tax: bool | None = None
    tax_type: str | None = None

    # Source
    source: str = "shopify"