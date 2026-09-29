import json
import logging
from fastapi import APIRouter, Request, Header, Depends, HTTPException, status
from sqlalchemy.orm import Session

from saas_core.db.session import get_db
from saas_core.billing.service import BillingService
from saas_core.exceptions import SaasCoreError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/cashfree")
async def cashfree_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_signature: str = Header(None, alias="x-webhook-signature"),
    x_webhook_timestamp: str = Header(None, alias="x-webhook-timestamp"),
):
    """
    Receives and processes webhooks from Cashfree.
    Verifies HMAC signature and processes events idempotently.
    """
    if not x_webhook_signature or not x_webhook_timestamp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing webhook signature or timestamp headers",
        )

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    try:
        result = BillingService.process_cashfree_webhook(
            db=db,
            event_payload=payload,
            raw_body=raw_body,
            signature=x_webhook_signature,
            timestamp=x_webhook_timestamp,
        )
        return result
    except SaasCoreError as e:
        logger.warning("Webhook handling error: %s", e.message)
        raise HTTPException(status_code=e.status_code, detail=e.message)
