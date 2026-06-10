from typing import Any

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings


router = APIRouter(
    prefix="/admin/idempotency",
    tags=["Admin Idempotency"],
)


def _check_admin_token(x_admin_token: str | None) -> None:
    expected_token = settings.admin_debug_token

    if not expected_token:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_DEBUG_TOKEN is not configured",
        )

    if not x_admin_token or x_admin_token != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin token",
        )


def _get_database_url() -> str:
    database_url = settings.database_url

    if not database_url:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL is not configured",
        )

    return database_url


@router.get("/orders/recent")
def get_recent_processed_orders(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    limit: int = 20,
) -> dict[str, Any]:
    """
    Lista los últimos pedidos procesados por la idempotencia.
    """

    _check_admin_token(x_admin_token)

    safe_limit = max(1, min(limit, 100))
    database_url = _get_database_url()

    query = """
        SELECT
            shopify_order_id,
            shopify_order_name,
            status,
            factusol_order_code,
            error_message,
            created_at,
            updated_at
        FROM processed_shopify_orders
        ORDER BY updated_at DESC
        LIMIT %s
    """

    try:
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (safe_limit,))
                rows = cursor.fetchall()

        return {
            "ok": True,
            "count": len(rows),
            "orders": rows,
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": "Could not query processed_shopify_orders",
            "exception_type": type(exc).__name__,
            "exception_detail": str(exc),
        }


@router.get("/orders/{shopify_order_id}")
def get_processed_order(
    shopify_order_id: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """
    Consulta un pedido concreto por Shopify order id.
    """

    _check_admin_token(x_admin_token)
    database_url = _get_database_url()

    query = """
        SELECT
            shopify_order_id,
            shopify_order_name,
            status,
            factusol_order_code,
            error_message,
            created_at,
            updated_at
        FROM processed_shopify_orders
        WHERE shopify_order_id = %s
    """

    try:
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (shopify_order_id,))
                row = cursor.fetchone()

        return {
            "ok": True,
            "found": row is not None,
            "order": row,
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": "Could not query processed_shopify_orders",
            "exception_type": type(exc).__name__,
            "exception_detail": str(exc),
        }


@router.post("/orders/reset-processing")
def reset_processing_orders(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """
    Resetea pedidos zombis en estado processing.
    Los marca como failed para permitir reprocesarlos.
    """

    _check_admin_token(x_admin_token)
    database_url = _get_database_url()

    query = """
        UPDATE processed_shopify_orders
        SET status = 'failed',
            error_message = 'Manual reset: stale processing state',
            updated_at = CURRENT_TIMESTAMP
        WHERE status = 'processing'
        RETURNING
            shopify_order_id,
            shopify_order_name,
            status,
            factusol_order_code,
            error_message,
            created_at,
            updated_at
    """

    try:
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        return {
            "ok": True,
            "reset_count": len(rows),
            "orders": rows,
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": "Could not reset processing orders",
            "exception_type": type(exc).__name__,
            "exception_detail": str(exc),
        }


@router.post("/orders/{shopify_order_id}/mark-failed")
def mark_order_failed(
    shopify_order_id: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """
    Marca un pedido concreto como failed para poder reintentarlo.
    """

    _check_admin_token(x_admin_token)
    database_url = _get_database_url()

    query = """
        UPDATE processed_shopify_orders
        SET status = 'failed',
            error_message = 'Manual reset for retry',
            updated_at = CURRENT_TIMESTAMP
        WHERE shopify_order_id = %s
        RETURNING
            shopify_order_id,
            shopify_order_name,
            status,
            factusol_order_code,
            error_message,
            created_at,
            updated_at
    """

    try:
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (shopify_order_id,))
                row = cursor.fetchone()

        return {
            "ok": True,
            "updated": row is not None,
            "order": row,
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": "Could not mark order as failed",
            "exception_type": type(exc).__name__,
            "exception_detail": str(exc),
        }