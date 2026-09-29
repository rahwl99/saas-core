from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from saas_core.db.session import get_db
from saas_core.db.models import User
from saas_core.auth.dependencies import get_current_user
from saas_core.account.service import AccountService
from saas_core.api.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(user: User = Depends(get_current_user)):
    """
    Returns the authenticated user's profile.
    """
    return user


@router.delete("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def delete_current_user_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes/anonymizes the authenticated user's account, cancels any active subscription,
    and removes Firebase identity where configured.
    """
    return await AccountService.delete_and_anonymize_user(db=db, user=user)
