"""
routers/coach_routes.py — Coach layer (Head Coach also has full access).

Coaches can:
  - create client accounts under themselves
  - list their clients, activate/deactivate them, extend validity, set quota
  - grant/revoke their leased skills to their own clients
  - see which skills they've been leased
Head Coach can do all of the above for any coach's clients
(when creating a client, Head Coach must specify coach_id).
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db, User, Skill, SkillAssignment, SkillGrant
from auth import require_coach_or_above, hash_password
from services.quota_service import transfer_credits
from services.pricing_service import estimate_usd_for_balance
import csv, io

router = APIRouter(prefix="/api/coach", tags=["coach"])


# ---------- Schemas ----------

class ClientIn(BaseModel):
    name: str
    email: EmailStr
    password: str                      # temporary
    coach_id: Optional[int] = None     # required only when Head Coach creates
    validity_days: int = 365


class ClientUpdate(BaseModel):
    is_active: Optional[bool] = None
    extend_days: Optional[int] = None


class AllocateIn(BaseModel):
    client_id: int
    tokens: int          # positive = allocate from coach balance, negative = reclaim
    note: str = ""


class BrandingIn(BaseModel):
    brand_name: str = ""
    brand_logo: str = ""       # base64 data URL, max ~500KB
    brand_about: str = ""
    brand_website: str = ""


class GrantIn(BaseModel):
    skill_ids: list[int] = []
    all_skills: bool = False
    client_ids: list[int] = []
    all_clients: bool = False


class ResetPasswordIn(BaseModel):
    user_id: int
    new_password: str   # temporary; user must change on next login


# ---------- Helpers ----------

def resolve_coach_id(user: User, requested: Optional[int], db: Session) -> int:
    """A coach always acts as themselves; Head Coach must name a coach."""
    if user.role == "coach":
        return user.id
    if not requested:
        raise HTTPException(400, "coach_id is required when Head Coach creates a client")
    coach = db.query(User).filter(User.id == requested, User.role == "coach").first()
    if not coach:
        raise HTTPException(404, "Coach not found")
    return coach.id


def get_owned_client(user: User, client_id: int, db: Session) -> User:
    client = db.query(User).filter(User.id == client_id, User.role == "client").first()
    if not client:
        raise HTTPException(404, "Client not found")
    if user.role == "coach" and client.coach_id != user.id:
        raise HTTPException(403, "This client does not belong to you")
    return client


# ---------- My leased skills ----------

@router.get("/my-skills")
def my_skills(user: User = Depends(require_coach_or_above),
              db: Session = Depends(get_db)):
    """Skills available to this coach. Head Coach sees all enabled skills."""
    if user.role == "head_coach":
        skills = db.query(Skill).order_by(Skill.id).all()
        return [{"id": s.id, "title": s.title, "description": s.description,
                 "is_enabled": s.is_enabled} for s in skills]
    rows = (db.query(SkillAssignment, Skill)
            .join(Skill, SkillAssignment.skill_id == Skill.id)
            .filter(SkillAssignment.coach_id == user.id,
                    SkillAssignment.is_active == True)  # noqa: E712
            .order_by(Skill.id).all())
    return [{"id": s.id, "title": s.title, "description": s.description,
             "is_enabled": s.is_enabled} for _, s in rows]



# ---------- Password Reset ----------

@router.post("/reset-password")
def reset_password(body: ResetPasswordIn,
                   user: User = Depends(require_coach_or_above),
                   db: Session = Depends(get_db)):
    target = db.query(User).get(body.user_id)
    if not target or target.role == "head_coach":
        raise HTTPException(404, "User not found")
    # coaches may only reset their own clients
    if user.role == "coach":
        if target.role != "client" or target.coach_id != user.id:
            raise HTTPException(403, "You can only reset your own clients' passwords")
    if len(body.new_password) < 8:
        raise HTTPException(400, "Temporary password must be at least 8 characters")
    target.password_hash = hash_password(body.new_password)
    target.must_change_password = True
    db.commit()
    return {"ok": True, "message": f"Password reset for {target.name}. "
            "They must change it on next login."}

@router.get("/clients/template")
def clients_template(user: User = Depends(require_coach_or_above)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "email", "password", "validity_days"])
    w.writerow(["John Client", "john@example.com", "temp12345", "365"])
    from fastapi.responses import StreamingResponse
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="clients_template.csv"'})


@router.post("/clients/bulk")
async def clients_bulk_upload(file: UploadFile = File(...),
                              user: User = Depends(require_coach_or_above),
                              db: Session = Depends(get_db)):
    coach_id = resolve_coach_id(user, None, db) if user.role == "coach" else None
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    required = {"name", "email", "password"}
    fields = {(h or "").strip() for h in (reader.fieldnames or [])}
    if not required.issubset(fields):
        raise HTTPException(400, "CSV must have at least 'name', 'email' and 'password' columns")
    if user.role == "head_coach" and "coach_email" not in fields:
        raise HTTPException(400,
            "Head Coach uploads need a 'coach_email' column to say which coach each client belongs to")

    created, errors = [], []
    seen_emails = set()
    for i, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        email = (row.get("email") or "").strip().lower()
        password = (row.get("password") or "").strip()
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
            errors.append(f"Row {i} ({email}): email already exists — skipped")
            continue

        row_coach_id = coach_id
        if user.role == "head_coach":
            ce = (row.get("coach_email") or "").strip().lower()
            coach = db.query(User).filter(User.email == ce, User.role == "coach").first()
            if not coach:
                errors.append(f"Row {i} ({email}): coach_email '{ce}' not found — skipped")
                continue
            row_coach_id = coach.id

        db.add(User(name=name, email=email, password_hash=hash_password(password),
                    role="client", coach_id=row_coach_id, token_balance=0,
                    valid_from=date.today(),
                    valid_until=date.today() + timedelta(days=validity_days)))
        seen_emails.add(email)
        created.append(email)
    db.commit()
    return {"ok": True, "created": len(created), "emails": created, "errors": errors}


# ---------- Clients ----------

@router.post("/clients")
def create_client(body: ClientIn, user: User = Depends(require_coach_or_above),
                  db: Session = Depends(get_db)):
    coach_id = resolve_coach_id(user, body.coach_id, db)
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Email already exists")
    if len(body.password) < 8:
        raise HTTPException(400, "Temporary password must be at least 8 characters")
    cl = User(name=body.name.strip(), email=email,
              password_hash=hash_password(body.password), role="client",
              coach_id=coach_id, token_balance=0,
              valid_from=date.today(),
              valid_until=date.today() + timedelta(days=body.validity_days))
    db.add(cl)
    db.commit()
    db.refresh(cl)
    return {"id": cl.id, "name": cl.name, "email": cl.email,
            "coach_id": cl.coach_id, "valid_until": str(cl.valid_until)}


@router.get("/clients")
def list_clients(user: User = Depends(require_coach_or_above),
                 db: Session = Depends(get_db)):
    q = db.query(User).filter(User.role == "client")
    if user.role == "coach":
        q = q.filter(User.coach_id == user.id)
    clients = q.order_by(User.id).all()
    out = []
    for cl in clients:
        grants = db.query(SkillGrant).filter(
            SkillGrant.client_id == cl.id,
            SkillGrant.is_active == True).count()  # noqa: E712
        out.append({"id": cl.id, "name": cl.name, "email": cl.email,
                    "coach_id": cl.coach_id, "is_active": cl.is_active,
                    "valid_until": str(cl.valid_until),
                    "token_balance": cl.token_balance or 0,
                    "estimated_usd": estimate_usd_for_balance(db, cl.token_balance or 0),
                    "granted_skills": grants})
    return out


@router.patch("/clients/{client_id}")
def update_client(client_id: int, body: ClientUpdate,
                  user: User = Depends(require_coach_or_above),
                  db: Session = Depends(get_db)):
    cl = get_owned_client(user, client_id, db)
    if body.is_active is not None:
        cl.is_active = body.is_active
    if body.extend_days:
        base = max(cl.valid_until, date.today()) if cl.valid_until else date.today()
        cl.valid_until = base + timedelta(days=body.extend_days)
    db.commit()
    return {"ok": True, "id": cl.id, "is_active": cl.is_active,
            "valid_until": str(cl.valid_until)}


# ---------- Credits (coach -> client, from coach's own balance) ----------

@router.post("/credits")
def allocate_credits(body: AllocateIn,
                     user: User = Depends(require_coach_or_above),
                     db: Session = Depends(get_db)):
    client = get_owned_client(user, body.client_id, db)
    source = user
    if user.role == "head_coach":
        # HC allocating directly to a client draws from the client's coach
        # would be confusing; HC issues from the infinite pool instead.
        pass
    transfer_credits(db, source, client, body.tokens, body.note)
    return {"ok": True, "client": client.name,
            "client_balance": client.token_balance,
            "your_balance": None if user.role == "head_coach" else user.token_balance}


@router.get("/my-balance")
def my_balance(user: User = Depends(require_coach_or_above),
               db: Session = Depends(get_db)):
    return {"token_balance": user.token_balance or 0,
            "unlimited": user.role == "head_coach",
            "estimated_usd": estimate_usd_for_balance(db, user.token_balance or 0)}


# ---------- Branding ----------

@router.get("/branding")
def get_branding(user: User = Depends(require_coach_or_above),
                 db: Session = Depends(get_db)):
    return {"brand_name": user.brand_name or "", "brand_logo": user.brand_logo or "",
            "brand_about": user.brand_about or "", "brand_website": user.brand_website or ""}


@router.patch("/branding")
def set_branding(body: BrandingIn,
                 user: User = Depends(require_coach_or_above),
                 db: Session = Depends(get_db)):
    if len(body.brand_logo) > 700_000:
        raise HTTPException(400, "Logo too large — please use an image under 500KB")
    user.brand_name = body.brand_name.strip()[:200]
    user.brand_logo = body.brand_logo
    user.brand_about = body.brand_about.strip()[:1000]
    user.brand_website = body.brand_website.strip()[:300]
    db.commit()
    return {"ok": True}


# ---------- Skill grants (coach -> client) ----------

@router.post("/grants")
@router.post("/grants")
def grant_skill(body: GrantIn, user: User = Depends(require_coach_or_above),
                db: Session = Depends(get_db)):
    """Grant one or several skills to one, several, or all clients — every
    combination of the two selections gets an active grant."""
    if body.all_skills:
        skills = db.query(Skill).filter(Skill.is_enabled == True).all()  # noqa: E712
    else:
        skills = db.query(Skill).filter(Skill.id.in_(body.skill_ids)).all()
    if not skills:
        raise HTTPException(404, "No matching skills found")

    # resolve the client list
    if body.all_clients:
        q = db.query(User).filter(User.role == "client", User.is_active == True)
        if user.role == "coach":
            q = q.filter(User.coach_id == user.id)
        clients = q.all()
    else:
        clients = []
        for cid in body.client_ids:
            cl = get_owned_client(user, cid, db)
            clients.append(cl)

    if not clients:
        raise HTTPException(404, "No matching clients found")

    # each client's coach must hold an active lease on each skill being granted
    granted_skills, skipped = [], []
    for skill in skills:
        lease_ok_for_any = False
        for client in clients:
            coach_id = user.id if user.role == "coach" else client.coach_id
            lease = db.query(SkillAssignment).filter(
                SkillAssignment.skill_id == skill.id,
                SkillAssignment.coach_id == coach_id,
                SkillAssignment.is_active == True).first()  # noqa: E712
            if not lease:
                continue
            lease_ok_for_any = True
            existing = db.query(SkillGrant).filter(
                SkillGrant.skill_id == skill.id,
                SkillGrant.client_id == client.id).first()
            if existing:
                existing.is_active = True
            else:
                db.add(SkillGrant(skill_id=skill.id, client_id=client.id,
                                  granted_by=user.id))
        if lease_ok_for_any:
            granted_skills.append(skill.title)
        else:
            skipped.append(skill.title)
    db.commit()

    if not granted_skills:
        raise HTTPException(403,
            "None of the selected skills are leased to the relevant coach(es)")
    return {"ok": True, "skills": granted_skills,
            "clients": [c.name for c in clients],
            "skipped_not_leased": skipped}


@router.delete("/grants")
def revoke_grant(skill_id: int, client_id: int,
                 user: User = Depends(require_coach_or_above),
                 db: Session = Depends(get_db)):
    client = get_owned_client(user, client_id, db)
    g = db.query(SkillGrant).filter(
        SkillGrant.skill_id == skill_id,
        SkillGrant.client_id == client.id).first()
    if not g:
        raise HTTPException(404, "Grant not found")
    g.is_active = False
    db.commit()
    return {"ok": True, "message": "Grant revoked"}


@router.get("/grants")
def list_grants(user: User = Depends(require_coach_or_above),
                db: Session = Depends(get_db)):
    q = (db.query(SkillGrant, Skill, User)
         .join(Skill, SkillGrant.skill_id == Skill.id)
         .join(User, SkillGrant.client_id == User.id))
    if user.role == "coach":
        q = q.filter(User.coach_id == user.id)
    rows = q.order_by(SkillGrant.id).all()
    return [{"id": g.id, "skill_id": s.id, "skill": s.title,
             "client_id": u.id, "client": u.name, "is_active": g.is_active}
            for g, s, u in rows]
