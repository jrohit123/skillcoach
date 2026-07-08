# SkillCoach — Phase 6: Reports (transcripts, credit audit trail, usage)

## What's new
- `routers/reports_routes.py` (new)
- `static/js/reports.js` (new)
- `main.py`, `static/headcoach.html`, `static/coach.html`, `static/client.html` (updated)

Updating: add the 2 new files, replace the 4 updated ones. No new installs.

## What it does
A new **📊 Reports** tab for Head Coach and Coach with three views:

1. **Chat transcripts** — filterable by user, skill, and date range; "View"
   opens the full read-only transcript in a popup.
2. **Credit ledger** — the permanent audit trail: every issue, allocation and
   reclaim with from/to/amount/note/timestamp. Green = given, red = reclaimed.
3. **Usage** — tokens consumed per user for any month, plus current balances.

Clients get a small "My credits" card in their sidebar showing credits received.

## Scope rules (test these!)
- Head Coach: everything, platform-wide
- Coach: own + own clients' transcripts; credit txns involving them or their
  clients; usage of self + own clients
- Client: own transcripts (already in chat history); own credit receipts

## Test checklist
1. Head Coach → Reports → all three views show platform-wide data
2. Filter transcripts by a specific client and date → list narrows correctly
3. Open a transcript → full conversation displays read-only
4. Coach → Reports → sees ONLY their own + their clients' conversations
5. Coach's credit ledger shows credits received from HC + allocations to their
   clients — but NOT another coach's transactions
6. Client login → "My credits" card lists credits received from their coach
7. Usage view: pick the current month → per-user token totals + balances

All pass → Phase 6 complete ✅ → Phase 7: Railway deployment (the finale).
