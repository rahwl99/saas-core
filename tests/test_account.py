import pytest
from unittest.mock import patch, MagicMock
from saas_core.db.models import User, TrialUsage
from saas_core.account.service import AccountService
from saas_core.trials.service import TrialService
from saas_core.exceptions import TrialAlreadyUsedError


@pytest.mark.asyncio
async def test_account_deletion_anonymizes_and_preserves_trial_ineligibility(db_session):
    email = "delete_me@example.com"
    user = User(firebase_uid="uid_del_1", email=email, display_name="John Doe")
    db_session.add(user)
    db_session.commit()

    # User claims trial first
    await TrialService.claim_trial(db_session, user, client_ip="127.0.0.1")

    # Verify TrialUsage row created
    usage = db_session.query(TrialUsage).filter_by(user_id=user.id).first()
    assert usage is not None

    # Delete account
    with patch("firebase_admin.auth.delete_user") as mock_fb_del:
        deleted_user = await AccountService.delete_and_anonymize_user(
            db=db_session,
            user=user,
            delete_firebase_user=True,
            cashfree_client=MagicMock()
        )
        mock_fb_del.assert_called_once_with("uid_del_1")

    # Verify user row anonymized
    assert deleted_user.status == "deleted"
    assert deleted_user.email != email
    assert "deleted_" in deleted_user.email
    assert deleted_user.display_name == "Deleted User"
    assert deleted_user.deleted_at is not None

    # Verify TrialUsage record survived
    surviving_usage = db_session.query(TrialUsage).first()
    assert surviving_usage is not None

    # If the user re-signs up with the same email under a new account, trial must still be DENIED
    new_user = User(firebase_uid="uid_del_new", email=email)
    db_session.add(new_user)
    db_session.commit()

    with pytest.raises(TrialAlreadyUsedError):
        await TrialService.claim_trial(db_session, new_user, client_ip="127.0.0.1")
