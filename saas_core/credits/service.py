import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from saas_core.db.models import CreditAccount, CreditTransaction
from saas_core.exceptions import InsufficientCreditsError, DuplicateReferenceError

logger = logging.getLogger(__name__)


class CreditService:
    """
    Authoritative credit balance and immutable ledger service.
    Handles atomic balance updates using SELECT ... FOR UPDATE row-level locking.
    """

    @staticmethod
    def get_or_create_account(db: Session, user_id: str) -> CreditAccount:
        """
        Retrieves or creates a credit account for a user.
        """
        stmt = select(CreditAccount).where(CreditAccount.user_id == user_id)
        account = db.execute(stmt).scalar_one_or_none()
        if not account:
            account = CreditAccount(user_id=user_id, balance=0)
            db.add(account)
            db.flush()
        return account

    @classmethod
    def get_balance(cls, db: Session, user_id: str) -> int:
        """
        Returns the current authoritative credit balance.
        """
        account = cls.get_or_create_account(db, user_id)
        return account.balance

    @classmethod
    def grant(
        cls,
        db: Session,
        user_id: str,
        amount: int,
        transaction_type: str,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CreditTransaction:
        """
        Atomically grants credits to a user and logs an immutable ledger entry.
        Idempotent when reference_id is provided.
        """
        if amount <= 0:
            raise ValueError("Grant amount must be strictly positive")

        # Check idempotency if reference_id is supplied
        if reference_id:
            dup_stmt = select(CreditTransaction).where(
                CreditTransaction.user_id == user_id,
                CreditTransaction.reference_id == reference_id,
                CreditTransaction.transaction_type == transaction_type
            )
            existing = db.execute(dup_stmt).scalar_one_or_none()
            if existing:
                logger.info(
                    "Credit grant idempotency hit: user_id=%s, ref=%s",
                    user_id, reference_id
                )
                return existing

        # Lock the credit account row for atomic balance update
        # with_for_update is supported in PostgreSQL; in SQLite tests it behaves gracefully
        account_stmt = (
            select(CreditAccount)
            .where(CreditAccount.user_id == user_id)
            .with_for_update()
        )
        account = db.execute(account_stmt).scalar_one_or_none()
        if not account:
            account = CreditAccount(user_id=user_id, balance=0)
            db.add(account)
            db.flush()

        new_balance = account.balance + amount
        account.balance = new_balance

        tx = CreditTransaction(
            user_id=user_id,
            credit_account_id=account.id,
            amount=amount,
            balance_after=new_balance,
            transaction_type=transaction_type,
            reference_id=reference_id,
            description=description,
            meta_info=metadata,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)

        logger.info(
            "Granted %d credits to user=%s, type=%s, new_balance=%d",
            amount, user_id, transaction_type, new_balance
        )
        return tx

    @classmethod
    def consume(
        cls,
        db: Session,
        user_id: str,
        amount: int,
        transaction_type: str = "USAGE",
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CreditTransaction:
        """
        Atomically consumes credits from a user's account.
        Validates sufficient balance, updates balance, creates ledger transaction.
        Enforces idempotency if reference_id is supplied.
        """
        if amount <= 0:
            raise ValueError("Consume amount must be strictly positive")

        # Check idempotency
        if reference_id:
            dup_stmt = select(CreditTransaction).where(
                CreditTransaction.user_id == user_id,
                CreditTransaction.reference_id == reference_id,
                CreditTransaction.transaction_type == transaction_type
            )
            existing = db.execute(dup_stmt).scalar_one_or_none()
            if existing:
                logger.info(
                    "Credit consume idempotency hit: user_id=%s, ref=%s",
                    user_id, reference_id
                )
                return existing

        # Lock the credit account row
        account_stmt = (
            select(CreditAccount)
            .where(CreditAccount.user_id == user_id)
            .with_for_update()
        )
        account = db.execute(account_stmt).scalar_one_or_none()
        if not account or account.balance < amount:
            current_bal = account.balance if account else 0
            logger.warning(
                "Insufficient credits: user=%s, required=%d, available=%d",
                user_id, amount, current_bal
            )
            raise InsufficientCreditsError(
                f"Insufficient credits: required {amount}, available {current_bal}"
            )

        new_balance = account.balance - amount
        account.balance = new_balance

        tx = CreditTransaction(
            user_id=user_id,
            credit_account_id=account.id,
            amount=-amount,
            balance_after=new_balance,
            transaction_type=transaction_type,
            reference_id=reference_id,
            description=description,
            meta_info=metadata,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)

        logger.info(
            "Consumed %d credits from user=%s, type=%s, new_balance=%d",
            amount, user_id, transaction_type, new_balance
        )
        return tx

    @classmethod
    def set_monthly_allocation(
        cls,
        db: Session,
        user_id: str,
        monthly_credits: int,
        reference_id: Optional[str] = None,
    ) -> CreditTransaction:
        """
        Replaces unused monthly credits with the new monthly allocation
        according to the non-rollover policy specified in section 17.
        """
        if reference_id:
            dup_stmt = select(CreditTransaction).where(
                CreditTransaction.user_id == user_id,
                CreditTransaction.reference_id == reference_id,
                CreditTransaction.transaction_type == "MONTHLY_GRANT"
            )
            existing = db.execute(dup_stmt).scalar_one_or_none()
            if existing:
                return existing

        account_stmt = (
            select(CreditAccount)
            .where(CreditAccount.user_id == user_id)
            .with_for_update()
        )
        account = db.execute(account_stmt).scalar_one_or_none()
        if not account:
            account = CreditAccount(user_id=user_id, balance=0)
            db.add(account)
            db.flush()

        # Non-rollover policy: set balance to monthly_credits
        delta = monthly_credits - account.balance
        account.balance = monthly_credits

        tx = CreditTransaction(
            user_id=user_id,
            credit_account_id=account.id,
            amount=delta,
            balance_after=monthly_credits,
            transaction_type="MONTHLY_GRANT",
            reference_id=reference_id,
            description=f"Monthly subscription credit reset/grant to {monthly_credits}",
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx
