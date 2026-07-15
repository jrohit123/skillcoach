"""
routers/admin_routes.py — Head Coach only.
Skills: create / edit / enable / disable / list
Coaches: create / list / activate-deactivate / extend validity / set quota
Assignments: lease a skill to a coach, revoke it
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import (get_db, User, Skill, SkillAssignment, ModelOption,
                      CreditTransaction, SkillCategory)
from auth import require_head_coach, hash_password
from services.quota_service import transfer_credits
from services.pricing_service import estimate_usd_for_balance
import csv, io

router = APIRouter(prefix="/api/admin", tags=["head coach"])


# ---------- Schemas ----------

def ensure_category(db: Session, name: str):
    """A category typed on a skill is auto-registered in the table."""
    name = (name or "").strip()[:100]
    if name and not db.query(SkillCategory).filter(SkillCategory.name == name).first():
        db.add(SkillCategory(name=name))


class SkillIn(BaseModel):
    title: str
    description: str = ""
    system_prompt: str
    category: str = ""


class SkillUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    category: Optional[str] = None
    is_enabled: Optional[bool] = None


class CoachIn(BaseModel):
    name: str
    email: EmailStr
    password: str  # temporary; coach must change on first login
    opening_credits: int = 0
    validity_days: int = 365


class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    extend_days: Optional[int] = None       # adds days to valid_until


class AssignIn(BaseModel):
    skill_id: int
    coach_ids: list[int] = []   # one, several, or use all_coaches
    all_coaches: bool = False


class IssueCreditsIn(BaseModel):
    coach_id: int
    tokens: int                 # positive = issue, negative = reclaim
    note: str = ""


class ModelIn(BaseModel):
    model_id: str
    display_name: str
    is_default: bool = False
    input_cost_per_mtok: float = 1.0
    output_cost_per_mtok: float = 5.0


# ---------- Skills ----------

@router.post("/skills")
def create_skill(body: SkillIn, hc: User = Depends(require_head_coach),
                 db: Session = Depends(get_db)):
    if not body.title.strip() or not body.system_prompt.strip():
        raise HTTPException(400, "Title and system prompt are required")
    ensure_category(db, body.category)
    s = Skill(title=body.title.strip(), description=body.description.strip(),
              system_prompt=body.system_prompt,
              category=body.category.strip()[:100], created_by=hc.id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "title": s.title, "is_enabled": s.is_enabled}


@router.get("/skills")
def list_skills(hc: User = Depends(require_head_coach), db: Session = Depends(get_db)):
    skills = db.query(Skill).order_by(Skill.id).all()
    out = []
    for s in skills:
        coach_count = db.query(SkillAssignment).filter(
            SkillAssignment.skill_id == s.id,
            SkillAssignment.is_active == True).count()  # noqa: E712
        out.append({"id": s.id, "title": s.title, "description": s.description,
                    "category": s.category or "",
                    "is_enabled": s.is_enabled, "assigned_coaches": coach_count,
                    "created_at": str(s.created_at)})
    return out


@router.get("/skills/template")
def skills_template(hc: User = Depends(require_head_coach)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["title", "description", "category", "system_prompt"])
    w.writerow(["Example Skill Title", "One-line description shown to coaches/clients",
                "Strategy", "You are a coach helping the client with... (the full system prompt)"])
    from fastapi.responses import StreamingResponse
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="skills_template.csv"'})


@router.post("/skills/bulk")
async def skills_bulk_upload(file: UploadFile = File(...),
                             hc: User = Depends(require_head_coach),
                             db: Session = Depends(get_db)):
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    required = {"title", "system_prompt"}
    if not required.issubset({(h or "").strip() for h in (reader.fieldnames or [])}):
        raise HTTPException(400, "CSV must have at least 'title' and 'system_prompt' columns")

    created, errors = [], []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        title = (row.get("title") or "").strip()
        prompt = (row.get("system_prompt") or "").strip()
        category = (row.get("category") or "").strip()
        desc = (row.get("description") or "").strip()
        if not title or not prompt:
            errors.append(f"Row {i}: title and system_prompt are required — skipped")
            continue
        ensure_category(db, category)
        db.add(Skill(title=title, description=desc, system_prompt=prompt,
                     category=category[:100], created_by=hc.id))
        created.append(title)
    db.commit()
    return {"ok": True, "created": len(created), "titles": created, "errors": errors}


@router.get("/skills/{skill_id}")
def get_skill(skill_id: int, hc: User = Depends(require_head_coach),
              db: Session = Depends(get_db)):
    s = db.query(Skill).get(skill_id)
    if not s:
        raise HTTPException(404, "Skill not found")
    return {"id": s.id, "title": s.title, "description": s.description,
            "system_prompt": s.system_prompt, "category": s.category or "",
            "is_enabled": s.is_enabled}


@router.patch("/skills/{skill_id}")
def update_skill(skill_id: int, body: SkillUpdate,
                 hc: User = Depends(require_head_coach), db: Session = Depends(get_db)):
    s = db.query(Skill).get(skill_id)
    if not s:
        raise HTTPException(404, "Skill not found")
    if body.title is not None:
        s.title = body.title.strip()
    if body.description is not None:
        s.description = body.description.strip()
    if body.system_prompt is not None:
        s.system_prompt = body.system_prompt
    if body.category is not None:
        ensure_category(db, body.category)
        s.category = body.category.strip()[:100]
    if body.is_enabled is not None:
        s.is_enabled = body.is_enabled
    db.commit()
    return {"ok": True, "id": s.id, "is_enabled": s.is_enabled}


@router.get("/categories")
def list_categories(hc: User = Depends(require_head_coach),
                    db: Session = Depends(get_db)):
    rows = db.query(SkillCategory).order_by(SkillCategory.sort_order,
                                            SkillCategory.name).all()
    counts = {}
    for s in db.query(Skill.category).all():
        c = (s.category or "").strip()
        if c:
            counts[c] = counts.get(c, 0) + 1
    return [{"id": r.id, "name": r.name, "skills": counts.get(r.name, 0)}
            for r in rows]


class CategoryRenameIn(BaseModel):
    new_name: str


@router.post("/categories/{cat_id}/move")
def move_category(cat_id: int, direction: str,
                  hc: User = Depends(require_head_coach),
                  db: Session = Depends(get_db)):
    """direction = 'up' | 'down' — swaps sort position with the neighbour."""
    rows = db.query(SkillCategory).order_by(SkillCategory.sort_order,
                                            SkillCategory.name).all()
    # normalise sort_order to clean 0..n first (handles legacy zeros)
    for i, r in enumerate(rows):
        r.sort_order = i
    idx = next((i for i, r in enumerate(rows) if r.id == cat_id), None)
    if idx is None:
        raise HTTPException(404, "Category not found")
    j = idx - 1 if direction == "up" else idx + 1
    if 0 <= j < len(rows):
        rows[idx].sort_order, rows[j].sort_order = rows[j].sort_order, rows[idx].sort_order
    db.commit()
    return {"ok": True}


@router.patch("/categories/{cat_id}")
def rename_category(cat_id: int, body: CategoryRenameIn,
                    hc: User = Depends(require_head_coach),
                    db: Session = Depends(get_db)):
    cat = db.query(SkillCategory).get(cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    new = body.new_name.strip()[:100]
    if not new:
        raise HTTPException(400, "New name cannot be empty")
    clash = db.query(SkillCategory).filter(SkillCategory.name == new,
                                           SkillCategory.id != cat_id).first()
    if clash:
        raise HTTPException(400, "A category with that name already exists")
    old = cat.name
    cat.name = new
    db.query(Skill).filter(Skill.category == old).update({Skill.category: new})
    db.commit()
    return {"ok": True, "old": old, "new": new}


@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int, hc: User = Depends(require_head_coach),
                    db: Session = Depends(get_db)):
    cat = db.query(SkillCategory).get(cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    moved = (db.query(Skill).filter(Skill.category == cat.name)
             .update({Skill.category: ""}))
    db.delete(cat)
    db.commit()
    return {"ok": True, "message":
            f"Category deleted. {moved} skill(s) are now uncategorized."}


# ---------- Coaches ----------

@router.post("/coaches")
def create_coach(body: CoachIn, hc: User = Depends(require_head_coach),
                 db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Email already exists")
    if len(body.password) < 8:
        raise HTTPException(400, "Temporary password must be at least 8 characters")
    c = User(name=body.name.strip(), email=email,
             password_hash=hash_password(body.password), role="coach",
             token_balance=max(0, body.opening_credits),
             valid_from=date.today(),
             valid_until=date.today() + timedelta(days=body.validity_days))
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "name": c.name, "email": c.email,
            "valid_until": str(c.valid_until)}


@router.get("/coaches")
def list_coaches(hc: User = Depends(require_head_coach), db: Session = Depends(get_db)):
    coaches = db.query(User).filter(User.role == "coach").order_by(User.id).all()
    out = []
    for c in coaches:
        clients = db.query(User).filter(User.coach_id == c.id,
                                        User.role == "client").count()
        skills = db.query(SkillAssignment).filter(
            SkillAssignment.coach_id == c.id,
            SkillAssignment.is_active == True).count()  # noqa: E712
        out.append({"id": c.id, "name": c.name, "email": c.email,
                    "is_active": c.is_active, "valid_until": str(c.valid_until),
                    "token_balance": c.token_balance or 0,
                    "estimated_usd": estimate_usd_for_balance(db, c.token_balance or 0),
                    "clients": clients, "skills": skills})
    return out


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate,
                hc: User = Depends(require_head_coach), db: Session = Depends(get_db)):
    """Head Coach can activate/deactivate, extend validity, or change quota
    for any coach or client."""
    u = db.query(User).get(user_id)
    if not u or u.role == "head_coach":
        raise HTTPException(404, "User not found")
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.extend_days:
        base = max(u.valid_until, date.today()) if u.valid_until else date.today()
        u.valid_until = base + timedelta(days=body.extend_days)
    db.commit()
    return {"ok": True, "id": u.id, "is_active": u.is_active,
            "valid_until": str(u.valid_until)}


@router.get("/coaches/template")
def coaches_template(hc: User = Depends(require_head_coach)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "email", "password", "opening_credits", "validity_days"])
    w.writerow(["Jane Coach", "jane@example.com", "temp12345", "1000000", "365"])
    from fastapi.responses import StreamingResponse
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="coaches_template.csv"'})


@router.post("/coaches/bulk")
async def coaches_bulk_upload(file: UploadFile = File(...),
                              hc: User = Depends(require_head_coach),
                              db: Session = Depends(get_db)):
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    required = {"name", "email", "password"}
    if not required.issubset({(h or "").strip() for h in (reader.fieldnames or [])}):
        raise HTTPException(400, "CSV must have at least 'name', 'email' and 'password' columns")

    created, errors = [], []
    seen_emails = set()
    for i, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        email = (row.get("email") or "").strip().lower()
        password = (row.get("password") or "").strip()
        try:
            opening_credits = int(float(row.get("opening_credits") or 0))
        except ValueError:
            opening_credits = 0
        try:
            validity_days = int(float(row.get("validity_days") or 365))
        except ValueError:
            validity_days = 365

        if not name or not email or not password:
            errors.append(f"Row {i}: name, email and password are required — skipped")
            continue
        if len(password) < 8:
            errors.append(f"Row {i} ({email}): password must be at least 8 characters — skipped")
            continue
        if email in seen_emails or db.query(User).filter(User.email == email).first():
            errors.append(f"Row {i} ({name}, {email}): email already exists — skipped")
            continue

        db.add(User(name=name, email=email, password_hash=hash_password(password),
                    role="coach", token_balance=max(0, opening_credits),
                    valid_from=date.today(),
                    valid_until=date.today() + timedelta(days=validity_days)))
        seen_emails.add(email)
        created.append(email)
    db.commit()
    return {"ok": True, "created": len(created), "emails": created, "errors": errors}


# ---------- Skill assignments (lease to coach) ----------

@router.post("/assignments")
def assign_skill(body: AssignIn, hc: User = Depends(require_head_coach),
                 db: Session = Depends(get_db)):
    """Lease a skill to one, several, or all coaches at once."""
    skill = db.query(Skill).get(body.skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if body.all_coaches:
        coaches = db.query(User).filter(User.role == "coach",
                                        User.is_active == True).all()  # noqa: E712
    else:
        coaches = db.query(User).filter(User.id.in_(body.coach_ids),
                                        User.role == "coach").all()
    if not coaches:
        raise HTTPException(404, "No matching coaches found")
    for coach in coaches:
        existing = db.query(SkillAssignment).filter(
            SkillAssignment.skill_id == skill.id,
            SkillAssignment.coach_id == coach.id).first()
        if existing:
            existing.is_active = True
        else:
            db.add(SkillAssignment(skill_id=skill.id, coach_id=coach.id,
                                   assigned_by=hc.id))
    db.commit()
    return {"ok": True, "skill": skill.title,
            "coaches": [c.name for c in coaches]}


# ---------- Credits ----------

@router.post("/credits")
def issue_credits(body: IssueCreditsIn, hc: User = Depends(require_head_coach),
                  db: Session = Depends(get_db)):
    coach = db.query(User).filter(User.id == body.coach_id,
                                  User.role == "coach").first()
    if not coach:
        raise HTTPException(404, "Coach not found")
    transfer_credits(db, hc, coach, body.tokens, body.note)
    return {"ok": True, "coach": coach.name,
            "new_balance": coach.token_balance}


@router.get("/credits")
def credit_history(hc: User = Depends(require_head_coach),
                   db: Session = Depends(get_db)):
    rows = (db.query(CreditTransaction, User)
            .join(User, CreditTransaction.to_user_id == User.id)
            .order_by(CreditTransaction.id.desc()).limit(200).all())
    return [{"id": t.id, "to": u.name, "to_role": u.role, "tokens": t.tokens,
             "note": t.note, "at": str(t.created_at)} for t, u in rows]


# ---------- Model options ----------

@router.get("/models")
def list_model_options(hc: User = Depends(require_head_coach),
                       db: Session = Depends(get_db)):
    return [{"id": m.id, "model_id": m.model_id, "display_name": m.display_name,
             "is_default": m.is_default, "is_active": m.is_active,
             "input_cost_per_mtok": m.input_cost_per_mtok,
             "output_cost_per_mtok": m.output_cost_per_mtok}
            for m in db.query(ModelOption).order_by(ModelOption.id).all()]


class ModelCostIn(BaseModel):
    input_cost_per_mtok: float
    output_cost_per_mtok: float


@router.patch("/models/{mid}/cost")
def update_model_cost(mid: int, body: ModelCostIn,
                      hc: User = Depends(require_head_coach),
                      db: Session = Depends(get_db)):
    m = db.query(ModelOption).get(mid)
    if not m:
        raise HTTPException(404, "Model not found")
    m.input_cost_per_mtok = body.input_cost_per_mtok
    m.output_cost_per_mtok = body.output_cost_per_mtok
    db.commit()
    return {"ok": True}


@router.post("/models")
def add_model(body: ModelIn, hc: User = Depends(require_head_coach),
              db: Session = Depends(get_db)):
    if db.query(ModelOption).filter(ModelOption.model_id == body.model_id).first():
        raise HTTPException(400, "Model already exists")
    if body.is_default:
        db.query(ModelOption).update({ModelOption.is_default: False})
    db.add(ModelOption(model_id=body.model_id.strip(),
                       display_name=body.display_name.strip(),
                       is_default=body.is_default,
                       input_cost_per_mtok=body.input_cost_per_mtok,
                       output_cost_per_mtok=body.output_cost_per_mtok))
    db.commit()
    return {"ok": True}


@router.patch("/models/{mid}")
def update_model(mid: int, is_active: Optional[bool] = None,
                 is_default: Optional[bool] = None,
                 hc: User = Depends(require_head_coach),
                 db: Session = Depends(get_db)):
    m = db.query(ModelOption).get(mid)
    if not m:
        raise HTTPException(404, "Model not found")
    if is_active is not None:
        m.is_active = is_active
    if is_default:
        db.query(ModelOption).update({ModelOption.is_default: False})
        m.is_default = True
        m.is_active = True
    db.commit()
    return {"ok": True}


@router.delete("/assignments")
def revoke_assignment(skill_id: int, coach_id: int,
                      hc: User = Depends(require_head_coach),
                      db: Session = Depends(get_db)):
    a = db.query(SkillAssignment).filter(
        SkillAssignment.skill_id == skill_id,
        SkillAssignment.coach_id == coach_id).first()
    if not a:
        raise HTTPException(404, "Assignment not found")
    a.is_active = False
    db.commit()
    return {"ok": True, "message": "Assignment revoked (coach and their clients lose access)"}


@router.get("/assignments")
def list_assignments(hc: User = Depends(require_head_coach),
                     db: Session = Depends(get_db)):
    rows = (db.query(SkillAssignment, Skill, User)
            .join(Skill, SkillAssignment.skill_id == Skill.id)
            .join(User, SkillAssignment.coach_id == User.id)
            .order_by(SkillAssignment.id).all())
    return [{"id": a.id, "skill_id": s.id, "skill": s.title,
             "coach_id": u.id, "coach": u.name, "is_active": a.is_active}
            for a, s, u in rows]
