# SkillCoach — Phase 3: Coach Layer

## What's new
- `routers/coach_routes.py` (new file)
- `main.py` updated to register it

Updating your existing folder: add the new file, replace `main.py`. No new installs.

## Run
```
uvicorn main:app --reload
```

## Test checklist (in /docs)

As **Head Coach**:
1. Make sure you have a skill (id 1), a coach (from Phase 2), and the skill assigned to that coach.
2. **POST /api/coach/clients** WITHOUT coach_id → should return **400** ("coach_id is required")
3. **POST /api/coach/clients** WITH coach_id →
   `{"name":"Test Client","email":"client1@test.com","password":"temppass123","coach_id":2}` → client created

As **Coach** (Authorize with the coach account):
4. **GET /api/coach/my-skills** → shows only skills leased to you
5. **POST /api/coach/clients** (no coach_id needed) → creates a client under you
6. **POST /api/coach/grants** `{"skill_id":1,"client_id":<your client's id>}` → grant works
7. **GET /api/coach/grants** → shows the grant
8. **DELETE /api/coach/grants?skill_id=1&client_id=X** → revoke works
9. **PATCH /api/coach/clients/{id}** `{"extend_days":90}` → validity extends

Boundary checks:
10. As a **Client** (log in as one): **GET /api/coach/clients** → **403**
11. Try granting a skill that is NOT leased to the client's coach → **403**

All pass → Phase 3 complete ✅ → Phase 4 next: the chat engine (Claude API + quotas) — the heart of the system. Have your ANTHROPIC_API_KEY ready in .env for that one.
