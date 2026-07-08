# SkillCoach — Phase 4: Chat Engine (Claude API + Quotas)

## What's new
- `services/claude_service.py` (new)
- `services/quota_service.py` (new)
- `routers/chat_routes.py` (new)
- `main.py` updated

Updating your folder: add the 3 new files, replace `main.py`.
New install inside your venv:
```
pip install anthropic
```

## Configure your API key
In `.env`, set:
```
ANTHROPIC_API_KEY=sk-ant-...     (from console.anthropic.com → API Keys)
```
Optional overrides: `CLAUDE_MODEL` (default claude-sonnet-4-6),
`CLAUDE_MAX_TOKENS` (default 2000).

⚠️ From this phase on, tests make REAL Claude API calls that cost real
(small) money. A short test chat costs well under ₹5.

## Test checklist (in /docs)

As **Head Coach**: make sure a skill exists with a meaningful system prompt,
e.g. "You are an expert sales coach. Keep answers short and practical."
And ensure the chain from Phase 2–3 exists (skill → coach → client grant).

As **Client** (Authorize as the client):
1. **GET /api/chat/skills** → only your granted skills appear
2. **POST /api/chat/conversations** `{"skill_id":1}` → conversation created
3. **POST /api/chat/conversations/1/messages** `{"content":"How do I handle price objections?"}`
   → real Claude reply, styled by the skill's system prompt ✨
4. Send a follow-up in the same conversation → Claude remembers context
5. **GET /api/chat/conversations/1/messages** → full history stored
6. **GET /api/chat/usage** → tokens counted against your quota

Boundary checks:
7. Try **POST /api/chat/conversations** with a skill_id you're NOT granted → **403**
8. As Head Coach, disable the skill (PATCH /api/admin/skills/1 {"is_enabled":false})
   → client's **GET /api/chat/skills** goes empty, sending a message → **403**.
   Re-enable it afterwards.
9. (Optional) Set the client's quota very low via PATCH /api/coach/clients/{id}
   {"monthly_token_quota": 100}, send a message → next message returns **429**.
   Restore the quota afterwards.

All pass → Phase 4 complete ✅ → Phase 5: the frontend (login + three dashboards).
