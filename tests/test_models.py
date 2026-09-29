from saas_core.db.models import User, Plan, Subscription, CreditAccount, CreditTransaction, TrialUsage, WebhookEvent


def test_models_creation(db_session):
    user = User(
        firebase_uid="fb_test_123",
        email="test@example.com",
        display_name="Test User"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.firebase_uid == "fb_test_123"
    assert user.trial_used is False

    # Plan creation
    plan = Plan(
        name="Pro Monthly",
        slug="pro-monthly",
        price=999.00,
        currency="INR",
        monthly_credits=100
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert plan.slug == "pro-monthly"
    assert plan.monthly_credits == 100

    # Credit account creation
    account = CreditAccount(
        user_id=user.id,
        balance=50
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    assert account.balance == 50
    assert user.credit_account.id == account.id
