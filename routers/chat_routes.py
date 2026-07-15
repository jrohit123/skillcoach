"""
routers/chat_routes.py — chat engine for all roles.
Adds: model choice per conversation, auto-"start" first message,
AI-generated titles, rename, credit balances, coach branding lookup.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (get_db, User, Skill, SkillAssignment, SkillGrant,
                      Conversation, Message, ModelOption, SkillCategory)
from auth import get_current_user
from services.claude_service import call_claude, generate_title, DEFAULT_MODEL
from services.quota_service import check_credits, record_usage, get_usage
from services.pricing_service import estimate_usd_for_balance

router = APIRouter(prefix="/api/chat", tags=["chat"])

AUTO_START = "start"


class NewConversationIn(BaseModel):
    skill_id: int
    model_id: str = ""


class SendMessageIn(BaseModel):
    content: str


class RenameIn(BaseModel):
    title: str


class EditMessageIn(BaseModel):
    content: str


# ---------- Access helpers ----------

def can_use_skill(user: User, skill: Skill, db: Session) -> bool:
    if not skill or not skill.is_enabled:
        return False
    if user.role == "head_coach":
        return True
    if user.role == "coach":
        return db.query(SkillAssignment).filter(
            SkillAssignment.skill_id == skill.id,
            SkillAssignment.coach_id == user.id,
            SkillAssignment.is_active == True).first() is not None  # noqa: E712
    grant = db.query(SkillGrant).filter(
        SkillGrant.skill_id == skill.id,
        SkillGrant.client_id == user.id,
        SkillGrant.is_active == True).first()  # noqa: E712
    if not grant:
        return False
    lease = db.query(SkillAssignment).filter(
        SkillAssignment.skill_id == skill.id,
        SkillAssignment.coach_id == user.coach_id,
        SkillAssignment.is_active == True).first()  # noqa: E712
    return lease is not None


def get_owned_conversation(user: User, conv_id: int, db: Session) -> Conversation:
    conv = db.query(Conversation).get(conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return conv


def resolve_model(db: Session, requested: str) -> str:
    opts = db.query(ModelOption).filter(ModelOption.is_active == True).all()  # noqa: E712
    if requested and any(o.model_id == requested for o in opts):
        return requested
    default = next((o.model_id for o in opts if o.is_default), None)
    return default or DEFAULT_MODEL


# ---------- Models & branding ----------

@router.get("/models")
def list_models(user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    opts = (db.query(ModelOption).filter(ModelOption.is_active == True)  # noqa: E712
            .order_by(ModelOption.id).all())
    return [{"model_id": o.model_id, "display_name": o.display_name,
             "is_default": o.is_default} for o in opts]


@router.get("/branding")
def branding(user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """Coach sees their own branding; a client sees their coach's."""
    src = None
    if user.role == "coach":
        src = user
    elif user.role == "client" and user.coach_id:
        src = db.query(User).get(user.coach_id)
    if not src or not (src.brand_name or src.brand_logo):
        return {"brand_name": "", "brand_logo": "", "brand_about": "", "brand_website": ""}
    return {"brand_name": src.brand_name, "brand_logo": src.brand_logo,
            "brand_about": src.brand_about, "brand_website": src.brand_website}


