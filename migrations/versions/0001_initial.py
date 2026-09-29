"""Initial SaaS Core tables

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-29 12:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('firebase_uid', sa.String(length=128), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('trial_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_used', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_firebase_uid'), 'users', ['firebase_uid'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)

    # Plans
    op.create_table(
        'plans',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='INR'),
        sa.Column('billing_interval', sa.String(length=20), nullable=False, server_default='month'),
        sa.Column('monthly_credits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cashfree_plan_id', sa.String(length=100), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plans_slug'), 'plans', ['slug'], unique=True)

    # Subscriptions
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('plan_id', sa.String(length=36), nullable=False),
        sa.Column('cashfree_customer_id', sa.String(length=128), nullable=True),
        sa.Column('cashfree_subscription_id', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_plan_id'), 'subscriptions', ['plan_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_cashfree_customer_id'), 'subscriptions', ['cashfree_customer_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_cashfree_subscription_id'), 'subscriptions', ['cashfree_subscription_id'], unique=True)

    # Trial Usage
    op.create_table(
        'trial_usage',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('identity_hash', sa.String(length=64), nullable=False),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.Column('trial_started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trial_usage_identity_hash'), 'trial_usage', ['identity_hash'], unique=True)
    op.create_index(op.f('ix_trial_usage_ip_hash'), 'trial_usage', ['ip_hash'], unique=False)
    op.create_index(op.f('ix_trial_usage_user_id'), 'trial_usage', ['user_id'], unique=False)
    op.create_index('idx_trial_usage_ip_hash_created_at', 'trial_usage', ['ip_hash', 'created_at'], unique=False)

    # Credit Accounts
    op.create_table(
        'credit_accounts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('balance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credit_accounts_user_id'), 'credit_accounts', ['user_id'], unique=True)

    # Credit Transactions
    op.create_table(
        'credit_transactions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('credit_account_id', sa.String(length=36), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=50), nullable=False),
        sa.Column('reference_id', sa.String(length=128), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('meta_info', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['credit_account_id'], ['credit_accounts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credit_transactions_user_id'), 'credit_transactions', ['user_id'], unique=False)
    op.create_index(op.f('ix_credit_transactions_credit_account_id'), 'credit_transactions', ['credit_account_id'], unique=False)
    op.create_index('idx_credit_user_reference', 'credit_transactions', ['user_id', 'reference_id'], unique=False)

    # Webhook Events
    op.create_table(
        'webhook_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('event_id', sa.String(length=128), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'event_id', name='uq_webhook_provider_event_id')
    )


def downgrade() -> None:
    op.drop_table('webhook_events')
    op.drop_table('credit_transactions')
    op.drop_table('credit_accounts')
    op.drop_table('trial_usage')
    op.drop_table('subscriptions')
    op.drop_table('plans')
    op.drop_table('users')
