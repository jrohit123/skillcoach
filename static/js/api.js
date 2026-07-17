/* api.js — shared helpers for all pages */

const API = {
  token: () => localStorage.getItem("token"),

  async req(method, path, body) {
    document.body.classList.add("busy");
    try {
    const res = await fetch(path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(API.token() ? { Authorization: "Bearer " + API.token() } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 401) { logout(); return; }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      let msg = data.detail || ("Error " + res.status);
      if (Array.isArray(msg)) {
        // FastAPI validation errors: [{loc:[...], msg:"...", type:"..."}]
        msg = msg.map(e => `${(e.loc || []).slice(-1)[0]}: ${e.msg}`).join("; ");
      }
      throw new Error(msg);
    }
    return data;
    } finally { document.body.classList.remove("busy"); }
  },
  get: (p) => API.req("GET", p),
  post: (p, b) => API.req("POST", p, b),
  patch: (p, b) => API.req("PATCH", p, b),
  del: (p) => API.req("DELETE", p),
};

function logout() {
  localStorage.clear();
  window.location.href = "/static/login.html";
}

function requireRole(role) {
  if (!API.token()) { logout(); return; }
  if (localStorage.getItem("role") !== role) logout();
}

function el(id) { return document.getElementById(id); }

function flash(id, msg, ok = false) {
  const n = el(id);
  n.textContent = msg;
  n.className = "notice " + (ok ? "ok" : "err");
  setTimeout(() => { n.className = "notice"; }, 5000);
}

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const TZ_LIST = ["Asia/Kolkata","Asia/Dubai","Asia/Singapore","Asia/Tokyo","Australia/Sydney",
  "Europe/London","Europe/Paris","Europe/Berlin","America/New_York","America/Chicago",
  "America/Denver","America/Los_Angeles","UTC"];

function userTZ() { return localStorage.getItem("timezone") || "Asia/Kolkata"; }

/* Server datetimes are UTC ("YYYY-MM-DD HH:MM:SS..."); dates are plain YYYY-MM-DD. */
function fmtDate(s) {
  if (!s) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {           // plain date, no TZ shift
    const [y, m, d] = s.split("-");
    return `${d}-${MONTHS[parseInt(m) - 1]}-${y.slice(2)}`;
  }
  return fmtDateTime(s).slice(0, 9);
}

function fmtDateTime(s) {
  if (!s) return "";
  const dt = new Date(s.replace(" ", "T").split(".")[0] + "Z");
  if (isNaN(dt)) return s;
  const p = new Intl.DateTimeFormat("en-GB",
    { timeZone: userTZ(), day: "2-digit", month: "short", year: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(dt).reduce((a, x) => (a[x.type] = x.value, a), {});
  return `${p.day}-${p.month}-${p.year} ${p.hour}:${p.minute}`;
}

async function downloadFile(path, filename) {
  document.body.classList.add("busy");
  try {
    const res = await fetch(path, { headers: { Authorization: "Bearer " + API.token() } });
    if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || "Download failed"); }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  } finally { document.body.classList.remove("busy"); }
}

/* Reusable "bulk upload via CSV" card.
   templatePath: GET endpoint returning the empty template CSV
   uploadPath:   POST endpoint (multipart) accepting the filled CSV
   onDone:       called after a successful upload (e.g. to reload a table) */
function bulkUploadCardHTML(id, label) {
  return `
    <div class="card">
      <h2>Bulk upload ${esc(label)} (CSV)</h2>
      <div class="notice" id="${id}Notice"></div>
      <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
        <button class="btn ghost small" id="${id}Template">⬇ Download empty template</button>
        <input type="file" id="${id}File" accept=".csv" style="max-width:240px;">
        <button class="btn small" id="${id}Upload">Upload CSV</button>
      </div>
      <div id="${id}Result" style="font-size:12px; margin-top:10px;"></div>
    </div>`;
}

