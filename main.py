"""
main.py — SkillCoach Phase 1: app entry, DB init, Head Coach seeding.

Run:  uvicorn main:app --reload
Docs: http://127.0.0.1:8000/docs
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from database import init_db, SessionLocal, User
from auth import hash_password
from routers import auth_routes, admin_routes, coach_routes, chat_routes, reports_routes

load_dotenv()

app = FastAPI(title="SkillCoach", version="0.6.0 (Phase 6)")
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(coach_routes.router)
app.include_router(chat_routes.router)
app.include_router(reports_routes.router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return RedirectResponse("/static/login.html")


@app.on_event("startup")
def startup():
    init_db()
    seed_head_coach()
    seed_models()


def seed_models():
    from database import ModelOption
    db = SessionLocal()
    try:
        if db.query(ModelOption).count() == 0:
            db.add(ModelOption(model_id="claude-haiku-4-5",
                               display_name="Haiku — fast & economical",
                               is_default=True))
            db.add(ModelOption(model_id="claude-sonnet-4-6",
                               display_name="Sonnet — balanced intelligence"))
            db.commit()
            print("✅ Default model options seeded")
    finally:
        db.close()


def seed_head_coach():
    """Create the Head Coach account once, from env vars."""
    email = os.getenv("HEADCOACH_EMAIL", "").lower().strip()
    password = os.getenv("HEADCOACH_PASSWORD", "")
    name = os.getenv("HEADCOACH_NAME", "Head Coach")
    if not email or not password:
        print("⚠️  HEADCOACH_EMAIL / HEADCOACH_PASSWORD not set — skipping seed.")
        return
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            return
        hc = User(name=name, email=email,
                  password_hash=hash_password(password),
                  role="head_coach", must_change_password=False)
        db.add(hc)
        db.commit()
        print(f"✅ Head Coach account created: {email}")
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "phase": 6}
