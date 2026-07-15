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
    seed_categories()
    seed_categories()


def seed_categories():
    """Seed default categories once; also adopt any category names already
    used on skills (from before categories became manageable)."""
    from database import Category, Skill
    db = SessionLocal()
    try:
        existing = {c.name for c in db.query(Category).all()}
        defaults = ["Strategy", "Culture", "Operations", "Revenue", "Execution"]
        used = {s.category.strip() for s in db.query(Skill.category).all()
                if s.category and s.category.strip()}
        to_add = ([] if existing else defaults) + sorted(used - existing - set(defaults))
        if not existing:
            to_add = defaults + sorted(used - set(defaults))
        for name in dict.fromkeys(to_add):
            if name not in existing:
                db.add(Category(name=name))
        db.commit()
    finally:
        db.close()


def seed_models():
    from database import ModelOption
    db = SessionLocal()
    try:
        if db.query(ModelOption).count() == 0:
            db.add(ModelOption(model_id="claude-haiku-4-5",
                               display_name="Haiku — fast & economical",
                               is_default=True,
                               input_cost_per_mtok=1.0, output_cost_per_mtok=5.0))
            db.add(ModelOption(model_id="claude-sonnet-4-6",
                               display_name="Sonnet — balanced intelligence",
                               input_cost_per_mtok=3.0, output_cost_per_mtok=15.0))
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


def seed_categories():
    """Seed the 5 default categories once, plus any already used on skills."""
    from database import SkillCategory, Skill
    db = SessionLocal()
    try:
        if db.query(SkillCategory).count() == 0:
            used = {(s.category or "").strip() for s in db.query(Skill.category).all()}
            defaults = ["Strategy", "Culture", "Operations", "Revenue", "Execution"]
            names = dict.fromkeys(defaults + sorted(used - {""} - set(defaults)))
            for i, name in enumerate(names):
                db.add(SkillCategory(name=name, sort_order=i))
            db.commit()
            print("✅ Skill categories seeded")
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "phase": 6}
