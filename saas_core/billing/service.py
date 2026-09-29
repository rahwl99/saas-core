import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from saas_core.config.settings import get_saas_settings
from saas_core.db.models import User, Plan, Subscription, WebhookEvent
from saas_core.credits.service import CreditService
from saas_core.billing.cashfree import CashfreeClient
from saas_core.exceptions import (
    BillingDisabledError,
    SubscriptionNotFoundError,
    WebhookVerificationError,
)

logger = logging.getLogger(__name__)


class BillingService:
    """
    Core billing service handling plans, checkouts, webhook idempotency,
    and automatic monthly credit allocations.
    """

    @classmethod
    def list_active_plans(cls, db: Session) -> List[Plan]:
        """Returns all currently active subscription plans."""
        stmt = select(Plan).where(Plan.active == True)
        return list(db.execute(stmt).scalars().all())

    @classmethod
    def get_plan_by_slug(cls, db: Session, slug: str) -> Optional[Plan]:
        stmt = select(Plan).where(Plan.slug == slug, Plan.active == True)
        return db.execute(stmt).scalar_one_or_none()

    @classmethod
    def get_user_subscription(cls, db: Session, user_id: str) -> Optional[Subscription]:
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["ACTIVE", "PENDING"])
        ).order_by(Subscription.created_at.desc())
        return db.execute(stmt).scalars().first()

    @classmethod
    async def create_checkout(
        cls,
        db: Session,
        user: User,
        plan_slug: str,
        return_url: Optional[str] = None,
        cashfree_client: Optional[CashfreeClient] = None,
    ) -> Dict[str, Any]:
        """
        Initiates a subscription checkout with Cashfree.
        """
        settings = get_saas_settings()
        if not settings.BILLING_ENABLED:
            raise BillingDisabledError("Billing features are disabled.")

        plan = cls.get_plan_by_slug(db, plan_slug)
        if not plan:
            raise ValueError(f"Plan with slug '{plan_slug}' not found or inactive")

        client = cashfree_client or CashfreeClient()

        # Generate a unique subscription reference
        sub_reference_id = f"sub_{uuid.uuid4().hex[:16]}"
        customer_id = f"cust_{user.id}"

        # If cashfree_plan_id is defined, call Cashfree API
        plan_id_for_cf = plan.cashfree_plan_id or plan.slug
        cf_response = await client.create_subscription(
            subscription_id=sub_reference_id,
            plan_id=plan_id_for_cf,
            customer_id=customer_id,
            customer_email=user.email or "user@example.com",
            customer_name=user.display_name,
            return_url=return_url,
        )

        # Record pending subscription locally
        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            cashfree_customer_id=customer_id,
            cashfree_subscription_id=sub_reference_id,
            status="PENDING",
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        return {
            "subscription_id": subscription.id,
            "cashfree_subscription_id": sub_reference_id,
            "payment_link": cf_response.get("payment_link") or cf_response.get("subscription_session_id"),
            "data": cf_response,
        }

    @classmethod
    async def cancel_subscription(
        cls,
        db: Session,
        user: User,
        cashfree_client: Optional[CashfreeClient] = None,
    ) -> Subscription:
        """
        Cancels the user's active subscription.
        """
        sub = cls.get_user_subscription(db, user.id)
        if not sub:
            raise SubscriptionNotFoundError("No active subscription found to cancel.")

        client = cashfree_client or CashfreeClient()
        if sub.cashfree_subscription_id:
            await client.cancel_subscription(sub.cashfree_subscription_id)

        sub.status = "CANCELLED"
        sub.cancel_at_period_end = True
        db.commit()
        db.refresh(sub)
        logger.info("Subscription cancelled for user_id=%s, sub_id=%s", user.id, sub.id)
        return sub

    @classmethod
    def process_cashfree_webhook(
        cls,
        db: Session,
        event_payload: Dict[str, Any],
        raw_body: bytes,
        signature: str,
        timestamp: str,
    ) -> Dict[str, Any]:
        """
        Verifies and idempotently handles Cashfree subscription and payment webhooks.
        Allocates monthly credits on successful recurring or initial payment.
        """
        settings = get_saas_settings()
        if not settings.BILLING_ENABLED:
            raise BillingDisabledError("Billing is disabled.")

        # 1. Verify webhook signature
        if not CashfreeClient.verify_webhook_signature(raw_body, signature, timestamp):
            logger.warning("Rejected webhook: invalid signature")
            raise WebhookVerificationError("Cashfree webhook signature verification failed")

        # 2. Extract event identifiers
        event_type = event_payload.get("type", "UNKNOWN")
        data = event_payload.get("data", {})
        
        # Determine unique event_id from payload (order_id, payment_id, or explicit event_id)
        event_id = (
            event_payload.get("event_id")
            or str(data.get("payment", {}).get("cf_payment_id"))
            or str(data.get("subscription", {}).get("cf_subscription_id"))
            or str(data.get("order", {}).get("order_id"))
        )

        if not event_id:
            # Fallback to hash of body if no clear id
            event_id = uuid.uuid5(uuid.NAMESPACE_DNS, raw_body.decode("utf-8", errors="ignore")).hex

        # 3. Check idempotency in webhook_events
        dup_stmt = select(WebhookEvent).where(
            WebhookEvent.provider == "cashfree",
            WebhookEvent.event_id == event_id,
        )
        existing_event = db.execute(dup_stmt).scalar_one_or_none()
        if existing_event and existing_event.processed:
            logger.info("Webhook already processed (idempotent no-op): %s", event_id)
            return {"status": "success", "message": "Already processed", "event_id": event_id}

        # 4. Handle event logic inside transaction
        webhook_record = existing_event or WebhookEvent(
            provider="cashfree",
            event_id=event_id,
            event_type=event_type,
            processed=False,
        )
        if not existing_event:
            db.add(webhook_record)
            db.flush()

        # Handle subscription payment success events
        # e.g., SUBSCRIPTION_PAYMENT_SUCCESS, PAYMENT_SUCCESS_WEBHOOK
        if "PAYMENT_SUCCESS" in event_type.upper() or "SUBSCRIPTION_CHARGED" in event_type.upper():
            sub_id = (
                data.get("subscription", {}).get("subscription_id")
                or data.get("subscription_id")
                or data.get("order", {}).get("order_tags", {}).get("subscription_id")
            )
            if sub_id:
                sub_stmt = select(Subscription).where(
                    Subscription.cashfree_subscription_id == sub_id
                )
                subscription = db.execute(sub_stmt).scalar_one_or_none()
                if subscription:
                    subscription.status = "ACTIVE"
                    # Grant plan credits to user
                    plan = db.execute(select(Plan).where(Plan.id == subscription.plan_id)).scalar_one_or_none()
                    if plan and plan.monthly_credits > 0:
                        CreditService.set_monthly_allocation(
                            db=db,
                            user_id=subscription.user_id,
                            monthly_credits=plan.monthly_credits,
                            reference_id=f"webhook_{event_id}",
                        )
                        logger.info(
                            "Granted %d monthly credits to user=%s via webhook event=%s",
                            plan.monthly_credits, subscription.user_id, event_id
                        )

        elif "PAYMENT_FAILED" in event_type.upper():
            sub_id = data.get("subscription", {}).get("subscription_id")
            if sub_id:
                sub_stmt = select(Subscription).where(Subscription.cashfree_subscription_id == sub_id)
                subscription = db.execute(sub_stmt).scalar_one_or_none()
                if subscription:
                    subscription.status = "PAST_DUE"

        elif "SUBSCRIPTION_CANCELLED" in event_type.upper():
            sub_id = data.get("subscription", {}).get("subscription_id")
            if sub_id:
                sub_stmt = select(Subscription).where(Subscription.cashfree_subscription_id == sub_id)
                subscription = db.execute(sub_stmt).scalar_one_or_none()
                if subscription:
                    subscription.status = "CANCELLED"

        # Mark processed
        webhook_record.processed = True
        webhook_record.processed_at = datetime.now(timezone.utc)
        db.commit()

        return {"status": "success", "event_id": event_id, "event_type": event_type}
