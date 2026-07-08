# SkillCoach — Phase 1 Setup

## Step 1 — Create the Railway PostgreSQL database
1. Go to railway.app → New Project → **Deploy PostgreSQL** (just the database, no app yet).
2. Click the PostgreSQL service → **Variables** tab → copy the value of **DATABASE_PUBLIC_URL**.
   (Use the PUBLIC url for now, since the app runs on your laptop.)

## Step 2 — Set up the project locally
Open a terminal in the folder where you extracted these files, then:

```
python -m venv venv
venv\Scripts\activate          (Windows)
# source venv/bin/activate     (Mac/Linux)

pip install -r requirements.txt
```

## Step 3 — Configure environment
1. Copy `.env.example` to a new file named `.env`
2. Paste your Railway DATABASE_PUBLIC_URL into `DATABASE_URL`
3. Generate a JWT secret:  `python -c "import secrets; print(secrets.token_hex(32))"` and paste it
4. Set your Head Coach email + password

## Step 4 — Run it
```
uvicorn main:app --reload
```
You should see: `✅ Head Coach account created: ...`

## Step 5 — Test it
Open http://127.0.0.1:8000/docs in your browser (FastAPI's built-in test UI):

1. **GET /api/health** → should return `{"status":"ok","phase":1}`
2. Click **Authorize** (top right) → enter your Head Coach email as username + your password → Authorize
3. **GET /api/auth/me** → should return your Head Coach details
4. Try **POST /api/auth/change-password** if you want

If all 4 work, Phase 1 is complete ✅ — tell Claude and we move to Phase 2 (skills + coach management).

## Troubleshooting
- `connection refused` → DATABASE_URL wrong; re-copy DATABASE_PUBLIC_URL from Railway
- `⚠️ HEADCOACH_EMAIL not set` → your `.env` file is missing or misnamed (must be exactly `.env`)
- bcrypt error on Windows → run `pip install bcrypt==4.0.1` again inside the venv
