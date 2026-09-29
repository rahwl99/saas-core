import logging
from typing import Optional, Dict, Any
from saas_core.config.settings import get_saas_settings
from saas_core.email.resend import ResendClient

logger = logging.getLogger(__name__)


class EmailService:
    """
    Intentionally thin transactional email service for SaaS events:
    - welcome
    - trial_expiring
    - payment_success
    - payment_failed
    - subscription_cancelled

    No-ops gracefully when SAAS_EMAIL_ENABLED=false.
    """

    @classmethod
    def _is_enabled(cls) -> bool:
        return get_saas_settings().EMAIL_ENABLED

    @classmethod
    def send_welcome_email(
        cls,
        to_email: str,
        display_name: Optional[str] = None,
        client: Optional[ResendClient] = None,
    ) -> Optional[Dict[str, Any]]:
        if not cls._is_enabled():
            return None

        name = display_name or "there"
        subject = "Welcome to our platform!"
        html = f"<h1>Welcome, {name}!</h1><p>We're thrilled to have you on board.</p>"
        resend_client = client or ResendClient()
        return resend_client.send_email(to_email, subject, html)

    @classmethod
    def send_trial_expiring_email(
        cls,
        to_email: str,
        days_left: int = 1,
        client: Optional[ResendClient] = None,
    ) -> Optional[Dict[str, Any]]:
        if not cls._is_enabled():
            return None

        subject = f"Your free trial expires in {days_left} day(s)"
        html = f"<p>Your trial will expire soon. Upgrade your plan to keep using your credits seamlessly!</p>"
        resend_client = client or ResendClient()
        return resend_client.send_email(to_email, subject, html)

    @classmethod
    def send_payment_success_email(
        cls,
        to_email: str,
        amount: float,
        plan_name: str,
        client: Optional[ResendClient] = None,
    ) -> Optional[Dict[str, Any]]:
        if not cls._is_enabled():
            return None

        subject = "Payment received - Subscription active"
        html = f"<p>Thank you! Your payment for <strong>{plan_name}</strong> was successful.</p>"
        resend_client = client or ResendClient()
        return resend_client.send_email(to_email, subject, html)

    @classmethod
    def send_payment_failed_email(
        cls,
        to_email: str,
        plan_name: str,
        client: Optional[ResendClient] = None,
    ) -> Optional[Dict[str, Any]]:
        if not cls._is_enabled():
            return None

        subject = "Action Required: Payment failed for your subscription"
        html = f"<p>We were unable to process your payment for <strong>{plan_name}</strong>. Please update your payment method.</p>"
        resend_client = client or ResendClient()
        return resend_client.send_email(to_email, subject, html)

    @classmethod
    def send_subscription_cancelled_email(
        cls,
        to_email: str,
        plan_name: str,
        client: Optional[ResendClient] = None,
    ) -> Optional[Dict[str, Any]]:
        if not cls._is_enabled():
            return None

        subject = "Your subscription has been cancelled"
        html = f"<p>Your subscription to <strong>{plan_name}</strong> has been cancelled.</p>"
        resend_client = client or ResendClient()
        return resend_client.send_email(to_email, subject, html)
