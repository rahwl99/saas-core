# SaaS Core Architecture

## Purpose

`saas_core` is a reusable backend module for SaaS applications.

It provides common infrastructure for:

* authentication
* users
* optional trials
* credits
* subscriptions
* payments
* transactional email
* account deletion

The host SaaS application remains responsible for its own application-specific functionality.

## Architecture

```text
Frontend
   |
   | Firebase ID Token
   v
Host FastAPI Application
   |
   +--> saas_core
          |
          +--> Firebase Auth
          +--> Trial Service
          +--> Credit Service
          +--> Billing Service
          +--> Email Service
          +--> Account Service
          |
          v
      PostgreSQL
          ^
          |
      Cashfree
      Webhooks
```

## External Services

| Service              | Purpose                       |
| -------------------- | ----------------------------- |
| Firebase Auth        | Authentication                |
| Supabase PostgreSQL  | Database                      |
| Cashfree             | Payments/subscriptions        |
| Resend               | Transactional email           |
| Cloudflare Turnstile | Signup/trial abuse protection |

## Deliberately excluded

The core does not use:

* Firestore
* Redis
* Celery
* Cloud Tasks
* Cloud Scheduler
* Firebase Functions
* Supabase Edge Functions
* background workers
* queues
* Kubernetes

## Package boundary

All reusable code belongs under:

```text
saas_core/
```

The core must not create root-level:

```text
models/
services/
utils/
auth/
api/
config/
```

directories.

The host application owns those namespaces.

## Data ownership

The host application owns its application-specific tables.

`saas_core` owns its SaaS tables:

```text
users
plans
subscriptions
trial_usage
credit_accounts
credit_transactions
webhook_events
```

## Deployment

The package is deployment-agnostic.

It can run:

* locally
* in Docker
* on Cloud Run
* on a VPS
* on another container platform

Cloud Run is not required by the application.

## Design principles

1. Keep the core small.
2. Prefer PostgreSQL transactions over additional infrastructure.
3. Keep integrations isolated.
4. Never trust client billing or credit state.
5. Make expensive/optional features configurable.
6. Avoid premature abstractions.
7. Keep the host application in control.
