from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from saas_core.db.session import get_db
from saas_core.db.models import User
from saas_core.auth.dependencies import get_current_user
from saas_core.credits.service import CreditService
from saas_core.exceptions import SaasCoreError
from saas_core.api.schemas import (
    BalanceResponse,
    ConsumeCreditsRequest,
    TransactionResponse,
)

router = APIRouter(prefix="/credits", tags=["Credits"])


@router.get("/balance", response_model=BalanceResponse)
def get_credit_balance(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the current credit balance of the authenticated user.
    """
    balance = CreditService.get_balance(db, user.id)
    return BalanceResponse(user_id=user.id, balance=balance)


@router.post("/consume", response_model=TransactionResponse)
def consume_credits(
    body: ConsumeCreditsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atomically consumes credits for an operation.
    """
    try:
        tx = CreditService.consume(
            db=db,
            user_id=user.id,
            amount=body.amount,
            transaction_type=body.transaction_type,
            reference_id=body.reference_id,
            description=body.description,
            metadata=body.metadata,
        )
        return tx
    except SaasCoreError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
