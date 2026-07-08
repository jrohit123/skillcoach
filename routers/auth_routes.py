"""
routers/auth_routes.py — login, change password, current-user info.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, User
from auth import verify_password, hash_password, create_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


class TimezoneIn(BaseModel):
    timezone: str


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username.lower().strip()).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    if user.valid_until and user.valid_until < date.today():
        raise HTTPException(status_code=403, detail="Account validity has expired")
    return {
        "access_token": create_token(user),
        "token_type": "bearer",
        "role": user.role,
        "name": user.name,
        "must_change_password": user.must_change_password,
        "timezone": user.timezone or "Asia/Kolkata",
    }


@router.post("/change-password")
def change_password(body: ChangePasswordIn,
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.commit()
    return {"ok": True, "message": "Password changed"}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "valid_until": str(user.valid_until),
        "timezone": user.timezone or "Asia/Kolkata",
    }


@router.patch("/timezone")
def set_timezone(body: TimezoneIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    user.timezone = body.timezone.strip()[:50]
    db.commit()
    return {"ok": True, "timezone": user.timezone}
