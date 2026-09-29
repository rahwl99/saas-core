from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session

from saas_core.db.session import get_db
from saas_core.db.models import User
from saas_core.auth.dependencies import get_current_user
from saas_core.trials.service import TrialService
from saas_core.abuse.trial_protection import extract_client_ip
from saas_core.config.settings import get_saas_settings
from saas_core.exceptions import SaasCoreError
from saas_core.api.schemas import ClaimTrialRequest, UserResponse, TrialStatusResponse

router = APIRouter(prefix="/trial", tags=["Trial"])


@router.get("/status", response_model=TrialStatusResponse)
def get_trial_status(user: User = Depends(get_current_user)):
    """
    Returns the user's trial status.
    """
    settings = get_saas_settings()
    if not settings.TRIAL_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trial system is disabled")

    is_active = TrialService.is_trial_active(user)
    return TrialStatusResponse(
        trial_active=is_active,
        trial_used=user.trial_used,
        trial_started_at=user.trial_started_at,
        trial_expires_at=user.trial_expires_at
    )


@router.post("/claim", response_model=UserResponse)
async def claim_trial(
    request: Request,
    body: ClaimTrialRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Claims the free trial for the authenticated user.
    """
    settings = get_saas_settings()
    if not settings.TRIAL_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trial system is disabled")

    client_ip = extract_client_ip(request, settings.TRUSTED_PROXIES)

    try:
        updated_user = await TrialService.claim_trial(
            db=db,
            user=user,
            client_ip=client_ip,
            turnstile_token=body.turnstile_token
        )
        return updated_user
    except SaasCoreError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
