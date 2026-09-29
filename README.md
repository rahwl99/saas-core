# SaaS Core

A reusable, vendorable Python SaaS backend core designed to be copied directly into FastAPI projects.

It provides Firebase Auth integration, user synchronization, free trials with abuse protection, Cashfree subscription billing, idempotent webhook handling, transactional Resend emails, and an atomic, immutable credit ledger.

---

## Features

- **Portability**: Lives cleanly under `saas_core/`. No collisions with host app models, routes, or configurations.
- **Firebase Auth**: Server-side token verification with auto-provisioning of local user records and credit accounts.
- **Atomic Credit Ledger**: Append-only ledger with row-level locking (`SELECT ... FOR UPDATE`), idempotency via `reference_id`, and negative balance prevention.
- **Optional Free Trial**: Timestamp-based active trial checks (no cron workers required) with configurable duration and initial credits.
- **Trial Abuse Deterrence**: Keyed HMAC hashing of normalized emails and client IPs (with trusted proxy support) + Cloudflare Turnstile verification. Abuse records survive account deletion.
- **Cashfree Subscriptions**: Checkout session creation, subscription tracking, and idempotent signature-verified webhook processing.
- **Transactional Emails**: Pre-wired Resend notifications (welcome, trial expiring, payment success, payment failed, subscription cancelled) that cleanly no-op when disabled.
- **Account Deletion / Anonymization**: PII anonymization, active subscription cancellation, and Firebase user deletion.

---

## Directory Structure

```text
saas_core/
├── __init__.py
├── version.py
├── dependencies.py
├── exceptions.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── db/
│   ├── __init__.py
│   ├── base.py
│   ├── session.py
│   └── models.py
├── auth/
│   ├── __init__.py
│   ├── firebase.py
│   └── dependencies.py
├── abuse/
│   ├── __init__.py
│   └── trial_protection.py
├── trials/
│   ├── __init__.py
│   └── service.py
├── credits/
│   ├── __init__.py
│   └── service.py
├── billing/
│   ├── __init__.py
│   ├── cashfree.py
│   └── service.py
├── email/
│   ├── __init__.py
│   ├── resend.py
│   └── service.py
├── account/
│   ├── __init__.py
│   └── service.py
└── api/
    ├── __init__.py
    ├── schemas.py
    ├── users.py
    ├── trial.py
    ├── credits.py
    ├── billing.py
    └── webhooks.py
```

---

## Quick Start

### 1. Start Local PostgreSQL

```bash
docker compose up -d
```

### 2. Configure Environment

Copy `.env.saas.example` to `.env`:

```bash
cp .env.saas.example .env
```

All SaaS Core settings use the `SAAS_` prefix.

### 3. Run Database Migrations

```bash
alembic upgrade head
```

### 4. Run Tests

```bash
pytest -v
```

---

## Integrating into an Existing FastAPI App

Copy the `saas_core/` directory into your project, or install dependencies:

```python
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# Import SaaS Core components
from saas_core.api import (
    users_router,
    trial_router,
    credits_router,
    billing_router,
    webhooks_router,
)
from saas_core.auth import get_current_user
from saas_core.credits import CreditService
from saas_core.db import get_db, User

app = FastAPI(title="My Application")

# Mount SaaS core routers
app.include_router(users_router, prefix="/api/v1")
app.include_router(trial_router, prefix="/api/v1")
app.include_router(credits_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")

# Protect your own custom endpoints with credit consumption:
@app.post("/api/v1/generate")
def run_generation(prompt: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Atomically consume credits:
    CreditService.consume(
        db=db,
        user_id=user.id,
        amount=2,
        transaction_type="USAGE",
        reference_id="unique_task_id"
    )
    return {"message": "Success"}
```

For more documentation, see:
- [Architecture](docs/ARCHITECTURE.md)
- [Integration Guide](docs/INTEGRATION.md)
- [Billing & Credits](docs/BILLING-CREDITS.md)
- [Security](docs/SECURITY.md)
