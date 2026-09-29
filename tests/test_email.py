import pytest
from unittest.mock import MagicMock
from saas_core.email.service import EmailService
from saas_core.config.settings import get_saas_settings


def test_email_enabled_sends_email():
    settings = get_saas_settings()
    settings.EMAIL_ENABLED = True

    mock_client = MagicMock()
    mock_client.send_email.return_value = {"id": "email_123"}

    res = EmailService.send_welcome_email(
        to_email="test@user.com",
        display_name="Charlie",
        client=mock_client
    )
    assert res == {"id": "email_123"}
    mock_client.send_email.assert_called_once()
    args, kwargs = mock_client.send_email.call_args
    assert args[0] == "test@user.com"
    assert "Welcome, Charlie!" in args[2]


def test_email_disabled_noop():
    settings = get_saas_settings()
    original_state = settings.EMAIL_ENABLED
    settings.EMAIL_ENABLED = False

    mock_client = MagicMock()
    try:
        res = EmailService.send_welcome_email(
            to_email="test@user.com",
            client=mock_client
        )
        assert res is None
        mock_client.send_email.assert_not_called()
    finally:
        settings.EMAIL_ENABLED = original_state
