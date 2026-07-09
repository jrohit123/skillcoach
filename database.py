"""
database.py — PostgreSQL connection + all table models (SQLAlchemy).
Phase 1 creates all 7 tables up front so later phases don't need migrations.
"""
import os
from datetime import datetime, date, timedelta

from dotenv import load_dotenv
from sqlalchemy import (create_engine, Column, Integer, String, Text, Boolean,
                        Date, DateTime, ForeignKey, UniqueConstraint)
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
# Railway sometimes gives postgres:// which SQLAlchemy rejects
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def default_valid_until():
    return date.today() + timedelta(days=365)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False)  # head_coach | coach | client
    coach_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # for clients
    is_active = Column(Boolean, default=True)
    valid_from = Column(Date, default=date.today)
    valid_until = Column(Date, default=default_valid_until)
    token_balance = Column(Integer, default=0)   # one-time credit balance (tokens)
    must_change_password = Column(Boolean, default=True)
    timezone = Column(String(50), default="Asia/Kolkata")
    # coach branding
    brand_name = Column(String(200), default="")
    brand_logo = Column(Text, default="")        # base64 data URL
    brand_about = Column(Text, default="")
    brand_website = Column(String(300), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class SkillCategory(Base):
    __tablename__ = "skill_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    sort_order = Column(Integer, default=0)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null = platform issue
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tokens = Column(Integer, nullable=False)     # positive = given, negative = reclaimed
    note = Column(String(300), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelOption(Base):
    __tablename__ = "model_options"
    id = Column(Integer, primary_key=True)
    model_id = Column(String(100), unique=True, nullable=False)  # e.g. claude-haiku-4-5
    display_name = Column(String(150), nullable=False)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)


class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    system_prompt = Column(Text, nullable=False)
    category = Column(String(100), default="")
    is_enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)


class SkillAssignment(Base):  # Head Coach leases skill -> Coach
    __tablename__ = "skill_assignments"
    id = Column(Integer, primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    coach_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("skill_id", "coach_id", name="uq_skill_coach"),)


class SkillGrant(Base):  # Coach grants skill -> Client
    __tablename__ = "skill_grants"
    id = Column(Integer, primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    granted_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("skill_id", "client_id", name="uq_skill_client"),)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    title = Column(String(200), default="New conversation")
    model_id = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    superseded = Column(Boolean, default=False)   # edited-away turns (soft delete)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class UsageMonthly(Base):
    __tablename__ = "usage_monthly"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(String(7), nullable=False)  # "2026-07"
    tokens_used = Column(Integer, default=0)
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_user_month"),)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    migrate()


MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_balance INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS brand_name VARCHAR(200) DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS brand_logo TEXT DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS brand_about TEXT DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS brand_website VARCHAR(300) DEFAULT ''",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS model_id VARCHAR(100) DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'Asia/Kolkata'",
    "ALTER TABLE skills ADD COLUMN IF NOT EXISTS category VARCHAR(100) DEFAULT ''",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS superseded BOOLEAN DEFAULT FALSE",
    "ALTER TABLE skill_categories ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0",
    # carry over any previous monthly quota as an opening balance, then drop it
    """DO $$ BEGIN
         IF EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='monthly_token_quota') THEN
           UPDATE users SET token_balance = COALESCE(token_balance,0) + monthly_token_quota
             WHERE role != 'head_coach' AND COALESCE(token_balance,0) = 0;
           ALTER TABLE users DROP COLUMN monthly_token_quota;
         END IF;
       END $$;""",
]


def migrate():
    from sqlalchemy import text
    if not DATABASE_URL.startswith("postgresql"):
        return  # migrations are written for PostgreSQL (production)
    with engine.begin() as conn:
        for stmt in MIGRATIONS:
            conn.execute(text(stmt))
