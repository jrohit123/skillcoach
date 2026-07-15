/* chat.js — shared chat panel: markdown rendering, categories, edit-message.
   Requires api.js; marked + DOMPurify loaded via CDN in the page. */

function renderMD(text) {
  if (window.marked && window.DOMPurify)
    return DOMPurify.sanitize(marked.parse(text ?? ""));
  return esc(text);  // fallback if CDN blocked
}

const Chat = {
  convId: null,
  skills: [],
  catOrder: [],
  category: "All",
  msgCache: [],   // visible messages of the open conversation

  async init() {
    const [skills, models, catOrder] = await Promise.all([
      API.get("/api/chat/skills"), API.get("/api/chat/models"),
      API.get("/api/chat/skill-categories").catch(() => [])]);
    Chat.skills = skills;
    Chat.catOrder = catOrder;
    el("modelSelect").innerHTML = models.map(m =>
      `<option value="${esc(m.model_id)}" ${m.is_default ? "selected" : ""}>${esc(m.display_name)}</option>`).join("");
    Chat.renderCategories();
    const firstCat = Chat.categoryList()[0] || "All";
    Chat.applyCategory(firstCat);
    el("chatSend").onclick = () => Chat.send();
    el("chatText").addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); Chat.send(); }
    });
    el("newConvBtn").onclick = () => Chat.newConversation();
    await Chat.loadConversations();
    await Chat.loadUsage();
  },

  /* ---------- categories ---------- */

  categoryList() {
    const present = new Set(Chat.skills.map(s => s.category).filter(c => c));
    const ordered = Chat.catOrder.filter(c => present.has(c));        // server order
    const extras = [...present].filter(c => !Chat.catOrder.includes(c)).sort();
    return [ ...ordered, ...extras, "All"];  // uncategorized skills appear under "All"
  },

  renderCategories() {
    const box = el("catList");
    if (!box) return;
    box.innerHTML = Chat.categoryList().map(c =>
      `<button data-cat="${esc(c)}" class="${c === Chat.category ? "active" : ""}">${esc(c)}</button>`).join("");
    box.querySelectorAll("button").forEach(b =>
      b.onclick = () => Chat.applyCategory(b.dataset.cat));
  },

  applyCategory(cat) {
    Chat.category = cat;
    const list = Chat.skills.filter(s =>
      cat === "All" ? true : s.category === cat);
    el("skillSelect").innerHTML = list.length
      ? list.map(s => `<option value="${s.id}">${esc(s.title)}</option>`).join("")
      : `<option value="">No skills in this category</option>`;
    Chat.renderCategories();
  },

  /* ---------- usage / conversations ---------- */

  async loadUsage() {
    try {
      const u = await API.get("/api/chat/usage");
      const usd = (u.estimated_usd != null)
        ? ` <span title="Approximate value — assumes the costliest active AI model, since actual cost depends on which model you pick per chat.">(≈ $${u.estimated_usd.toFixed(2)} USD)</span>`
        : "";
      el("usageInfo").innerHTML = u.unlimited
        ? "Platform account · unlimited credits"
        : `Credit balance: <b>${u.token_balance.toLocaleString()}</b> tokens${usd}
           · used this month: ${u.tokens_used_this_month.toLocaleString()}`;
    } catch (e) { /* non-fatal */ }
  },

  async loadConversations() {
    const convs = await API.get("/api/chat/conversations");
    el("convList").innerHTML = convs.map(c => `
      <div style="display:flex; align-items:center; gap:4px;">
        <button data-id="${c.id}" class="${c.id === Chat.convId ? "active" : ""}"
          style="flex:1;" title="${esc(c.skill)}">${esc(c.title)}</button>
        <button class="rename" data-id="${c.id}" data-title="${esc(c.title)}"
          title="Rename" style="border:none;background:none;cursor:pointer;font-size:13px;">✏️</button>
      </div>`).join("") ||
      `<span style="font-size:12px;color:var(--ink-soft)">No conversations yet — start one above.</span>`;
    el("convList").querySelectorAll("button[data-id]:not(.rename)").forEach(b =>
      b.onclick = () => Chat.open(parseInt(b.dataset.id)));
    el("convList").querySelectorAll("button.rename").forEach(b =>
      b.onclick = async (e) => {
        e.stopPropagation();
        const t = prompt("Rename conversation:", b.dataset.title);
        if (t && t.trim()) {
          await API.patch(`/api/chat/conversations/${b.dataset.id}`, { title: t.trim() });
          Chat.loadConversations();
        }
      });
  },

  /* ---------- rendering ---------- */

  msgHTML(m, idx) {
    if (m.role === "assistant")
      return `<div class="msg assistant md">${renderMD(m.content)}</div>`;
    const editable = !(idx === 0 && m.content === "start");
    return `<div class="msg user" data-mid="${m.id}">
      <span style="white-space:pre-wrap;">${esc(m.content)}</span>
      ${editable ? `<button class="edit-btn" title="Edit message"
        onclick="Chat.startEdit(${m.id})">✏️</button>` : ""}</div>`;
  },

  drawMessages() {
    el("chatMsgs").innerHTML = Chat.msgCache
      .filter((m, i) => !(i === 0 && m.role === "user" && m.content === "start"))
      .map((m) => Chat.msgHTML(m, Chat.msgCache.indexOf(m))).join("");
    Chat.scroll();
  },

  async open(id) {
    Chat.convId = id;
    Chat.msgCache = await API.get(`/api/chat/conversations/${id}/messages`);
    Chat.drawMessages();
    // update download link
    const dlBtn = el("dlBtn");
    if (dlBtn) { dlBtn.onclick = () =>
      downloadFile(`/api/reports/conversations/${id}/download`,
                   `conversation_${id}.html`); }
    await Chat.loadConversations();
    if (el("dlBtn")) el("dlBtn").style.display = "inline-block";
  },

  /* ---------- new conversation / send ---------- */

  async newConversation() {
    const skillId = parseInt(el("skillSelect").value);
    if (!skillId) { flash("chatNotice", "No skill selected"); return; }
    el("newConvBtn").disabled = true;
    el("chatMsgs").innerHTML = `<div class="msg thinking">Starting…</div>`;
    try {
      const c = await API.post("/api/chat/conversations",
        { skill_id: skillId, model_id: el("modelSelect").value });
      Chat.convId = c.id;
      await Chat.open(c.id);
      if (el("dlBtn")) el("dlBtn").style.display = "inline-block";
      await Chat.loadUsage();
      el("chatText").focus();
    } catch (e) {
      el("chatMsgs").innerHTML = "";
      flash("chatNotice", e.message);
    } finally { el("newConvBtn").disabled = false; }
  },

  async send() {
    const text = el("chatText").value.trim();
    if (!text) return;
    if (!Chat.convId) { flash("chatNotice", "Start a new conversation first."); return; }

    el("chatText").value = "";
    el("chatMsgs").insertAdjacentHTML("beforeend",
      `<div class="msg user"><span style="white-space:pre-wrap;">${esc(text)}</span></div>`);
    el("chatMsgs").insertAdjacentHTML("beforeend", `<div class="msg thinking" id="thinking">Thinking…</div>`);
    el("chatSend").disabled = true;
    Chat.scroll();

    try {
      const r = await API.post(`/api/chat/conversations/${Chat.convId}/messages`, { content: text });
      el("thinking").remove();
      Chat.msgCache = await API.get(`/api/chat/conversations/${Chat.convId}/messages`);
      Chat.drawMessages();
      await Chat.loadConversations();
      await Chat.loadUsage();
    } catch (e) {
      el("thinking").remove();
      flash("chatNotice", e.message);
    } finally {
      el("chatSend").disabled = false;
      Chat.scroll();
    }
  },

  /* ---------- edit a message (fork) ---------- */

  startEdit(mid) {
    const m = Chat.msgCache.find(x => x.id === mid);
    if (!m) return;
    const bubble = el("chatMsgs").querySelector(`[data-mid="${mid}"]`);
    if (!bubble) return;
    bubble.outerHTML = `
      <div class="msg user editing" data-mid="${mid}" style="width:78%;">
        <textarea id="editText" style="min-height:70px;">${esc(m.content)}</textarea>
        <div style="display:flex; gap:8px; margin-top:8px; justify-content:flex-end;">
          <button class="btn small ghost" style="border-color:#fff;color:#fff;"
            onclick="Chat.drawMessages()">Cancel</button>
          <button class="btn small" style="background:#fff;color:var(--indigo);"
            onclick="Chat.saveEdit(${mid})">Save & resend</button>
        </div>
        <p style="font-size:11px; opacity:.8; margin-top:6px;">
          Saving discards everything after this message and re-asks from here.</p>
      </div>`;
    el("editText").focus();
  },

  async saveEdit(mid) {
    const text = el("editText").value.trim();
    if (!text) { flash("chatNotice", "Message cannot be empty"); return; }
    el("chatMsgs").insertAdjacentHTML("beforeend", `<div class="msg thinking" id="thinking">Thinking…</div>`);
    try {
      await API.patch(`/api/chat/conversations/${Chat.convId}/messages/${mid}`, { content: text });
      Chat.msgCache = await API.get(`/api/chat/conversations/${Chat.convId}/messages`);
      Chat.drawMessages();
      await Chat.loadUsage();
    } catch (e) {
      el("thinking") && el("thinking").remove();
      flash("chatNotice", e.message);
      Chat.drawMessages();
    }
  },

  scroll() { const m = el("chatMsgs"); m.scrollTop = m.scrollHeight; },
};

