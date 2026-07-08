# SkillCoach — Phase 5: Frontend (Phenom branding)

## What's new
- `static/` folder: login.html, client.html, coach.html, headcoach.html,
  css/style.css, js/api.js, js/chat.js
- `main.py` updated (serves static files; / redirects to login)

Updating your folder: copy the whole `static/` folder in, replace `main.py`.
No new installs.

## Run
```
uvicorn main:app --reload
```
Open **http://127.0.0.1:8000** — you should land on the SkillCoach login page
(Phenom Business Coaching Systems, Montserrat, light gradient, aitamate footer).

## Test checklist (in the browser this time!)

1. **Login as Head Coach** → lands on the Head Coach dashboard
2. **Skills tab**: create a skill via "+ New skill" (title, description, system prompt),
   edit it, disable/enable it
3. **Coaches tab**: create a coach with a temporary password
4. **Assignments tab**: lease the skill to the coach
5. **Chat tab**: start a conversation as Head Coach — real Claude replies in the UI
6. **Log out → log in as the coach** with the temp password →
   you should be forced to set a new password first
7. Coach dashboard → **My clients**: create a client; **Skill grants**: grant the skill
8. Coach → **Chat**: coach can chat with their leased skill; usage bar updates
9. **Log out → log in as the client** (temp password → forced change)
10. Client sees ONLY the chat: pick skill → New conversation → chat with running
    history; conversations appear in the left list with auto-titles; reopening an
    old conversation restores the full history
11. Mobile check (optional): shrink the browser window — layout stacks vertically
12. Footer check: "Developed by" + aitamate logo → opens www.aitamate.com in a new tab

All pass → Phase 5 complete ✅ → Phase 6: Reports (transcripts + usage, role-scoped).