@router.get("/skill-categories")
def ordered_categories(user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """Ordered category names, for the chat sidebar (all roles)."""
    rows = db.query(SkillCategory).order_by(SkillCategory.sort_order,
                                            SkillCategory.name).all()
    return [r.name for r in rows]


# ---------- Available skills ----------

@router.get("/skills")
def available_skills(user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    skills = db.query(Skill).filter(Skill.is_enabled == True).order_by(Skill.id).all()  # noqa: E712
    return [{"id": s.id, "title": s.title, "description": s.description,
             "category": (s.category or "").strip()}
            for s in skills if can_use_skill(user, s, db)]


# ---------- Conversations ----------

@router.post("/conversations")
def new_conversation(body: NewConversationIn,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    skill = db.query(Skill).get(body.skill_id)
    if not can_use_skill(user, skill, db):
        raise HTTPException(403, "You don't have access to this skill")
    check_credits(db, user)

    model = resolve_model(db, body.model_id)
    conv = Conversation(user_id=user.id, skill_id=skill.id, model_id=model)
    db.add(conv)
    db.commit()
    db.refresh(conv)

    # Auto-send "start" so the skill greets the user immediately
    result = call_claude(skill.system_prompt, [], AUTO_START, model=model)
    db.add(Message(conversation_id=conv.id, role="user", content=AUTO_START,
                   input_tokens=result["input_tokens"], output_tokens=0))
    db.add(Message(conversation_id=conv.id, role="assistant",
                   content=result["text"], input_tokens=0,
                   output_tokens=result["output_tokens"]))
    db.commit()
    record_usage(db, user, result["input_tokens"] + result["output_tokens"])

    return {"id": conv.id, "skill_id": skill.id, "skill": skill.title,
            "title": conv.title, "model_id": model,
            "greeting": result["text"]}


@router.get("/conversations")
def my_conversations(user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    rows = (db.query(Conversation, Skill)
            .join(Skill, Conversation.skill_id == Skill.id)
            .filter(Conversation.user_id == user.id)
            .order_by(Conversation.id.desc()).all())
    return [{"id": c.id, "title": c.title, "skill": s.title,
             "skill_id": s.id, "model_id": c.model_id,
             "created_at": str(c.created_at)} for c, s in rows]


@router.patch("/conversations/{conv_id}")
def rename_conversation(conv_id: int, body: RenameIn,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    conv = get_owned_conversation(user, conv_id, db)
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "Title cannot be empty")
    conv.title = title[:200]
    db.commit()
    return {"ok": True, "id": conv.id, "title": conv.title}


@router.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    conv = get_owned_conversation(user, conv_id, db)
    msgs = (db.query(Message)
            .filter(Message.conversation_id == conv.id,
                    Message.superseded == False)  # noqa: E712
            .order_by(Message.id).all())
    return [{"id": m.id, "role": m.role, "content": m.content,
             "created_at": str(m.created_at)} for m in msgs]


# ---------- Send a message ----------

@router.post("/conversations/{conv_id}/messages")
def send_message(conv_id: int, body: SendMessageIn,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "Message cannot be empty")

    conv = get_owned_conversation(user, conv_id, db)
    skill = db.query(Skill).get(conv.skill_id)
    if not can_use_skill(user, skill, db):
        raise HTTPException(403, "Access to this skill has been revoked or disabled")

    check_credits(db, user)

    history = [{"role": m.role, "content": m.content}
               for m in db.query(Message)
               .filter(Message.conversation_id == conv.id,
                       Message.superseded == False)  # noqa: E712
               .order_by(Message.id).all()]

    result = call_claude(skill.system_prompt, history, content,
                         model=conv.model_id)

    db.add(Message(conversation_id=conv.id, role="user", content=content,
                   input_tokens=result["input_tokens"], output_tokens=0))
    db.add(Message(conversation_id=conv.id, role="assistant",
                   content=result["text"],
                   input_tokens=0, output_tokens=result["output_tokens"]))

    # AI title after the first real user message
    if conv.title == "New conversation":
        conv.title = generate_title(content, result["text"])

    db.commit()
    record_usage(db, user, result["input_tokens"] + result["output_tokens"])

    return {"reply": result["text"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "conversation_title": conv.title}


# ---------- Edit a message (fork: soft-deletes later turns) ----------

@router.patch("/conversations/{conv_id}/messages/{msg_id}")
def edit_message(conv_id: int, msg_id: int, body: EditMessageIn,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "Message cannot be empty")

    conv = get_owned_conversation(user, conv_id, db)
    skill = db.query(Skill).get(conv.skill_id)
    if not can_use_skill(user, skill, db):
        raise HTTPException(403, "Access to this skill has been revoked or disabled")

    msg = db.query(Message).filter(Message.id == msg_id,
                                   Message.conversation_id == conv.id).first()
    if not msg or msg.role != "user" or msg.superseded:
        raise HTTPException(404, "Message not found or not editable")
    if msg.content == AUTO_START:
        first = (db.query(Message)
                 .filter(Message.conversation_id == conv.id)
                 .order_by(Message.id).first())
        if first and first.id == msg.id:
            raise HTTPException(400, "The opening message cannot be edited")

    check_credits(db, user)

    # soft-delete the edited message and everything after it
    (db.query(Message)
       .filter(Message.conversation_id == conv.id, Message.id >= msg.id)
       .update({Message.superseded: True}))
    db.commit()

    # rebuild history from what remains, then re-ask with the edited text
    history = [{"role": m.role, "content": m.content}
               for m in db.query(Message)
               .filter(Message.conversation_id == conv.id,
                       Message.superseded == False)  # noqa: E712
               .order_by(Message.id).all()]

    result = call_claude(skill.system_prompt, history, content,
                         model=conv.model_id)

    db.add(Message(conversation_id=conv.id, role="user", content=content,
                   input_tokens=result["input_tokens"], output_tokens=0))
    db.add(Message(conversation_id=conv.id, role="assistant",
                   content=result["text"], input_tokens=0,
                   output_tokens=result["output_tokens"]))
    db.commit()
    record_usage(db, user, result["input_tokens"] + result["output_tokens"])

    return {"reply": result["text"], "conversation_title": conv.title}


# ---------- My usage / balance ----------

@router.get("/usage")
def my_usage(user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    return {"tokens_used_this_month": get_usage(db, user.id),
            "token_balance": user.token_balance or 0,
            "unlimited": user.role == "head_coach",
            "estimated_usd": estimate_usd_for_balance(db, user.token_balance or 0)}
