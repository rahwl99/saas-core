# Security Requirements

## Authentication

Firebase ID tokens must be verified server-side.

Never trust a client-provided:

```text
user_id
email
subscription_status
credit_balance
```

The Firebase UID from the verified token is used to identify the authenticated user.

## Secrets

Never commit:

* Firebase private keys
* Cashfree secrets
* Resend API keys
* Turnstile secret keys
* database passwords
* hash secrets

Use environment variables or the deployment platform's secret manager.

## Trial identity hashing

Trial identity should be stored as a keyed HMAC rather than raw email.

Conceptually:

```text
HMAC-SHA256(
    trial_hash_secret,
    normalized_email
)
```

Do the same for IP addresses.

Do not use plain SHA256 for abuse identifiers.

## IP privacy

Do not store raw IP addresses for trial tracking.

Use an HMAC hash.

Do not log raw IP addresses.

## Trial abuse

IP matching is an abuse-reduction mechanism, not a perfect identity system.

Do not enforce:

```text
one IP = one trial
```

by default.

Shared networks can contain legitimate users.

Use configurable thresholds.

## Turnstile

Turnstile validation must happen on the backend using Cloudflare Siteverify.

Never trust only the client-side Turnstile result.

Tokens are temporary and single-use.

## Billing

Never trust frontend payment state.

Cashfree webhook authenticity must be verified before processing.

Webhook events must be idempotent.

Duplicate provider events must not create duplicate credit grants.

## Credits

Credit balance modifications must happen through the credit service.

Never directly modify the balance from application code.

Consumption must be atomic.

Negative balances are not allowed.

Credit ledger entries are immutable.

## Webhooks

Store provider event IDs.

Use a unique constraint on:

```text
provider + event_id
```

A repeated webhook must not repeat its business effect.

## Errors

Production responses must not expose:

* stack traces
* SQL errors
* provider credentials
* internal configuration
* secrets

Log internal errors safely without leaking sensitive information.

## Account deletion

Deletion must not automatically restore trial eligibility.

Retain only the minimum non-personal information required for:

* trial abuse prevention
* billing integrity
* credit integrity
* required operational/audit purposes

Actual legal retention requirements depend on the deploying application's jurisdiction and policies.

## Dependency discipline

Avoid unnecessary third-party packages.

Do not introduce:

* Redis
* Celery
* background workers
* custom cryptography
* unnecessary authentication systems
* unnecessary payment systems

without a documented requirement.
