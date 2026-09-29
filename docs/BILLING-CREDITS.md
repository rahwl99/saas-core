# Billing and Credits

## Credit model

Each user has one credit account.

```text
user
  |
  v
credit_account
  |
  v
credit_transactions
```

The current balance is stored in:

```text
credit_accounts.balance
```

Every change is recorded in:

```text
credit_transactions
```

## Credit grants

Examples:

```text
TRIAL_GRANT
MONTHLY_GRANT
```

Usage:

```text
USAGE
```

Administrative corrections may use:

```text
ADMIN_ADJUSTMENT
```

## Immutable ledger

Completed credit transactions must never be edited or deleted.

Each transaction records:

```text
amount
balance_after
transaction_type
reference_id
description
metadata
created_at
```

## Credit consumption

Credit consumption must happen inside a database transaction.

Flow:

```text
BEGIN
  |
  +-- lock credit account
  |
  +-- check balance
  |
  +-- subtract credits
  |
  +-- insert ledger entry
  |
COMMIT
```

If insufficient credits exist, the transaction fails without modifying the balance.

## Idempotency

Credit-consuming operations should provide a logical reference:

```text
reference_id = application_job_id
```

A retry of the same logical operation must not consume credits twice.

## Trial

When enabled:

```text
3 days
10 credits
```

are the default values.

The values are configurable.

Trial credits are granted exactly once.

Trial eligibility survives account deletion.

## Monthly subscription credits

Successful recurring payment:

```text
Cashfree webhook
      |
      v
verify event
      |
      v
deduplicate
      |
      v
identify subscription
      |
      v
identify plan
      |
      v
grant monthly credits
```

The grant is recorded as:

```text
MONTHLY_GRANT
```

The same payment event must never grant credits twice.

## No rollover in v1

Unused monthly credits do not roll over.

There is no:

* credit bucket system
* credit expiration engine
* rollover system
* promotional credit system
* referral credit system

These can be added by an individual SaaS later.

## Plans

Plans are database records.

Example:

```text
Starter
100 credits/month

Pro
500 credits/month

Business
2000 credits/month
```

The credit service does not need to know plan names.

It receives the configured credit amount.

## Cashfree

Cashfree is the payment provider for v1.

The backend is authoritative for application subscription state.

Frontend payment success must not directly grant credits.

Only verified backend payment events may trigger monthly credit grants.
