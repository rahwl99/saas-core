import hmac
import hashlib
import ipaddress
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import Request

from saas_core.config.settings import get_saas_settings
from saas_core.db.models import TrialUsage
from saas_core.exceptions import TrialUnavailableError

logger = logging.getLogger(__name__)


def hash_identifier(value: str, secret: str) -> str:
    """
    Computes keyed HMAC-SHA256 of a normalized identifier.
    Never stores plain SHA256 or raw values.
    """
    normalized = value.strip().lower()
    return hmac.new(secret.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def extract_client_ip(request: Request, trusted_proxies: Optional[list[str]] = None) -> str:
    """
    Extracts client IP carefully.
    Does NOT blindly trust X-Forwarded-For unless the direct peer is in trusted_proxies.
    """
    client_host = request.client.host if request.client else "127.0.0.1"
    trusted = trusted_proxies or []

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for and client_host in trusted:
        # Client was proxied by a trusted reverse proxy, use left-most IP
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        if ips:
            return ips[0]

    return client_host


async def verify_turnstile_token(token: str, secret_key: str, remote_ip: Optional[str] = None) -> bool:
    """
    Validates a Cloudflare Turnstile token server-side via Siteverify API.
    Tokens are single-use and expire within 5 minutes.
    """
    url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    data = {
        "secret": secret_key,
        "response": token,
    }
    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, data=data)
            resp_data = resp.json()
            success = resp_data.get("success", False)
            if not success:
                logger.warning("Turnstile verification failed: %s", resp_data.get("error-codes"))
            return success
    except Exception as e:
        logger.error("Exception during Turnstile siteverify: %s", str(e))
        return False


class TrialAbuseService:
    """
    Evaluates trial eligibility using identity HMAC, IP HMAC within a time window,
    and optional Cloudflare Turnstile verification.
    """

    @classmethod
    async def evaluate_eligibility(
        cls,
        db: Session,
        email: str,
        client_ip: str,
        turnstile_token: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Returns (is_eligible, reason)
        Reasons: ALLOW, IDENTITY_USED, IP_LIMIT_EXCEEDED, TURNSTILE_FAILED
        """
        settings = get_saas_settings()

        if not settings.TRIAL_ENABLED:
            return False, "TRIAL_DISABLED"

        # 1. Turnstile Check (if enabled)
        if settings.TURNSTILE_ENABLED:
            if not turnstile_token:
                logger.warning("Trial rejected: Turnstile token missing")
                return False, "TURNSTILE_REQUIRED"

            is_valid = await verify_turnstile_token(
                token=turnstile_token,
                secret_key=settings.TURNSTILE_SECRET_KEY or "",
                remote_ip=client_ip
            )
            if not is_valid:
                logger.warning("Trial rejected: Turnstile verification failed")
                return False, "TURNSTILE_FAILED"

        # 2. Normalized Email Identity Check
        identity_hash = hash_identifier(email, settings.TRIAL_HASH_SECRET)
        id_stmt = select(TrialUsage).where(TrialUsage.identity_hash == identity_hash)
        existing_identity = db.execute(id_stmt).scalar_one_or_none()
        if existing_identity:
            logger.info("Trial rejected: Identity already used trial")
            return False, "IDENTITY_USED"

        # 3. IP Threshold Check (if enabled)
        if settings.TRIAL_IP_LIMIT_ENABLED and client_ip:
            ip_hash = hash_identifier(client_ip, settings.TRIAL_HASH_SECRET)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.TRIAL_IP_WINDOW_HOURS)
            
            ip_count_stmt = select(func.count(TrialUsage.id)).where(
                TrialUsage.ip_hash == ip_hash,
                TrialUsage.created_at >= cutoff
            )
            trial_count = db.execute(ip_count_stmt).scalar() or 0
            if trial_count >= settings.TRIAL_IP_MAX_TRIALS:
                logger.info(
                    "Trial rejected: IP limit exceeded (%d trials in %dh)",
                    trial_count, settings.TRIAL_IP_WINDOW_HOURS
                )
                return False, "IP_LIMIT_EXCEEDED"

        return True, "ALLOW"
