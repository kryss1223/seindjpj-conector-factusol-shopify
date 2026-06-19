from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.core.config import settings
from app.services.factusol_order_failure_report_service import (
    FactusolOrderFailureReportService,
)


router = APIRouter(
    prefix="/admin/reports",
    tags=["Admin Reports"],
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


@router.get("/factusol-order-failures/preview")
def preview_factusol_order_failures_report(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """
    Genera una vista previa del reporte de pedidos no procesados en FactuSOL.

    No envía email.
    """

    _check_admin_token(x_admin_token)

    try:
        service = FactusolOrderFailureReportService()
        return service.build_report_preview(limit=limit)

    except Exception as exc:
        return {
            "ok": False,
            "error": "Could not build FactuSOL order failures report",
            "exception_type": type(exc).__name__,
            "exception_detail": str(exc),
        }