import base64
import hashlib
import hmac

from app.core.config import settings


def verify_shopify_hmac(raw_body: bytes, received_hmac: str | None) -> bool:
    if not received_hmac:
        return False

    digest = hmac.new(
        key=settings.shopify_api_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).digest()

    calculated_hmac = base64.b64encode(digest).decode("utf-8")

    return hmac.compare_digest(calculated_hmac, received_hmac)