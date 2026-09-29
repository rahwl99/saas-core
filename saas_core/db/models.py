import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from saas_core.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """
    Users table.
    Links local user records to Firebase Auth UID without using Firebase UID as primary key.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    
    # Trial tracking
    trial_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps & Soft deletion
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    credit_account: Mapped[Optional["CreditAccount"]] = relationship("CreditAccount", back_populates="user", uselist=False)
    subscriptions: Mapped[List["Subscription"]] = relationship("Subscription", back_populates="user")


class Plan(Base):
    """
    Plans table.
    Defines subscription tiers and their monthly credit allotments.
    """
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(20), default="month", nullable=False)  # month / year
    monthly_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cashfree_plan_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    subscriptions: Mapped[List["Subscription"]] = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    """
    Subscriptions table.
    Tracks recurring billing subscriptions managed via Cashfree.
    """
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("plans.id"), nullable=False, index=True)
    cashfree_customer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    cashfree_subscription_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, CANCELLED, PAST_DUE, etc.
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")


class TrialUsage(Base):
    """
    Trial usage tracking table.
    Persists hashed identities and IP hashes. MUST survive account deletion to prevent trial abuse.
    """
    __tablename__ = "trial_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    identity_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    trial_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_trial_usage_ip_hash_created_at", "ip_hash", "created_at"),
    )


class CreditAccount(Base):
    """
    Credit accounts table.
    Exactly one row per user holding the authoritative balance.
    """
    __tablename__ = "credit_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="credit_account")
    transactions: Mapped[List["CreditTransaction"]] = relationship("CreditTransaction", back_populates="account")


class CreditTransaction(Base):
    """
    Credit ledger transactions table.
    Append-only ledger. Transactions are never updated or deleted.
    """
    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    credit_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("credit_accounts.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # positive for grants, negative for consumption
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # TRIAL_GRANT, MONTHLY_GRANT, USAGE, etc.
    reference_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_info: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    account: Mapped["CreditAccount"] = relationship("CreditAccount", back_populates="transactions")

    __table_args__ = (
        Index("idx_credit_user_reference", "user_id", "reference_id"),
    )


class WebhookEvent(Base):
    """
    Webhook events table.
    Enforces idempotency using a unique constraint on (provider, event_id).
    """
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "cashfree"
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event_id"),
    )
