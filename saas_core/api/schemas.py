from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime


class UserResponse(BaseModel):
    id: str
    firebase_uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    status: str
    trial_started_at: Optional[datetime] = None
    trial_expires_at: Optional[datetime] = None
    trial_used: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClaimTrialRequest(BaseModel):
    turnstile_token: Optional[str] = None


class TrialStatusResponse(BaseModel):
    trial_active: bool
    trial_used: bool
    trial_started_at: Optional[datetime] = None
    trial_expires_at: Optional[datetime] = None


class BalanceResponse(BaseModel):
    user_id: str
    balance: int


class ConsumeCreditsRequest(BaseModel):
    amount: int
    transaction_type: str = "USAGE"
    reference_id: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict] = None


class TransactionResponse(BaseModel):
    id: str
    user_id: str
    amount: int
    balance_after: int
    transaction_type: str
    reference_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanResponse(BaseModel):
    id: str
    name: str
    slug: str
    price: float
    currency: str
    billing_interval: str
    monthly_credits: int
    active: bool

    model_config = ConfigDict(from_attributes=True)


class CheckoutRequest(BaseModel):
    plan_slug: str
    return_url: Optional[str] = None


class CheckoutResponse(BaseModel):
    subscription_id: str
    cashfree_subscription_id: str
    payment_link: Optional[str] = None
    data: dict


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    plan_id: str
    cashfree_subscription_id: Optional[str] = None
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool

    model_config = ConfigDict(from_attributes=True)
