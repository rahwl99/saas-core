import hmac
import hashlib
import base64
import logging
from typing import Dict, Any, Optional
import httpx

from saas_core.config.settings import get_saas_settings
from saas_core.exceptions import WebhookVerificationError

logger = logging.getLogger(__name__)


class CashfreeClient:
    """
    Encapsulates Cashfree Subscriptions & Payments API integration.
    Keeps all provider-specific HTTP calls cleanly isolated.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        environment: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        settings = get_saas_settings()
        self.client_id = client_id or settings.CASHFREE_CLIENT_ID
        self.client_secret = client_secret or settings.CASHFREE_CLIENT_SECRET
        self.environment = (environment or settings.CASHFREE_ENVIRONMENT).upper()
        self.api_version = api_version or settings.CASHFREE_API_VERSION

        if self.environment == "PRODUCTION":
            self.base_url = "https://api.cashfree.com/pg"
        else:
            self.base_url = "https://sandbox.cashfree.com/pg"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "x-client-id": self.client_id or "",
            "x-client-secret": self.client_secret or "",
            "x-api-version": self.api_version,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def create_subscription(
        self,
        subscription_id: str,
        plan_id: str,
        customer_id: str,
        customer_email: str,
        customer_phone: str = "9999999999",
        customer_name: Optional[str] = None,
        return_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a subscription order with Cashfree.
        """
        url = f"{self.base_url}/subscriptions"
        payload = {
            "subscription_id": subscription_id,
            "plan_details": {
                "plan_id": plan_id
            },
            "customer_details": {
                "customer_id": customer_id,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
                "customer_name": customer_name or "SaaS User",
            }
        }
        if return_url:
            payload["subscription_meta"] = {"return_url": return_url}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=self._get_headers())
            if response.status_code not in (200, 201):
                logger.error("Cashfree subscription create failed: %d %s", response.status_code, response.text)
                response.raise_for_status()
            return response.json()

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancels an active subscription in Cashfree.
        """
        url = f"{self.base_url}/subscriptions/{subscription_id}/cancel"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=self._get_headers())
            if response.status_code not in (200, 204):
                logger.error("Cashfree subscription cancel failed: %d %s", response.status_code, response.text)
                response.raise_for_status()
            return response.json() if response.text else {"status": "SUCCESS"}

    @staticmethod
    def verify_webhook_signature(
        raw_body: bytes,
        signature: str,
        timestamp: str,
        secret_key: Optional[str] = None,
    ) -> bool:
        """
        Verifies Cashfree webhook signature using HMAC-SHA256.
        Cashfree signature format: HMAC-SHA256(secret, timestamp + raw_body).
        Returns boolean.
        """
        if not signature or not timestamp:
            return False

        secret = secret_key or get_saas_settings().CASHFREE_WEBHOOK_SECRET
        if not secret:
            logger.error("Cannot verify Cashfree webhook: secret is not configured")
            return False

        payload_to_sign = timestamp.encode("utf-8") + raw_body
        expected_sig = base64.b64encode(
            hmac.new(secret.encode("utf-8"), payload_to_sign, hashlib.sha256).digest()
        ).decode("utf-8")

        # Compare constant-time
        return hmac.compare_digest(expected_sig, signature)