const CHAT_PANEL_HTML = `
  <div class="card">
    <div style="display:flex; gap:10px; align-items:end; flex-wrap:wrap;">
      <div style="flex:2; min-width:180px;">
        <label>Skill</label>
        <select id="skillSelect"></select>
      </div>
      <div style="flex:1; min-width:160px;">
        <label>Model</label>
        <select id="modelSelect"></select>
      </div>
      <button class="btn" id="newConvBtn">New conversation</button>
    </div>
    <div style="font-size:12px;color:var(--ink-soft);margin-top:10px;" id="usageInfo"></div>
  </div>
  <div class="card chat-box">
    <div class="notice" id="chatNotice"></div>
    <div style="display:flex; justify-content:flex-end; margin-bottom:6px; min-height:24px;">
      <button class="btn ghost small" id="dlBtn" style="display:none;">⬇ Download HTML</button>
    </div>
    <div class="chat-msgs" id="chatMsgs"></div>
    <div class="chat-input">
      <textarea id="chatText" placeholder="Type your message… (Enter to send, Shift+Enter for a new line)"></textarea>
      <button class="btn" id="chatSend">Send</button>
    </div>
  </div>`;

const CONV_SIDEBAR_HTML = `
  <div class="card">
    <h2>Categories</h2>
    <div class="cat-list" id="catList"></div>
  </div>
  <div class="card">
    <h2>Conversations</h2>
    <div class="conv-list" id="convList"></div>
  </div>`;
