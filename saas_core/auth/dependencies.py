import logging
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from saas_core.db.session import get_db
from saas_core.db.models import User, CreditAccount
from saas_core.auth.firebase import verify_firebase_id_token
from saas_core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


def get_or_sync_user(
    db: Session,
    firebase_uid: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None
) -> User:
    """
    Looks up a local user by firebase_uid. If absent, creates a new local user
    and initializes their credit account. If present, updates email/display_name if changed.
    """
    stmt = select(User).where(User.firebase_uid == firebase_uid)
    user = db.execute(stmt).scalar_one_or_none()

    if not user:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            display_name=display_name,
            status="active"
        )
        db.add(user)
        db.flush()

        # Ensure credit account exists for user
        credit_account = CreditAccount(user_id=user.id, balance=0)
        db.add(credit_account)
        db.commit()
        db.refresh(user)
        logger.info("Created new synchronized user: id=%s", user.id)
    else:
        # Check for profile updates
        changed = False
        if email is not None and user.email != email:
            user.email = email
            changed = True
        if display_name is not None and user.display_name != display_name:
            user.display_name = display_name
            changed = True
        if changed:
            db.commit()
            db.refresh(user)

    return user


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency that extracts Bearer token, verifies with Firebase,
    syncs with database, and returns the User model instance.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    id_token = parts[1]

    try:
        token_claims = verify_firebase_id_token(id_token)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    firebase_uid = token_claims.get("uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing uid claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = token_claims.get("email")
    display_name = token_claims.get("name")

    user = get_or_sync_user(db, firebase_uid=firebase_uid, email=email, display_name=display_name)
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or deleted"
        )

    return user
