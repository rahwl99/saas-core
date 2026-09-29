# SaaS Core Integration

## Goal

Copy `saas_core/` into an existing FastAPI application without restructuring the existing project.

## 1. Copy the package

Copy:

```text
saas_core/
```

into the host project.

Do not copy the example application into production code.

## 2. Install dependencies

Use the project's existing dependency manager.

Install the dependencies documented in:

```text
pyproject.toml
```

Do not create a second dependency-management system in the host application.

## 3. Configure environment variables

Add the required `SAAS_*` variables to the host application's environment.

Example:

```env
SAAS_DATABASE_URL=
SAAS_FIREBASE_PROJECT_ID=
SAAS_FIREBASE_CLIENT_EMAIL=
SAAS_FIREBASE_PRIVATE_KEY=

SAAS_CASHFREE_CLIENT_ID=
SAAS_CASHFREE_CLIENT_SECRET=
SAAS_CASHFREE_ENVIRONMENT=

SAAS_RESEND_API_KEY=
SAAS_RESEND_FROM_EMAIL=

SAAS_TRIAL_ENABLED=true
SAAS_TRIAL_DURATION_DAYS=3
SAAS_TRIAL_CREDITS=10
```

## 4. Database

The host application should provide the PostgreSQL database.

Supabase is the recommended managed provider, but the code only requires PostgreSQL.

The host project's Alembic environment should remain authoritative.

Merge the SaaS-core migration into the host migration history rather than creating two independent migration systems.

## 5. Register routes

The host application owns the FastAPI instance.

Example:

```python
from fastapi import FastAPI

from saas_core.api.users import router as users_router
from saas_core.api.credits import router as credits_router
from saas_core.api.trial import router as trial_router
from saas_core.api.billing import router as billing_router
from saas_core.api.webhooks import router as webhook_router

app = FastAPI()

app.include_router(users_router, prefix="/api/v1")
app.include_router(credits_router, prefix="/api/v1")

if settings.saas_trial_enabled:
    app.include_router(trial_router, prefix="/api/v1")

if settings.saas_billing_enabled:
    app.include_router(billing_router, prefix="/api/v1")

if settings.saas_billing_enabled:
    app.include_router(webhook_router, prefix="/api/v1")
```

The exact integration may vary according to the host project.

## 6. Use the services

Application code should use service methods rather than directly modifying SaaS tables.

Example:

```python
await credit_service.consume(
    user_id=user.id,
    amount=5,
    transaction_type="USAGE",
    reference_id=job.id,
)
```

Do not directly modify:

```text
credit_accounts.balance
```

from application-specific code.

## 7. Trial configuration

For a SaaS with a free trial:

```env
SAAS_TRIAL_ENABLED=true
SAAS_TRIAL_DURATION_DAYS=3
SAAS_TRIAL_CREDITS=10
```

For a cost-heavy SaaS:

```env
SAAS_TRIAL_ENABLED=false
```

No trial logic should run when disabled.

## 8. Billing configuration

Enable billing:

```env
SAAS_BILLING_ENABLED=true
```

Configure Cashfree credentials and webhook settings.

The frontend must never be the authority for:

* payment success
* subscription status
* credit grants

Those states come from the backend and verified Cashfree events.

## 9. Email configuration

Enable:

```env
SAAS_EMAIL_ENABLED=true
```

or disable:

```env
SAAS_EMAIL_ENABLED=false
```

When disabled, email calls should safely no-op.

## 10. Turnstile

Enable only if the host frontend integrates the Turnstile widget:

```env
SAAS_TURNSTILE_ENABLED=true
```

The frontend sends the Turnstile token to the backend.

The backend validates the token with Cloudflare.

## 11. Host application isolation

Do not rename existing host folders to accommodate `saas_core`.

Do not replace the host application's:

* FastAPI instance
* configuration system
* database system
* user model
* application services

unless the integration explicitly requires it.

The core is designed to be embedded into an existing application.
