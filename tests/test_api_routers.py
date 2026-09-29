import pytest
import json
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from saas_core.db.session import get_db
from saas_core.db.models import User, Plan
from saas_core.auth.dependencies import get_current_user
from saas_core.credits.service import CreditService
from saas_core.api.users import router as users_router
from saas_core.api.trial import router as trial_router
from saas_core.api.credits import router as credits_router
from saas_core.api.billing import router as billing_router
from saas_core.api.webhooks import router as webhooks_router
from saas_core.config.settings import get_saas_settings
from tests.test_billing import create_cf_signature


@pytest.fixture
def api_app(db_session):
    app = FastAPI(title="Host Test App")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(trial_router, prefix="/api/v1")
    app.include_router(credits_router, prefix="/api/v1")
    app.include_router(billing_router, prefix="/api/v1")
    app.include_router(webhooks_router, prefix="/api/v1")

    # Override get_db to use test in-memory session
    app.dependency_overrides[get_db] = lambda: db_session
    return app


def test_api_users_me_and_delete(api_app, db_session):
    user = User(firebase_uid="uid_api_1", email="api1@example.com", display_name="API User 1")
    db_session.add(user)
    db_session.commit()

    api_app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(api_app)

    # 1. GET /api/v1/users/me
    res = client.get("/api/v1/users/me")
    assert res.status_code == 200
    assert res.json()["email"] == "api1@example.com"

    # 2. DELETE /api/v1/users/me
    with patch("firebase_admin.auth.delete_user"):
        del_res = client.delete("/api/v1/users/me")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"
        assert "deleted_" in del_res.json()["email"]


def test_api_trial_claim_and_status(api_app, db_session):
    user = User(firebase_uid="uid_api_2", email="api2@example.com")
    db_session.add(user)
    db_session.commit()

    api_app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(api_app)

    # Check initial status
    status_res = client.get("/api/v1/trial/status")
    assert status_res.status_code == 200
    assert status_res.json()["trial_active"] is False
    assert status_res.json()["trial_used"] is False

    # Claim trial
    claim_res = client.post("/api/v1/trial/claim", json={})
    assert claim_res.status_code == 200
    assert claim_res.json()["trial_used"] is True

    # Check status again
    status_res2 = client.get("/api/v1/trial/status")
    assert status_res2.status_code == 200
    assert status_res2.json()["trial_active"] is True


def test_api_credits_balance_and_consume(api_app, db_session):
    user = User(firebase_uid="uid_api_3", email="api3@example.com")
    db_session.add(user)
    db_session.commit()

    api_app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(api_app)

    # Grant some credits
    CreditService.grant(db_session, user.id, 50, "PURCHASE")

    # GET /credits/balance
    res = client.get("/api/v1/credits/balance")
    assert res.status_code == 200
    assert res.json()["balance"] == 50

    # POST /credits/consume
    consume_res = client.post("/api/v1/credits/consume", json={
        "amount": 20,
        "transaction_type": "API_CALL",
        "reference_id": "call_123"
    })
    assert consume_res.status_code == 200
    assert consume_res.json()["balance_after"] == 30

    # Insufficient credits check
    fail_res = client.post("/api/v1/credits/consume", json={
        "amount": 100,
        "transaction_type": "API_CALL"
    })
    assert fail_res.status_code == 402


def test_api_billing_plans_and_webhook(api_app, db_session):
    settings = get_saas_settings()
    settings.CASHFREE_WEBHOOK_SECRET = "webhook_secret_key"

    plan = Plan(name="Starter", slug="starter", price=299.0, monthly_credits=50)
    db_session.add(plan)
    db_session.commit()

    client = TestClient(api_app)

    # GET /billing/plans
    plans_res = client.get("/api/v1/billing/plans")
    assert plans_res.status_code == 200
    assert len(plans_res.json()) >= 1
    assert plans_res.json()[0]["slug"] == "starter"

    # POST /webhooks/cashfree
    payload = {
        "type": "SUBSCRIPTION_PAYMENT_SUCCESS",
        "event_id": "evt_api_hook_1",
        "data": {}
    }
    raw_body = json.dumps(payload).encode("utf-8")
    timestamp = "1672531199"
    sig = create_cf_signature(raw_body, timestamp, settings.CASHFREE_WEBHOOK_SECRET)

    hook_res = client.post(
        "/api/v1/webhooks/cashfree",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": sig,
            "x-webhook-timestamp": timestamp
        }
    )
    assert hook_res.status_code == 200
    assert hook_res.json()["status"] == "success"
