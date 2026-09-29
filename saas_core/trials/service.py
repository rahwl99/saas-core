import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from saas_core.config.settings import get_saas_settings
from saas_core.db.models import User, TrialUsage
from saas_core.credits.service import CreditService
from saas_core.abuse.trial_protection import TrialAbuseService, hash_identifier
from saas_core.exceptions import (
    TrialUnavailableError,
    TrialAlreadyUsedError,
)

logger = logging.getLogger(__name__)


class TrialService:
    """
    Manages the lifecycle of free trials.
    Enforces atomic creation: trial status and credit grant succeed or fail together.
    """

    @classmethod
    def is_trial_active(cls, user: User) -> bool:
        """
        Determines whether a user has an active trial based on timestamps.
        No background expiration worker needed.
        """
        if not user.trial_started_at or not user.trial_expires_at:
            return False
        expires_at = user.trial_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < expires_at

    @classmethod
    def should_send_expiry_warning(cls, user: User, hours_before: int = 24) -> bool:
        """
        Check if user's trial is within warning window and still active.
        Exposed for host application scheduling/cron if desired.
        """
        if not cls.is_trial_active(user) or not user.trial_expires_at:
            return False
        now = datetime.now(timezone.utc)
        expires_at = user.trial_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        diff = expires_at - now
        return timedelta(0) < diff <= timedelta(hours=hours_before)

    @classmethod
    async def claim_trial(
        cls,
        db: Session,
        user: User,
        client_ip: str,
        turnstile_token: Optional[str] = None,
    ) -> User:
        """
        Claims a free trial atomically.
        1. Checks user trial status with row lock
        2. Evaluates abuse rules (email hash, IP count, Turnstile)
        3. Sets trial start/expiration timestamps
        4. Grants trial credits
        5. Records durable TrialUsage record
        All in one database transaction.
        """
        settings = get_saas_settings()

        if not settings.TRIAL_ENABLED:
            raise TrialUnavailableError("Free trial is currently disabled.")

        # Lock user row to prevent race conditions on simultaneous requests
        user_stmt = select(User).where(User.id == user.id).with_for_update()
        locked_user = db.execute(user_stmt).scalar_one()

        if locked_user.trial_used or locked_user.trial_started_at is not None:
            raise TrialAlreadyUsedError("A trial has already been claimed for this account.")

        if not locked_user.email:
            raise TrialUnavailableError("User email is required to claim a trial.")

        # Evaluate abuse rules
        is_eligible, reason = await TrialAbuseService.evaluate_eligibility(
            db=db,
            email=locked_user.email,
            client_ip=client_ip,
            turnstile_token=turnstile_token,
        )

        if not is_eligible:
            if reason == "IDENTITY_USED":
                raise TrialAlreadyUsedError("This email identity has already utilized a free trial.")
            elif reason == "IP_LIMIT_EXCEEDED":
                raise TrialUnavailableError("Trial limit reached for this network/IP.")
            elif reason in ("TURNSTILE_REQUIRED", "TURNSTILE_FAILED"):
                raise TrialUnavailableError("Captcha verification failed or required.")
            else:
                raise TrialUnavailableError(f"Trial unavailable: {reason}")

        # Atomic trial setup
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.TRIAL_DURATION_DAYS)

        locked_user.trial_started_at = now
        locked_user.trial_expires_at = expires_at
        locked_user.trial_used = True

        # Grant trial credits atomically within same flow
        CreditService.grant(
            db=db,
            user_id=locked_user.id,
            amount=settings.TRIAL_CREDITS,
            transaction_type="TRIAL_GRANT",
            reference_id=f"trial_init_{locked_user.id}",
            description=f"Welcome {settings.TRIAL_CREDITS} trial credits ({settings.TRIAL_DURATION_DAYS}-day trial)",
        )

        # Record durable trial usage (survives account deletion)
        identity_hash = hash_identifier(locked_user.email, settings.TRIAL_HASH_SECRET)
        ip_hash = hash_identifier(client_ip, settings.TRIAL_HASH_SECRET) if client_ip else None

        usage = TrialUsage(
            user_id=locked_user.id,
            identity_hash=identity_hash,
            ip_hash=ip_hash,
            trial_started_at=now,
        )
        db.add(usage)

        db.commit()
        db.refresh(locked_user)
        logger.info(
            "Free trial successfully claimed: user_id=%s, expires_at=%s",
            locked_user.id, expires_at.isoformat()
        )
        return locked_user
