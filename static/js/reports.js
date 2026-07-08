/* reports.js — Reports panel: sortable, paginated, exportable. Requires api.js. */

const Reports = {
  state: { rows: [], sortKey: null, sortDir: -1, page: 1, pageSize: 20, view: "T" },

  async render() {
    el("main").innerHTML = `
      <div class="card">
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn small" id="rTabT">Chat transcripts</button>
          <button class="btn small ghost" id="rTabC">Credit ledger</button>
          <button class="btn small ghost" id="rTabU">Usage</button>
        </div>
      </div>
      <div id="rBody"></div>`;
    ["T", "C", "U"].forEach(k => el("rTab" + k).onclick = () => Reports.switch(k));
    Reports.switch("T");
  },

  switch(which) {
    ["T", "C", "U"].forEach(k =>
      el("rTab" + k).className = "btn small" + (k === which ? "" : " ghost"));
    Reports.state = { rows: [], sortKey: null, sortDir: -1, page: 1,
                      pageSize: Reports.state.pageSize, view: which };
    ({ T: Reports.transcripts, C: Reports.credits, U: Reports.usage })[which]();
  },

  /* ---------- shared table plumbing ---------- */

  sortRows() {
    const { sortKey, sortDir } = Reports.state;
    if (!sortKey) return Reports.state.rows;
    return [...Reports.state.rows].sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (typeof x === "number" && typeof y === "number") return (x - y) * sortDir;
      return String(x ?? "").localeCompare(String(y ?? "")) * sortDir;
    });
  },

  pageRows() {
    const s = Reports.state;
    const sorted = Reports.sortRows();
    const start = (s.page - 1) * s.pageSize;
    return sorted.slice(start, start + s.pageSize);
  },

  th(label, key) {
    const s = Reports.state;
    const arrow = s.sortKey === key ? (s.sortDir === 1 ? " ▲" : " ▼") : "";
    return `<th style="cursor:pointer; user-select:none;"
      onclick="Reports.sortBy('${key}')">${label}${arrow}</th>`;
  },

  sortBy(key) {
    const s = Reports.state;
    if (s.sortKey === key) s.sortDir *= -1;
    else { s.sortKey = key; s.sortDir = 1; }
    s.page = 1;
    Reports.redraw();
  },

  pagerHTML() {
    const s = Reports.state;
    const total = s.rows.length;
    const pages = Math.max(1, Math.ceil(total / s.pageSize));
    if (s.page > pages) s.page = pages;
    return `
      <div style="display:flex; align-items:center; gap:12px; margin-top:12px;
                  font-size:13px; color:var(--ink-soft); flex-wrap:wrap;">
        <span><b>${total}</b> record${total === 1 ? "" : "s"}</span>
        <span>Show
          <select style="width:auto; padding:4px 6px;" onchange="Reports.setPageSize(this.value)">
            ${[10, 20, 50, 100].map(n =>
              `<option value="${n}" ${n === s.pageSize ? "selected" : ""}>${n}</option>`).join("")}
          </select> per page
        </span>
        <span>
          <button class="btn small ghost" ${s.page <= 1 ? "disabled" : ""}
            onclick="Reports.setPage(${s.page - 1})">‹ Prev</button>
          Page ${s.page} of ${pages}
          <button class="btn small ghost" ${s.page >= pages ? "disabled" : ""}
            onclick="Reports.setPage(${s.page + 1})">Next ›</button>
        </span>
      </div>`;
  },

  setPageSize(n) { Reports.state.pageSize = parseInt(n); Reports.state.page = 1; Reports.redraw(); },
  setPage(p) { Reports.state.page = p; Reports.redraw(); },

  redraw() {
    ({ T: Reports.drawTranscripts, C: Reports.drawCredits,
       U: Reports.drawUsage })[Reports.state.view]();
  },

  /* ---------- Transcripts ---------- */

  async transcripts() {
    const f = await API.get("/api/reports/filters");
    el("rBody").innerHTML = `
      <div class="card">
        <h2>Chat transcripts</h2>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr auto auto; gap:0 12px; align-items:end;">
          <div><label>User</label><select id="rfUser"><option value="">All</option>
            ${f.users.map(u => `<option value="${u.id}">${esc(u.name)} (${u.role.replace("_", " ")})</option>`).join("")}
          </select></div>
          <div><label>Skill</label><select id="rfSkill"><option value="">All</option>
            ${f.skills.map(s => `<option value="${s.id}">${esc(s.title)}</option>`).join("")}
          </select></div>
          <div><label>From</label><input id="rfFrom" type="date"></div>
          <div><label>To</label><input id="rfTo" type="date"></div>
          <button class="btn" id="rfGo">Filter</button>
          <button class="btn ghost" id="rfXlsx">⬇ Excel</button>
        </div>
        <div id="rTable"></div>
      </div>`;
    el("rfGo").onclick = () => Reports.loadTranscripts();
    el("rfXlsx").onclick = () =>
      downloadFile("/api/reports/export/conversations?" + Reports.tQuery(),
                   "skillcoach_transcripts.xlsx");
    await Reports.loadTranscripts();
  },

  tQuery() {
    const p = new URLSearchParams();
    if (el("rfUser").value) p.set("user_id", el("rfUser").value);
    if (el("rfSkill").value) p.set("skill_id", el("rfSkill").value);
    if (el("rfFrom").value) p.set("date_from", el("rfFrom").value);
    if (el("rfTo").value) p.set("date_to", el("rfTo").value);
    return p.toString();
  },

  async loadTranscripts() {
    Reports.state.rows = await API.get("/api/reports/conversations?" + Reports.tQuery());
    Reports.state.page = 1;
    Reports.drawTranscripts();
  },

  drawTranscripts() {
    el("rTable").innerHTML = `
      <table style="margin-top:14px;"><thead><tr>
        ${Reports.th("Title", "title")}${Reports.th("User", "user")}
        ${Reports.th("Skill", "skill")}${Reports.th("Model", "model_id")}
        ${Reports.th("Msgs", "messages")}${Reports.th("Started", "created_at")}<th></th>
      </tr></thead><tbody>
        ${Reports.pageRows().map(c => `
          <tr>
            <td><b>${esc(c.title)}</b></td>
            <td>${esc(c.user)} <span style="color:var(--ink-soft);font-size:11px;">${c.user_role.replace("_", " ")}</span></td>
            <td>${esc(c.skill)}</td>
            <td style="font-size:11px;">${esc(c.model_id || "")}</td>
            <td>${c.messages}</td>
            <td style="font-size:12px;">${fmtDateTime(c.created_at)}</td>
            <td><button class="btn small ghost" onclick="Reports.openTranscript(${c.id})">View</button></td>
          </tr>`).join("") || `<tr><td colspan="7">No conversations match these filters.</td></tr>`}
      </tbody></table>${Reports.pagerHTML()}`;
  },

  async openTranscript(id) {
    const t = await API.get(`/api/reports/conversations/${id}`);
    document.body.insertAdjacentHTML("beforeend", `
      <div class="modal-bg open" id="trModal" onclick="if(event.target===this) this.remove()">
        <div class="card modal" style="max-width:680px;">
          <h2>${esc(t.title)}</h2>
          <p style="font-size:12px;color:var(--ink-soft);margin-bottom:12px;">
            ${esc(t.user)} · ${esc(t.skill)} · ${esc(t.model_id || "")} · ${fmtDateTime(t.created_at)}</p>
          <div class="chat-msgs" style="max-height:52vh;">
            ${t.messages.map(m => `<div class="msg ${m.role}">${esc(m.content)}</div>`).join("")}
          </div>
          <div style="margin-top:14px; display:flex; gap:10px;">
            <button class="btn ghost" onclick="downloadFile('/api/reports/conversations/${t.id}/download','transcript_${t.id}.txt')">⬇ Download .txt</button>
            <button class="btn ghost" onclick="el('trModal').remove()">Close</button>
          </div>
        </div>
      </div>`);
  },

  /* ---------- Credit ledger ---------- */

  async credits() {
    el("rBody").innerHTML = `
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <h2 style="margin:0;">Credit ledger — full audit trail</h2>
          <button class="btn ghost" onclick="downloadFile('/api/reports/export/credits','skillcoach_credit_ledger.xlsx')">⬇ Excel</button>
        </div>
        <p style="font-size:12px;color:var(--ink-soft);margin:8px 0 0;">
          Every credit movement is recorded permanently. Click a column heading to sort.</p>
        <div id="rTable"></div>
      </div>`;
    Reports.state.rows = await API.get("/api/reports/credits");
    Reports.drawCredits();
  },

  drawCredits() {
    el("rTable").innerHTML = `
      <table style="margin-top:14px;"><thead><tr>
        ${Reports.th("Credit Id", "id")}${Reports.th("From", "from")}${Reports.th("To", "to")}
        ${Reports.th("Tokens", "tokens")}${Reports.th("Note", "note")}${Reports.th("When", "at")}
      </tr></thead><tbody>
        ${Reports.pageRows().map(t => `
          <tr>
            <td>${t.id}</td>
            <td>${esc(t.from)} <span style="color:var(--ink-soft);font-size:11px;">${esc(t.from_role)}</span></td>
            <td>${esc(t.to)} <span style="color:var(--ink-soft);font-size:11px;">${esc(t.to_role)}</span></td>
            <td style="font-weight:700; color:${t.tokens >= 0 ? "var(--ok)" : "var(--danger)"};">
              ${t.tokens >= 0 ? "+" : ""}${t.tokens.toLocaleString()}</td>
            <td>${esc(t.note)}</td>
            <td style="font-size:12px;">${fmtDateTime(t.at)}</td>
          </tr>`).join("") || `<tr><td colspan="6">No credit transactions yet.</td></tr>`}
      </tbody></table>${Reports.pagerHTML()}`;
  },

  /* ---------- Usage ---------- */

  async usage() {
    const now = new Date().toISOString().slice(0, 7);
    el("rBody").innerHTML = `
      <div class="card">
        <h2>Token usage</h2>
        <div style="display:flex; gap:12px; align-items:end; flex-wrap:wrap;">
          <div><label>Month</label><input id="ruMonth" type="month" value="${now}"></div>
          <button class="btn" id="ruGo">Show</button>
          <button class="btn ghost" id="ruXlsx">⬇ Excel</button>
        </div>
        <div id="rTable"></div>
      </div>`;
    const load = async () => {
      const r = await API.get("/api/reports/usage?month=" + el("ruMonth").value);
      Reports.state.rows = r.rows;
      Reports.state.page = 1;
      Reports.drawUsage();
    };
    el("ruGo").onclick = load;
    el("ruXlsx").onclick = () =>
      downloadFile("/api/reports/export/usage?month=" + el("ruMonth").value,
                   "skillcoach_usage.xlsx");
    await load();
  },

  drawUsage() {
    el("rTable").innerHTML = `
      <table style="margin-top:14px;"><thead><tr>
        ${Reports.th("User", "user")}${Reports.th("Role", "role")}
        ${Reports.th("Tokens used", "tokens_used")}${Reports.th("Current balance", "balance")}
      </tr></thead><tbody>
        ${Reports.pageRows().map(u => `
          <tr><td><b>${esc(u.user)}</b></td><td>${u.role.replace("_", " ")}</td>
          <td>${u.tokens_used.toLocaleString()}</td>
          <td>${u.balance.toLocaleString()}</td></tr>`).join("")
          || `<tr><td colspan="4">No usage recorded for this month.</td></tr>`}
      </tbody></table>${Reports.pagerHTML()}`;
  },
};
