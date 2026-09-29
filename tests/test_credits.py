import pytest
from saas_core.db.models import User
from saas_core.credits.service import CreditService
from saas_core.exceptions import InsufficientCreditsError


def test_credit_grant_and_balance(db_session):
    user = User(firebase_uid="uid_credit_1", email="credit1@example.com")
    db_session.add(user)
    db_session.commit()

    # Initial balance is 0
    bal = CreditService.get_balance(db_session, user.id)
    assert bal == 0

    # Grant 20 credits
    tx = CreditService.grant(
        db=db_session,
        user_id=user.id,
        amount=20,
        transaction_type="TRIAL_GRANT",
        reference_id="ref_trial_1",
        description="Welcome trial credits"
    )
    assert tx.amount == 20
    assert tx.balance_after == 20
    assert tx.transaction_type == "TRIAL_GRANT"

    bal = CreditService.get_balance(db_session, user.id)
    assert bal == 20


def test_credit_consume_success_and_ledger(db_session):
    user = User(firebase_uid="uid_credit_2", email="credit2@example.com")
    db_session.add(user)
    db_session.commit()

    CreditService.grant(db_session, user.id, 50, "INITIAL_PURCHASE")

    # Consume 15 credits
    tx = CreditService.consume(
        db=db_session,
        user_id=user.id,
        amount=15,
        transaction_type="USAGE",
        reference_id="task_abc",
        description="AI generation request"
    )
    assert tx.amount == -15
    assert tx.balance_after == 35

    bal = CreditService.get_balance(db_session, user.id)
    assert bal == 35


def test_credit_insufficient_balance(db_session):
    user = User(firebase_uid="uid_credit_3", email="credit3@example.com")
    db_session.add(user)
    db_session.commit()

    CreditService.grant(db_session, user.id, 10, "INITIAL_PURCHASE")

    with pytest.raises(InsufficientCreditsError):
        CreditService.consume(db_session, user.id, 15, "USAGE")

    # Balance must remain unchanged at 10
    bal = CreditService.get_balance(db_session, user.id)
    assert bal == 10


def test_credit_consume_idempotency(db_session):
    user = User(firebase_uid="uid_credit_4", email="credit4@example.com")
    db_session.add(user)
    db_session.commit()

    CreditService.grant(db_session, user.id, 100, "INITIAL_PURCHASE")

    # First consume call
    tx1 = CreditService.consume(
        db_session,
        user.id,
        amount=10,
        transaction_type="USAGE",
        reference_id="idemp_req_1"
    )
    assert tx1.balance_after == 90

    # Retry with same reference_id
    tx2 = CreditService.consume(
        db_session,
        user.id,
        amount=10,
        transaction_type="USAGE",
        reference_id="idemp_req_1"
    )
    assert tx2.id == tx1.id
    assert tx2.balance_after == 90

    # Balance should still be 90, not 80
    bal = CreditService.get_balance(db_session, user.id)
    assert bal == 90


def test_monthly_allocation_policy(db_session):
    user = User(firebase_uid="uid_credit_5", email="credit5@example.com")
    db_session.add(user)
    db_session.commit()

    CreditService.grant(db_session, user.id, 30, "INITIAL")
    CreditService.consume(db_session, user.id, 10, "USAGE")
    assert CreditService.get_balance(db_session, user.id) == 20

    # Monthly renewal resets/allocates monthly credits to 100 (non-rollover)
    tx = CreditService.set_monthly_allocation(
        db_session,
        user_id=user.id,
        monthly_credits=100,
        reference_id="sub_period_jan"
    )
    assert tx.balance_after == 100
    assert CreditService.get_balance(db_session, user.id) == 100
