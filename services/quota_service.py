"""
services/quota_service.py — one-time credit balances + usage tracking.

Head Coach has an infinite pool (owns the platform key) and issues credits
to coaches; coaches allocate to clients from their own balance.
usage_monthly is kept for reporting purposes.
"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database import User, UsageMonthly, CreditTransaction


def current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def get_usage(db: Session, user_id: int) -> int:
    row = db.query(UsageMonthly).filter(
        UsageMonthly.user_id == user_id,
        UsageMonthly.month == current_month()).first()
    return row.tokens_used if row else 0


def check_credits(db: Session, user: User):
    """Raise 429 if the user has no credits left. Head Coach exempt."""
    if user.role == "head_coach":
        return
    if (user.token_balance or 0) <= 0:
        who = "your coach" if user.role == "client" else "the Head Coach"
        raise HTTPException(
            status_code=429,
            detail=f"You have no credits left. Contact {who} to purchase more.")


def record_usage(db: Session, user: User, tokens: int):
    """Deduct from balance (may dip slightly below zero on the final call)
    and log monthly usage."""
    if user.role != "head_coach":
        user.token_balance = (user.token_balance or 0) - tokens
    month = current_month()
    row = db.query(UsageMonthly).filter(
        UsageMonthly.user_id == user.id,
        UsageMonthly.month == month).first()
    if row:
        row.tokens_used += tokens
    else:
        db.add(UsageMonthly(user_id=user.id, month=month, tokens_used=tokens))
    db.commit()


def transfer_credits(db: Session, from_user: User, to_user: User,
                     tokens: int, note: str = ""):
    """Move credits. from_user None-role 'head_coach' = infinite source.
    Negative tokens = reclaim (pull back from to_user)."""
    if tokens == 0:
        raise HTTPException(400, "Amount cannot be zero")
    if tokens > 0:
        if from_user.role != "head_coach" and (from_user.token_balance or 0) < tokens:
            raise HTTPException(400,
                f"Insufficient credits: you have {from_user.token_balance:,}, tried to give {tokens:,}")
        if from_user.role != "head_coach":
            from_user.token_balance -= tokens
        to_user.token_balance = (to_user.token_balance or 0) + tokens
    else:  # reclaim
        take = -tokens
        if (to_user.token_balance or 0) < take:
            raise HTTPException(400,
                f"Cannot reclaim {take:,}: user only has {to_user.token_balance:,}")
        to_user.token_balance -= take
        if from_user.role != "head_coach":
            from_user.token_balance = (from_user.token_balance or 0) + take
    db.add(CreditTransaction(
        from_user_id=None if from_user.role == "head_coach" else from_user.id,
        to_user_id=to_user.id, tokens=tokens, note=note))
    db.commit()
