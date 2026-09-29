class SaasCoreError(Exception):
    """Base exception for all SaaS Core errors."""
    def __init__(self, message: str, status_code: int = 400, code: str = "saas_core_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class AuthenticationError(SaasCoreError):
    def __init__(self, message: str = "Invalid or missing authentication credentials"):
        super().__init__(message=message, status_code=401, code="authentication_error")


class AuthorizationError(SaasCoreError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message=message, status_code=403, code="authorization_error")


class TrialUnavailableError(SaasCoreError):
    def __init__(self, message: str = "Trial is currently unavailable or disabled"):
        super().__init__(message=message, status_code=400, code="trial_unavailable")


class TrialAlreadyUsedError(SaasCoreError):
    def __init__(self, message: str = "Trial has already been claimed for this account or identity"):
        super().__init__(message=message, status_code=409, code="trial_already_used")


class InsufficientCreditsError(SaasCoreError):
    def __init__(self, message: str = "Insufficient credit balance for this operation"):
        super().__init__(message=message, status_code=402, code="insufficient_credits")


class BillingDisabledError(SaasCoreError):
    def __init__(self, message: str = "Billing features are currently disabled"):
        super().__init__(message=message, status_code=400, code="billing_disabled")


class SubscriptionNotFoundError(SaasCoreError):
    def __init__(self, message: str = "Subscription not found"):
        super().__init__(message=message, status_code=404, code="subscription_not_found")


class WebhookVerificationError(SaasCoreError):
    def __init__(self, message: str = "Webhook signature verification failed"):
        super().__init__(message=message, status_code=400, code="webhook_verification_failed")


class DuplicateReferenceError(SaasCoreError):
    def __init__(self, message: str = "Operation with this reference_id has already been processed"):
        super().__init__(message=message, status_code=409, code="duplicate_reference")
