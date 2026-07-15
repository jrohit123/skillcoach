"""
services/pricing_service.py — token -> USD transparency helpers.

Credits in SkillCoach are a single combined-token balance (input + output
count the same toward a user's balance), but Anthropic bills input and
output tokens at different rates per model. These helpers convert stored
token counts into an approximate USD figure so every role can see what
their usage is actually worth, without needing to inspect the Anthropic
console.
"""
from sqlalchemy.orm import Session
from database import ModelOption


def costliest_active_model(db: Session) -> ModelOption | None:
    """The active model with the highest output-token rate — used as the
    conservative (worst-case) assumption when we only know a TOTAL token
    count and not its actual model / input-output split (e.g. a credit
    balance that hasn't been spent yet)."""
    models = db.query(ModelOption).filter(ModelOption.is_active == True).all()  # noqa: E712
    if not models:
        return None
    return max(models, key=lambda m: (m.output_cost_per_mtok or 0))


def estimate_usd_for_balance(db: Session, tokens: int,
                             assumed_input_ratio: float = 0.8) -> float | None:
    """Conservative worst-case USD value of an unspent token balance —
    assumes the costliest active model and a typical 80/20 input/output
    split (SkillCoach resends full history each turn, so input-heavy).
    Returns None if no active models are configured."""
    m = costliest_active_model(db)
    if not m or tokens <= 0:
        return 0.0 if m else None
    blended_per_mtok = (assumed_input_ratio * (m.input_cost_per_mtok or 0) +
                       (1 - assumed_input_ratio) * (m.output_cost_per_mtok or 0))
    return round((tokens / 1_000_000) * blended_per_mtok, 4)


def exact_usd_for_tokens(input_tokens: int, output_tokens: int,
                         model: ModelOption | None) -> float:
    """Exact USD cost for a known input/output split on a known model."""
    if not model:
        return 0.0
    return round((input_tokens / 1_000_000) * (model.input_cost_per_mtok or 0) +
                (output_tokens / 1_000_000) * (model.output_cost_per_mtok or 0), 4)
