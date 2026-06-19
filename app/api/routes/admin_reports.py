from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.core.config import settings
from app.services.factusol_order_failure_report_service import (
    FactusolOrderFailureReportService,
)
from app.services.email_service import EmailService


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
    


@router.post("/factusol-order-failures/send")
def send_factusol_order_failures_report(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    limit: int = Query(default=50, ge=1, le=200),
    send_when_empty: bool = Query(default=False),
) -> dict[str, Any]:
    """
    Genera y envía por email el reporte de pedidos no procesados en FactuSOL.

    Por defecto, si no hay incidencias, no envía email.
    """

    _check_admin_token(x_admin_token)

    try:
        report_service = FactusolOrderFailureReportService()
        report = report_service.build_report_preview(limit=limit)

        if not report.get("ok"):
            return report

        count = report.get("count", 0)

        if count == 0 and not send_when_empty:
            return {
                "ok": True,
                "sent": False,
                "reason": "No incidents found. Email was not sent.",
                "count": 0,
                "subject": report.get("subject"),
                "body": report.get("body"),
            }

        email_service = EmailService()
        email_result = email_service.send_plain_text_email(
            subject=report["subject"],
            body=report["body"],
        )

        return {
            "ok": email_result.get("sent") is True,
            "sent": email_result.get("sent") is True,
            "count": count,
            "subject": report.get("subject"),
            "email_result": email_result,
        }

    except Exception as exc:
        return {
            "ok": False,
            "sent": False,
            "error": "Could not send FactuSOL order failures report",
            "exception_type": type(exc).__name__,
            "exception_detail": str(exc),
        }