function wireBulkUpload(id, templatePath, uploadPath, templateFilename, onDone) {
  el(`${id}Template`).onclick = () => downloadFile(templatePath, templateFilename);
  el(`${id}Upload`).onclick = async () => {
    const f = el(`${id}File`).files[0];
    if (!f) { flash(`${id}Notice`, "Choose a CSV file first"); return; }
    const form = new FormData();
    form.append("file", f);
    document.body.classList.add("busy");
    try {
      const res = await fetch(uploadPath, { method: "POST",
        headers: { Authorization: "Bearer " + API.token() }, body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      flash(`${id}Notice`, `${data.created} row(s) created.`, true);
      el(`${id}Result`).innerHTML = data.errors.length
        ? `<b style="color:var(--danger);">${data.errors.length} row(s) skipped:</b><br>` +
          data.errors.map(e => esc(e)).join("<br>")
        : "";
      el(`${id}File`).value = "";
      if (onDone) onDone();
    } catch (e) { flash(`${id}Notice`, e.message); }
    finally { document.body.classList.remove("busy"); }
  };
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

/* Shared topbar + footer injection (coach/client see coach branding) */
async function renderChrome() {
  const name = localStorage.getItem("name") || "";
  const role = (localStorage.getItem("role") || "").replace("_", " ");
  document.body.insertAdjacentHTML("afterbegin", `
    <div class="topbar">
      <div class="brand" id="brandArea">
        <span class="app">SkillCoach</span>
        <span class="org">Phenom Business Coaching Systems</span>
      </div>
      <div class="who"><b>${esc(name)}</b> · ${esc(role)} &nbsp;
        <select id="tzSelect" style="width:auto; font-size:11px; padding:4px 6px;"
          title="Your timezone (affects how dates are shown)">
          ${TZ_LIST.map(z => `<option value="${z}" ${z === userTZ() ? "selected" : ""}>${z}</option>`).join("")}
        </select>
        <button class="btn ghost small" onclick="openPasswordModal()">Password</button>
        <button class="btn ghost small" onclick="logout()">Log out</button>
      </div>
    </div>`);
  document.body.insertAdjacentHTML("beforeend", `
    <footer>
      A tool by <b>&nbsp;Phenom Business Coaching Systems&nbsp;</b> · Developed by
      <a href="https://www.aitamate.com" target="_blank" rel="noopener">
        <img src="https://aitamate.com/src/Logo-transparent_bg.png" alt="aitamate Solutions">
      </a>
    </footer>`);
  el("tzSelect").onchange = async () => {
    const tz = el("tzSelect").value;
    try { await API.patch("/api/auth/timezone", { timezone: tz }); } catch (e) {}
    localStorage.setItem("timezone", tz);
    location.reload();
  };
  // coach/client: show the coach's branding in the topbar
  const r = localStorage.getItem("role");
  if (r === "coach" || r === "client") {
    try {
      const b = await API.get("/api/chat/branding");
      if (b.brand_name || b.brand_logo) {
        const site = b.brand_website
          ? (b.brand_website.startsWith("http") ? b.brand_website : "https://" + b.brand_website) : "";
        el("brandArea").innerHTML = `
          ${b.brand_logo ? `<img src="${b.brand_logo}" alt="${esc(b.brand_name)}" style="height:34px;">` : ""}
          <span class="app">${esc(b.brand_name) || "SkillCoach"}</span>
          <span class="org">${b.brand_about ? esc(b.brand_about) : ""}
            ${site ? ` · <a href="${esc(site)}" target="_blank" rel="noopener">${esc(b.brand_website)}</a>` : ""}</span>`;
      }
    } catch (e) { /* keep default branding */ }
  }
}

/* Change-password modal (available to every logged-in user) */
function openPasswordModal() {
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-bg open" id="pwModal" onclick="if(event.target===this) this.remove()">
      <div class="card modal" style="max-width:420px;">
        <h2>Change password</h2>
        <div class="notice" id="pwNotice"></div>
        <label>Current password</label>
        <input id="pwOld" type="password" autocomplete="current-password">
        <label>New password (min 8 characters)</label>
        <input id="pwNew" type="password" autocomplete="new-password">
        <label>Confirm new password</label>
        <input id="pwNew2" type="password" autocomplete="new-password">
        <div style="margin-top:16px; display:flex; gap:10px;">
          <button class="btn" onclick="submitPasswordChange()">Change password</button>
          <button class="btn ghost" onclick="el('pwModal').remove()">Cancel</button>
        </div>
      </div>
    </div>`);
}

async function submitPasswordChange() {
  const oldP = el("pwOld").value, p1 = el("pwNew").value, p2 = el("pwNew2").value;
  if (p1.length < 8) { flash("pwNotice", "New password must be at least 8 characters"); return; }
  if (p1 !== p2) { flash("pwNotice", "New passwords do not match"); return; }
  try {
    await API.post("/api/auth/change-password", { old_password: oldP, new_password: p1 });
    flash("pwNotice", "Password changed successfully.", true);
    setTimeout(() => el("pwModal") && el("pwModal").remove(), 1200);
  } catch (e) { flash("pwNotice", e.message); }
}