import logging
from typing import Optional, Dict, Any
import resend

from saas_core.config.settings import get_saas_settings

logger = logging.getLogger(__name__)


class ResendClient:
    """
    Lightweight wrapper around the official Resend Python SDK.
    """

    def __init__(self, api_key: Optional[str] = None):
        settings = get_saas_settings()
        self.api_key = api_key or settings.RESEND_API_KEY
        if self.api_key:
            resend.api_key = self.api_key

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        settings = get_saas_settings()
        sender = from_email or settings.RESEND_FROM_EMAIL

        params: resend.Emails.SendParams = {
            "from": sender,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }

        try:
            response = resend.Emails.send(params)
            logger.info("Resend email dispatched successfully: to=%s, subject=%s", to_email, subject)
            return response
        except Exception as e:
            logger.error("Failed to send email via Resend to %s: %s", to_email, str(e))
            raise
