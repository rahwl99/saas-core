from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# Import SaaS Core routers and dependencies
from saas_core.api.users import router as users_router
from saas_core.api.trial import router as trial_router
from saas_core.api.credits import router as credits_router
from saas_core.api.billing import router as billing_router
from saas_core.api.webhooks import router as webhooks_router
from saas_core.auth.dependencies import get_current_user
from saas_core.credits.service import CreditService
from saas_core.db.session import get_db
from saas_core.db.models import User

# Host application creates and owns its FastAPI instance
app = FastAPI(
    title="My AI SaaS",
    description="Example host application integrating saas_core",
    version="1.0.0"
)

# Mount saas_core routers under configurable prefix
app.include_router(users_router, prefix="/api/v1")
app.include_router(trial_router, prefix="/api/v1")
app.include_router(credits_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


@app.get("/")
def health_check():
    return {"status": "ok", "app": "My AI SaaS"}


@app.post("/api/v1/generate")
def generate_ai_text(
    prompt: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Example host SaaS feature that atomically consumes credits using saas_core.
    """
    cost_in_credits = 2

    # Atomically verify and consume credits before running expensive operation
    tx = CreditService.consume(
        db=db,
        user_id=user.id,
        amount=cost_in_credits,
        transaction_type="USAGE",
        description=f"AI generation for prompt: {prompt[:30]}..."
    )

    # Simulated AI model generation
    generated_text = f"AI completion for '{prompt}'. Generated successfully!"

    return {
        "result": generated_text,
        "credits_spent": cost_in_credits,
        "balance_remaining": tx.balance_after
    }
