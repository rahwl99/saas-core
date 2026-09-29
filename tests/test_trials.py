import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from saas_core.db.models import User, TrialUsage
from saas_core.trials.service import TrialService
from saas_core.credits.service import CreditService
from saas_core.config.settings import get_saas_settings
from saas_core.exceptions import TrialUnavailableError, TrialAlreadyUsedError


@pytest.mark.asyncio
async def test_trial_claim_success(db_session):
    user = User(firebase_uid="uid_trial_1", email="trial1@example.com")
    db_session.add(user)
    db_session.commit()

    claimed_user = await TrialService.claim_trial(
        db=db_session,
        user=user,
        client_ip="192.168.1.10"
    )

    assert claimed_user.trial_used is True
    assert claimed_user.trial_started_at is not None
    assert claimed_user.trial_expires_at is not None
    assert TrialService.is_trial_active(claimed_user) is True

    # Check that 10 credits were granted atomically
    bal = CreditService.get_balance(db_session, claimed_user.id)
    assert bal == 10

    # Check TrialUsage row exists
    usages = db_session.query(TrialUsage).all()
    assert len(usages) == 1
    assert usages[0].user_id == claimed_user.id


@pytest.mark.asyncio
async def test_trial_cannot_be_claimed_twice_same_account(db_session):
    user = User(firebase_uid="uid_trial_2", email="trial2@example.com")
    db_session.add(user)
    db_session.commit()

    await TrialService.claim_trial(db_session, user, client_ip="192.168.1.20")

    # Second claim attempt on same account
    with pytest.raises(TrialAlreadyUsedError):
        await TrialService.claim_trial(db_session, user, client_ip="192.168.1.20")


@pytest.mark.asyncio
async def test_trial_cannot_be_claimed_twice_same_identity(db_session):
    user1 = User(firebase_uid="uid_trial_3a", email="sameidentity@example.com")
    user2 = User(firebase_uid="uid_trial_3b", email="SAMEIDENTITY@example.com")
    db_session.add_all([user1, user2])
    db_session.commit()

    await TrialService.claim_trial(db_session, user1, client_ip="192.168.1.30")

    # Second user with same email (even with different case)
    with pytest.raises(TrialAlreadyUsedError):
        await TrialService.claim_trial(db_session, user2, client_ip="192.168.1.31")


@pytest.mark.asyncio
async def test_trial_ip_rate_limit(db_session):
    user1 = User(firebase_uid="uid_ip_1", email="ip1@example.com")
    user2 = User(firebase_uid="uid_ip_2", email="ip2@example.com")
    user3 = User(firebase_uid="uid_ip_3", email="ip3@example.com")
    db_session.add_all([user1, user2, user3])
    db_session.commit()

    same_ip = "203.0.113.42"

    # Default TRIAL_IP_MAX_TRIALS is 2
    await TrialService.claim_trial(db_session, user1, client_ip=same_ip)
    await TrialService.claim_trial(db_session, user2, client_ip=same_ip)

    # 3rd claim from same IP should be blocked
    with pytest.raises(TrialUnavailableError) as exc_info:
        await TrialService.claim_trial(db_session, user3, client_ip=same_ip)

    assert "limit reached" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_trial_disabled_behavior(db_session):
    settings = get_saas_settings()
    original_state = settings.TRIAL_ENABLED
    settings.TRIAL_ENABLED = False

    user = User(firebase_uid="uid_disabled", email="disabled@example.com")
    db_session.add(user)
    db_session.commit()

    try:
        with pytest.raises(TrialUnavailableError):
            await TrialService.claim_trial(db_session, user, client_ip="1.2.3.4")
    finally:
        settings.TRIAL_ENABLED = original_state
