# SkillCoach — Phase 2: Head Coach Admin

## What's new
- `routers/admin_routes.py` (new file)
- `main.py` updated to register it

If you're updating your existing Phase 1 folder: just add the new
`routers/admin_routes.py` and replace `main.py`. Nothing else changed.
Then run one extra install inside your venv:

```
pip install "pydantic[email]"
```

## Run
```
uvicorn main:app --reload
```
Open http://127.0.0.1:8000/docs and Authorize as Head Coach.

## Test checklist (all in /docs)
1. **POST /api/admin/skills** — create a skill:
   `{"title": "Sales Coaching", "description": "Test", "system_prompt": "You are an expert sales coach..."}`
2. **GET /api/admin/skills** — see it listed
3. **POST /api/admin/coaches** — create a coach:
   `{"name": "Test Coach", "email": "coach1@test.com", "password": "temppass123"}`
4. **POST /api/admin/assignments** — `{"skill_id": 1, "coach_id": 2}` (use real IDs from steps 1 & 3)
5. **GET /api/admin/assignments** — see the lease
6. Log out (Authorize → Logout), log in as the coach → **GET /api/admin/skills** should return **403** (coaches blocked from admin)
7. Back as Head Coach: **PATCH /api/admin/users/2** with `{"extend_days": 90}` — validity extends
8. **PATCH /api/admin/skills/1** with `{"is_enabled": false}` then `true` — kill switch works

All 8 pass → Phase 2 complete ✅ → tell Claude, we move to Phase 3 (Coach layer: client accounts + skill grants).
