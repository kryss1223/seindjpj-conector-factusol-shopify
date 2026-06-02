import re
import unicodedata
from typing import Any

from app.schemas.normalized_customer import NormalizedCustomer


REQUIRED_CUSTOMER_FIELDS = [
    "fiscal_id",
    "fiscal_name",
    "fiscal_address",
    "fiscal_postal_code",
    "fiscal_city",
    "fiscal_province",
]


def validate_customer_against_factusol_lookup(
    customer: NormalizedCustomer,
    factusol_lookup: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Aplica reglas de negocio para determinar cómo tratar un cliente Shopify
    frente a FactuSOL.

    No crea clientes.
    No crea pedidos.
    Solo decide estado y acción recomendada.
    """

    missing_fields = _get_missing_required_fields(customer)

    if missing_fields:
        return {
            "status": "factusol_missing_data",
            "action": "manual_review_required",
            "reason": "Missing required fiscal data to validate or create customer.",
            "missing_fields": missing_fields,
            "checks": {},
        }

    if factusol_lookup is None:
        return {
            "status": "factusol_error",
            "action": "manual_review_required",
            "reason": "FactuSOL lookup result is not available.",
            "checks": {},
        }

    if "error" in factusol_lookup:
        return {
            "status": "factusol_error",
            "action": "manual_review_required",
            "reason": "FactuSOL lookup returned an error.",
            "error_detail": factusol_lookup.get("error"),
            "checks": {},
        }

    found = factusol_lookup.get("found", False)
    factusol_customer = factusol_lookup.get("customer")

    if not found or not factusol_customer:
        return {
            "status": "factusol_new_online",
            "action": "create_online_customer_with_default_conditions",
            "reason": "No customer found in FactuSOL with provided fiscal ID.",
            "checks": {
                "fiscal_id_exists": False,
            },
        }

    checks = _compare_customer_data(
        shopify_customer=customer,
        factusol_customer=factusol_customer,
    )

    if (
        checks["fiscal_id_matches"]
        and checks["fiscal_name_matches"]
        and checks["fiscal_address_matches"]
        and checks["postal_code_matches"]
    ):
        return {
            "status": "factusol_existing_verified",
            "action": "associate_order_to_existing_customer_with_online_conditions",
            "reason": "Customer exists in FactuSOL and main fiscal data matches.",
            "factusol_customer_code": factusol_customer.get("CODCLI"),
            "checks": checks,
            "commercial_conditions": {
                "apply_online_defaults": True,
                "apply_historical_discounts": False,
                "apply_special_rates": False,
                "apply_deferred_payment": False,
                "apply_commercial_credit": False,
            },
        }

    return {
        "status": "factusol_not_verified",
        "action": "manual_review_required",
        "reason": "Fiscal ID exists in FactuSOL but fiscal name/address data does not fully match.",
        "factusol_customer_code": factusol_customer.get("CODCLI"),
        "checks": checks,
        "commercial_conditions": {
            "apply_online_defaults": True,
            "apply_historical_discounts": False,
            "apply_special_rates": False,
            "apply_deferred_payment": False,
            "apply_commercial_credit": False,
        },
        "manual_flow": {
            "do_not_create_duplicate_customer": True,
            "do_not_associate_automatically": True,
            "allow_cart_download_or_sales_review": True,
            "max_validation_attempts": 3,
        },
    }


def _get_missing_required_fields(customer: NormalizedCustomer) -> list[str]:
    missing_fields = []

    for field_name in REQUIRED_CUSTOMER_FIELDS:
        value = getattr(customer, field_name, None)

        if value is None or str(value).strip() == "":
            missing_fields.append(field_name)

    return missing_fields


def _compare_customer_data(
    shopify_customer: NormalizedCustomer,
    factusol_customer: dict[str, Any],
) -> dict[str, bool]:
    shopify_fiscal_id = normalize_fiscal_id(shopify_customer.fiscal_id)
    factusol_fiscal_id = normalize_fiscal_id(factusol_customer.get("NIFCLI"))

    shopify_fiscal_name = normalize_text(shopify_customer.fiscal_name)
    factusol_fiscal_name = normalize_text(factusol_customer.get("NOFCLI"))

    shopify_address = normalize_text(shopify_customer.fiscal_address)
    factusol_address = normalize_text(factusol_customer.get("DOMCLI"))

    shopify_postal_code = normalize_postal_code(shopify_customer.fiscal_postal_code)
    factusol_postal_code = normalize_postal_code(factusol_customer.get("CPOCLI"))

    shopify_city = normalize_text(shopify_customer.fiscal_city)
    factusol_city = normalize_text(factusol_customer.get("POBCLI"))

    shopify_province = normalize_text(shopify_customer.fiscal_province)
    factusol_province = normalize_text(factusol_customer.get("PROCLI"))

    return {
        "fiscal_id_matches": shopify_fiscal_id == factusol_fiscal_id,
        "fiscal_name_matches": shopify_fiscal_name == factusol_fiscal_name,
        "fiscal_address_matches": shopify_address == factusol_address,
        "postal_code_matches": shopify_postal_code == factusol_postal_code,
        "city_matches": shopify_city == factusol_city,
        "province_matches": shopify_province == factusol_province,
    }


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip().lower()

    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))

    text = text.replace(".", "")
    text = text.replace(",", "")
    text = re.sub(r"\s+", " ", text)

    return text


def normalize_fiscal_id(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()


def normalize_postal_code(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(r"[^0-9]", "", str(value))