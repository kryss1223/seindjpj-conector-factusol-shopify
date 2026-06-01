from app.schemas.shopify_order import ShopifyOrderPayload


SHOPIFY_ATTRIBUTE_KEYS = {
    "factusol_fiscal_id": "fiscal_id",
    "factusol_fiscal_name": "fiscal_name",
    "factusol_commercial_name": "commercial_name",
    "factusol_fiscal_address": "fiscal_address",
    "factusol_fiscal_postal_code": "fiscal_postal_code",
    "factusol_fiscal_city": "fiscal_city",
    "factusol_fiscal_province": "fiscal_province",
    "factusol_fiscal_country": "fiscal_country",
    "factusol_contact_person": "contact_person",
    "factusol_email": "email",
    "factusol_phone": "phone",
    "factusol_mobile_phone": "mobile_phone",
    "factusol_contact_phone": "contact_phone",
    "factusol_iban": "iban",
    "factusol_ccc": "ccc",
    "factusol_bank_name": "bank_name",
    "factusol_payment_method": "payment_method",
    "factusol_payment_days": "payment_days",
    "factusol_apply_tax": "apply_tax",
    "factusol_tax_type": "tax_type",
}


def extract_shopify_order_attributes(
    payload: ShopifyOrderPayload,
) -> dict[str, str | int | bool | None]:
    """
    Extrae los atributos personalizados enviados desde el carrito de Shopify.

    Entrada:
    - payload.note_attributes con claves tipo factusol_fiscal_id.

    Salida:
    - diccionario interno neutral con claves tipo fiscal_id.
    """

    raw_attributes = {
        attribute.name: attribute.value
        for attribute in payload.note_attributes
        if attribute.name
    }

    normalized_attributes: dict[str, str | int | bool | None] = {}

    for shopify_key, internal_key in SHOPIFY_ATTRIBUTE_KEYS.items():
        value = raw_attributes.get(shopify_key)

        if value is None:
            normalized_attributes[internal_key] = None
            continue

        normalized_attributes[internal_key] = _normalize_attribute_value(
            internal_key=internal_key,
            value=value,
        )

    return normalized_attributes


def _normalize_attribute_value(
    internal_key: str,
    value: str,
) -> str | int | bool | None:
    cleaned_value = value.strip()

    if cleaned_value == "":
        return None

    if internal_key == "payment_days":
        try:
            return int(cleaned_value)
        except ValueError:
            return None

    if internal_key == "apply_tax":
        return cleaned_value.lower() in {"true", "1", "yes", "si", "sí"}

    return cleaned_value