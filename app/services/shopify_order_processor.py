import logging
from typing import Any

from app.core.config import settings
from app.schemas.shopify_order import ShopifyOrderPayload
from app.services.customer_validation_service import validate_customer_against_factusol_lookup
from app.services.factusol_customer_service import FactusolCustomerService
from app.services.factusol_order_service import FactusolOrderService
from app.services.idempotency_service import IdempotencyService
from app.services.order_product_validation_service import validate_order_products_against_factusol
from app.services.shopify_order_normalizer import normalize_shopify_order_customer

logger = logging.getLogger(__name__)


class ShopifyOrderProcessor:
    """
    Orquesta el flujo Shopify -> FactuSOL sin cambiar la logica ya probada
    de clientes, productos y pedidos.
    """

    async def precheck_order(self, payload: ShopifyOrderPayload) -> dict[str, Any]:
        return await self._process(payload=payload, create_order=False)

    async def process_paid_order(self, payload: ShopifyOrderPayload) -> dict[str, Any]:
        idempotency = IdempotencyService()
        processing_state = idempotency.start_processing(
            shopify_order_id=str(payload.id),
            shopify_order_name=payload.name,
        )

        if processing_state["status"] == "already_processed":
            return {
                "status": "already_processed",
                "created": False,
                "shopify_order_id": payload.id,
                "shopify_order_name": payload.name,
                "factusol_order_code": processing_state.get("factusol_order_code"),
            }

        if processing_state["status"] == "already_processing":
            return {
                "status": "already_processing",
                "created": False,
                "shopify_order_id": payload.id,
                "shopify_order_name": payload.name,
            }

        try:
            result = await self._process(payload=payload, create_order=True)

            if result.get("status") == "processed":
                idempotency.mark_processed(
                    shopify_order_id=str(payload.id),
                    factusol_order_code=result.get("factusol_order_code"),
                )
            elif result.get("status") == "manual_review_required":
                idempotency.mark_manual_review(
                    shopify_order_id=str(payload.id),
                    error_message=self._build_manual_review_error_message(result),
                )
            else:
                idempotency.mark_failed(
                    shopify_order_id=str(payload.id),
                    error_message=result.get("reason") or "Order processing failed",
                )

            return result

        except Exception as exc:
            logger.exception("Shopify paid order processing failed")
            idempotency.mark_failed(
                shopify_order_id=str(payload.id),
                error_message=str(exc),
            )
            raise

    async def _process(
        self,
        payload: ShopifyOrderPayload,
        create_order: bool,
    ) -> dict[str, Any]:
        normalized_customer = normalize_shopify_order_customer(payload)

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

        product_validation = await validate_order_products_against_factusol(payload)

        if create_order:
            customer_action_result = await self._resolve_customer_action(
                validation_result=validation_result,
                normalized_customer=normalized_customer,
            )
        else:
            customer_action_result = self._plan_customer_action(validation_result)

        if create_order:
            customer_ready = (
                isinstance(customer_action_result, dict)
                and customer_action_result.get("factusol_customer_code") is not None
            )
        else:
            customer_ready = validation_result["status"] in {
                "factusol_existing_verified",
                "factusol_new_online",
            }
        products_ready = (
            isinstance(product_validation, dict)
            and product_validation.get("status") == "products_verified"
        )

        if not create_order:
            return self._build_precheck_response(
                payload=payload,
                normalized_customer=normalized_customer,
                factusol_lookup=factusol_lookup,
                validation_result=validation_result,
                customer_action_result=customer_action_result,
                product_validation=product_validation,
                customer_ready=customer_ready,
                products_ready=products_ready,
            )

        if not customer_ready or not products_ready:
            return {
                "status": "manual_review_required",
                "created": False,
                "reason": "Customer or products are not ready for FactuSOL order creation.",
                "shopify_order_id": payload.id,
                "shopify_order_name": payload.name,
                "customer_ready": customer_ready,
                "products_ready": products_ready,

                # Resumen rápido
                "customer_validation_status": validation_result.get("status"),
                "customer_validation_reason": validation_result.get("reason"),
                "product_validation_status": product_validation.get("status"),
                "product_items_count": product_validation.get("items_count"),

                # Detalle real para diagnóstico
                "customer_validation": validation_result,
                "customer_action_result": customer_action_result,
                "product_validation": product_validation,
            }

        order_service = FactusolOrderService()
        order_result = await order_service.create_customer_order(
            shopify_payload=payload,
            customer=normalized_customer,
            factusol_customer_code=customer_action_result["factusol_customer_code"],
            product_validation=product_validation,
        )

        if not order_result.get("created"):
            return {
                "status": "failed",
                "created": False,
                "reason": order_result.get("reason") or "FactuSOL order creation failed.",
                "shopify_order_id": payload.id,
                "shopify_order_name": payload.name,
                "factusol_order_result": self._debug_value(order_result),
            }

        return {
            "status": "processed",
            "created": True,
            "shopify_order_id": payload.id,
            "shopify_order_name": payload.name,
            "factusol_customer_code": customer_action_result["factusol_customer_code"],
            "factusol_order_code": order_result.get("factusol_order_code"),
            "factusol_order_result": self._debug_value(order_result),
        }

    async def _resolve_customer_action(
        self,
        validation_result: dict[str, Any],
        normalized_customer: Any,
    ) -> dict[str, Any]:
        if validation_result["status"] == "factusol_existing_verified":
            return {
                "action": "use_existing_factusol_customer",
                "factusol_customer_code": validation_result.get("factusol_customer_code"),
                "created": False,
            }

        if validation_result["status"] == "factusol_new_online":
            factusol_customer_service = FactusolCustomerService()
            return await factusol_customer_service.create_online_customer(
                normalized_customer
            )

        return {
            "action": "manual_review_required",
            "created": False,
            "reason": validation_result.get("reason"),
            "status": validation_result.get("status"),
        }
    @staticmethod
    def _build_manual_review_error_message(result: dict[str, Any]) -> str:
        parts = []

        reason = result.get("reason")
        if reason:
            parts.append(f"reason={reason}")

        if "customer_ready" in result:
            parts.append(f"customer_ready={result.get('customer_ready')}")

        if "products_ready" in result:
            parts.append(f"products_ready={result.get('products_ready')}")

        customer_validation = result.get("customer_validation") or {}
        if isinstance(customer_validation, dict):
            customer_status = customer_validation.get("status")
            customer_reason = customer_validation.get("reason")
            missing_fields = customer_validation.get("missing_fields")

            if customer_status:
                parts.append(f"customer_status={customer_status}")

            if customer_reason:
                parts.append(f"customer_reason={customer_reason}")

            if missing_fields:
                parts.append(f"missing_fields={missing_fields}")

        customer_action_result = result.get("customer_action_result") or result.get("customer_action") or {}
        if isinstance(customer_action_result, dict):
            action_status = customer_action_result.get("status")
            action_reason = customer_action_result.get("reason")
            action = customer_action_result.get("action")

            if action:
                parts.append(f"customer_action={action}")

            if action_status:
                parts.append(f"customer_action_status={action_status}")

            if action_reason:
                parts.append(f"customer_action_reason={action_reason}")

        product_validation = result.get("product_validation") or {}
        if isinstance(product_validation, dict):
            product_status = product_validation.get("status")
            items = product_validation.get("items") or []

            if product_status:
                parts.append(f"product_status={product_status}")

            bad_items = []

            for item in items:
                if not isinstance(item, dict):
                    continue

                item_status = item.get("status")

                if item_status and item_status != "product_verified":
                    bad_items.append({
                        "sku": item.get("sku"),
                        "title": item.get("title"),
                        "status": item_status,
                        "reason": item.get("reason"),
                    })

            if bad_items:
                parts.append(f"bad_items={bad_items}")

        if not parts:
            return "Manual review required but no detailed reason was provided."

        return " | ".join(str(part) for part in parts)
    @staticmethod
    def _plan_customer_action(validation_result: dict[str, Any]) -> dict[str, Any]:
        if validation_result["status"] == "factusol_existing_verified":
            return {
                "action": "use_existing_factusol_customer",
                "factusol_customer_code": validation_result.get("factusol_customer_code"),
                "created": False,
            }

        if validation_result["status"] == "factusol_new_online":
            return {
                "action": "create_online_customer_on_paid_order",
                "factusol_customer_code": None,
                "created": False,
            }

        return {
            "action": "manual_review_required",
            "created": False,
            "reason": validation_result.get("reason"),
            "status": validation_result.get("status"),
        }

    def _build_precheck_response(
        self,
        payload: ShopifyOrderPayload,
        normalized_customer: Any,
        factusol_lookup: dict[str, Any],
        validation_result: dict[str, Any],
        customer_action_result: dict[str, Any],
        product_validation: dict[str, Any],
        customer_ready: bool,
        products_ready: bool,
    ) -> dict[str, Any]:
        response = {
            "status": "ready_for_order_creation"
            if customer_ready and products_ready
            else "manual_review_required",
            "created": False,
            "shopify_order_id": payload.id,
            "shopify_order_name": payload.name,
            "financial_status": payload.financial_status,
            "customer_ready": customer_ready,
            "products_ready": products_ready,
            "factusol_customer_code": customer_action_result.get("factusol_customer_code"),
            "next_action": (
                "wait_for_orders_paid"
                if customer_ready and products_ready
                else "manual_review_required"
            ),
        }

        if settings.debug_responses:
            response.update(
                {
                    "normalized_customer": normalized_customer.model_dump(),
                    "factusol_lookup": factusol_lookup,
                    "customer_validation": validation_result,
                    "customer_action_result": customer_action_result,
                    "product_validation": product_validation,
                }
            )

        return response

    @staticmethod
    def _debug_value(value: Any) -> Any:
        return value if settings.debug_responses else None