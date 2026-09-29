import hmac
import hashlib
import base64
import json
import pytest
from unittest.mock import AsyncMock

from saas_core.db.models import User, Plan, Subscription, WebhookEvent
from saas_core.billing.service import BillingService
from saas_core.billing.cashfree import CashfreeClient
from saas_core.credits.service import CreditService
from saas_core.config.settings import get_saas_settings
from saas_core.exceptions import WebhookVerificationError, SubscriptionNotFoundError


def create_cf_signature(raw_body: bytes, timestamp: str, secret: str) -> str:
    payload = timestamp.encode("utf-8") + raw_body
    return base64.b64encode(hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()).decode("utf-8")


@pytest.mark.asyncio
async def test_create_checkout_and_subscription(db_session):
    user = User(firebase_uid="uid_bill_1", email="bill1@example.com")
    plan = Plan(
        name="Growth",
        slug="growth",
        price=1999.0,
        currency="INR",
        monthly_credits=500
    )
    db_session.add_all([user, plan])
    db_session.commit()

    mock_cf = CashfreeClient()
    mock_cf.create_subscription = AsyncMock(return_value={
        "subscription_id": "sub_cf_123",
        "payment_link": "https://payments.cashfree.com/sub_link"
    })

    result = await BillingService.create_checkout(
        db=db_session,
        user=user,
        plan_slug="growth",
        cashfree_client=mock_cf
    )

    assert result["payment_link"] == "https://payments.cashfree.com/sub_link"
    sub = BillingService.get_user_subscription(db_session, user.id)
    assert sub is not None
    assert sub.status == "PENDING"
    assert sub.plan_id == plan.id


@pytest.mark.asyncio
async def test_cancel_subscription(db_session):
    user = User(firebase_uid="uid_bill_2", email="bill2@example.com")
    plan = Plan(name="Starter", slug="starter", price=499.0, monthly_credits=100)
    db_session.add_all([user, plan])
    db_session.commit()

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        cashfree_subscription_id="cf_sub_to_cancel",
        status="ACTIVE"
    )
    db_session.add(sub)
    db_session.commit()

    mock_cf = CashfreeClient()
    mock_cf.cancel_subscription = AsyncMock(return_value={"status": "SUCCESS"})

    cancelled_sub = await BillingService.cancel_subscription(db_session, user, cashfree_client=mock_cf)
    assert cancelled_sub.status == "CANCELLED"
    assert cancelled_sub.cancel_at_period_end is True


def test_webhook_payment_success_and_credit_grant(db_session):
    settings = get_saas_settings()
    settings.CASHFREE_WEBHOOK_SECRET = "webhook_secret_key"

    user = User(firebase_uid="uid_bill_3", email="bill3@example.com")
    plan = Plan(name="Pro", slug="pro", price=999.0, monthly_credits=250)
    db_session.add_all([user, plan])
    db_session.commit()

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id,
        cashfree_subscription_id="cf_sub_success_1",
        status="PENDING"
    )
    db_session.add(sub)
    db_session.commit()

    payload = {
        "type": "SUBSCRIPTION_PAYMENT_SUCCESS",
        "event_id": "evt_cf_pay_1",
        "data": {
            "subscription": {
                "subscription_id": "cf_sub_success_1"
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    timestamp = "1672531199"
    sig = create_cf_signature(raw_body, timestamp, settings.CASHFREE_WEBHOOK_SECRET)

    # 1. First webhook execution -> should succeed and grant credits
    res = BillingService.process_cashfree_webhook(
        db=db_session,
        event_payload=payload,
        raw_body=raw_body,
        signature=sig,
        timestamp=timestamp,
    )
    assert res["status"] == "success"

    # Verify subscription is now ACTIVE
    db_session.refresh(sub)
    assert sub.status == "ACTIVE"

    # Verify monthly credits granted
    bal = CreditService.get_balance(db_session, user.id)
    assert bal == 250

    # 2. Duplicate webhook retry -> should be idempotent no-op and NOT double-grant
    res_dup = BillingService.process_cashfree_webhook(
        db=db_session,
        event_payload=payload,
        raw_body=raw_body,
        signature=sig,
        timestamp=timestamp,
    )
    assert res_dup["message"] == "Already processed"

    bal_after = CreditService.get_balance(db_session, user.id)
    assert bal_after == 250


def test_webhook_invalid_signature_rejected(db_session):
    settings = get_saas_settings()
    settings.CASHFREE_WEBHOOK_SECRET = "webhook_secret_key"

    raw_body = b'{"type":"TEST"}'
    with pytest.raises(WebhookVerificationError):
        BillingService.process_cashfree_webhook(
            db=db_session,
            event_payload={"type": "TEST"},
            raw_body=raw_body,
            signature="bad_signature",
            timestamp="123456789",
        )
