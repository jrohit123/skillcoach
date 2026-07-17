"""
services/pricing_service.py — token -> USD transparency helpers.

Credits in SkillCoach are a single combined-token balance (input + output
count the same toward a user's balance), but Anthropic bills input and
output tokens at different rates per model. These helpers convert stored
token counts into an approximate USD figure so every role can see what
their usage is actually worth, without needing to inspect the Anthropic
console.

Balance estimates use the CHEAPEST active model — a balance is worth at
LEAST this much (it can only buy more, never less, if spent on a pricier
model), which is the more intuitive "what is my balance worth" answer for
coaches and clients. The exact per-model rate difference is surfaced
separately as a warning when someone picks a non-cheapest model to chat with.
"""
from sqlalchemy.orm import Session
from database import ModelOption, PlatformSetting

DEFAULT_INPUT_RATIO = 0.65   # SkillCoach resends conversation history each
                             # turn, so usage skews input-heavy by default.
SETTING_KEY = "assumed_input_ratio"


def get_input_ratio(db: Session) -> float:
    """The configured input-token share used for blended USD estimates
    (Head Coach setting; falls back to the 65% default)."""
    row = db.query(PlatformSetting).filter(PlatformSetting.key == SETTING_KEY).first()
    if not row:
        return DEFAULT_INPUT_RATIO
    try:
        v = float(row.value)
        return v if 0 <= v <= 1 else DEFAULT_INPUT_RATIO
    except ValueError:
        return DEFAULT_INPUT_RATIO


def set_input_ratio(db: Session, ratio: float):
    ratio = max(0.0, min(1.0, ratio))
    row = db.query(PlatformSetting).filter(PlatformSetting.key == SETTING_KEY).first()
    if row:
        row.value = str(ratio)
    else:
        db.add(PlatformSetting(key=SETTING_KEY, value=str(ratio)))
    db.commit()


def cheapest_active_model(db: Session) -> ModelOption | None:
    """The active model with the lowest blended rate — used so a token
    balance's displayed USD value is a reliable floor (it can only be worth
    MORE if spent on a pricier model, never less)."""
    models = db.query(ModelOption).filter(ModelOption.is_active == True).all()  # noqa: E712
    if not models:
        return None
    ratio = get_input_ratio(db)
    return min(models, key=lambda m: blended_rate(m, ratio))


def blended_rate(model: ModelOption, input_ratio: float) -> float:
    """USD per 1M tokens at the configured input/output mix."""
    return (input_ratio * (model.input_cost_per_mtok or 0) +
           (1 - input_ratio) * (model.output_cost_per_mtok or 0))


def estimate_usd_for_balance(db: Session, tokens: int) -> float | None:
    """Conservative (floor) USD value of an unspent token balance — assumes
    the cheapest active model and the configured input/output mix.
    Returns None if no active models are configured."""
    m = cheapest_active_model(db)
    if not m:
        return None
    if tokens <= 0:
        return 0.0
    ratio = get_input_ratio(db)
    return round((tokens / 1_000_000) * blended_rate(m, ratio), 4)


def exact_usd_for_tokens(input_tokens: int, output_tokens: int,
                         model: ModelOption | None) -> float:
    """Exact USD cost for a known input/output split on a known model."""
    if not model:
        return 0.0
    return round((input_tokens / 1_000_000) * (model.input_cost_per_mtok or 0) +
                (output_tokens / 1_000_000) * (model.output_cost_per_mtok or 0), 4)


def model_cost_multiplier(db: Session, model_id: str) -> float | None:
    """How many times pricier this model's blended rate is than the
    cheapest active model. Returns None if the model or a cheapest
    reference can't be determined, or if this IS the cheapest model."""
    cheapest = cheapest_active_model(db)
    if not cheapest:
        return None
    target = db.query(ModelOption).filter(ModelOption.model_id == model_id,
                                          ModelOption.is_active == True).first()  # noqa: E712
    if not target or target.id == cheapest.id:
        return None
    ratio = get_input_ratio(db)
    cheap_rate = blended_rate(cheapest, ratio)
    if cheap_rate <= 0:
        return None
    return round(blended_rate(target, ratio) / cheap_rate, 2)
