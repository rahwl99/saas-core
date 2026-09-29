import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from firebase_admin import auth

from saas_core.db.models import User, Subscription
from saas_core.billing.service import BillingService
from saas_core.billing.cashfree import CashfreeClient

logger = logging.getLogger(__name__)


class AccountService:
    """
    Handles user account deletion and data anonymization.
    Guarantees:
    - Anonymizes PII (email, display_name, firebase_uid) in local users table
    - Deletes Firebase Auth user if configured
    - Automatically cancels any active subscription
    - Preserves immutable ledger transactions and TrialUsage records for system integrity and abuse deterrence
    """

    @classmethod
    async def delete_and_anonymize_user(
        cls,
        db: Session,
        user: User,
        delete_firebase_user: bool = True,
        cashfree_client: Optional[CashfreeClient] = None,
    ) -> User:
        user_id = user.id
        old_uid = user.firebase_uid

        # 1. Cancel active subscription if any
        try:
            active_sub = BillingService.get_user_subscription(db, user_id)
            if active_sub:
                await BillingService.cancel_subscription(
                    db=db,
                    user=user,
                    cashfree_client=cashfree_client
                )
                logger.info("Cancelled subscription for deleted user: %s", user_id)
        except Exception as e:
            logger.error("Error cancelling subscription during account deletion: %s", str(e))

        # 2. Delete user from Firebase Auth if requested
        if delete_firebase_user and old_uid:
            try:
                auth.delete_user(old_uid)
                logger.info("Deleted Firebase user with UID: %s", old_uid)
            except Exception as e:
                logger.warning("Could not delete user from Firebase (may not exist or mock env): %s", str(e))

        # 3. Anonymize user record locally
        anon_id = uuid.uuid4().hex[:12]
        user.firebase_uid = f"deleted_{anon_id}"
        user.email = f"deleted_{anon_id}@anonymized.local"
        user.display_name = "Deleted User"
        user.status = "deleted"
        user.deleted_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(user)

        logger.info("User account successfully anonymized and marked deleted: id=%s", user_id)
        return user
