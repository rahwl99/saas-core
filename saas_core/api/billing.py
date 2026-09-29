from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from saas_core.db.session import get_db
from saas_core.db.models import User
from saas_core.auth.dependencies import get_current_user
from saas_core.billing.service import BillingService
from saas_core.config.settings import get_saas_settings
from saas_core.exceptions import SaasCoreError
from saas_core.api.schemas import (
    PlanResponse,
    CheckoutRequest,
    CheckoutResponse,
    SubscriptionResponse,
)

router = APIRouter(prefix="/billing", tags=["Billing"])


def check_billing_enabled():
    if not get_saas_settings().BILLING_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Billing features are disabled"
        )


@router.get("/plans", response_model=List[PlanResponse], dependencies=[Depends(check_billing_enabled)])
def list_plans(db: Session = Depends(get_db)):
    """
    Returns available active subscription plans.
    """
    return BillingService.list_active_plans(db)


@router.post("/checkout", response_model=CheckoutResponse, dependencies=[Depends(check_billing_enabled)])
async def create_checkout_session(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a Cashfree subscription checkout session.
    """
    try:
        res = await BillingService.create_checkout(
            db=db,
            user=user,
            plan_slug=body.plan_slug,
            return_url=body.return_url
        )
        return CheckoutResponse(**res)
    except SaasCoreError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/subscription", response_model=SubscriptionResponse, dependencies=[Depends(check_billing_enabled)])
def get_user_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the user's active subscription if any.
    """
    sub = BillingService.get_user_subscription(db, user.id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found")
    return sub


@router.post("/cancel", response_model=SubscriptionResponse, dependencies=[Depends(check_billing_enabled)])
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancels the user's active subscription.
    """
    try:
        sub = await BillingService.cancel_subscription(db, user)
        return sub
    except SaasCoreError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
