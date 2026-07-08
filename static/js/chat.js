/* chat.js — shared chat panel. Requires api.js. */

const Chat = {
  convId: null,

  async init() {
    const [skills, models] = await Promise.all([
      API.get("/api/chat/skills"), API.get("/api/chat/models")]);
    el("skillSelect").innerHTML = skills.length
      ? skills.map(s => `<option value="${s.id}">${esc(s.title)}</option>`).join("")
      : `<option value="">No skills available yet</option>`;
    el("modelSelect").innerHTML = models.map(m =>
      `<option value="${esc(m.model_id)}" ${m.is_default ? "selected" : ""}>${esc(m.display_name)}</option>`).join("");
    el("chatSend").onclick = () => Chat.send();
    el("chatText").addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); Chat.send(); }
    });
    el("newConvBtn").onclick = () => Chat.newConversation();
    await Chat.loadConversations();
    await Chat.loadUsage();
  },

  async loadUsage() {
    try {
      const u = await API.get("/api/chat/usage");
      el("usageInfo").innerHTML = u.unlimited
        ? "Platform account · unlimited credits"
        : `Credit balance: <b>${u.token_balance.toLocaleString()}</b> tokens
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

  async newConversation() {
    const skillId = parseInt(el("skillSelect").value);
    if (!skillId) { flash("chatNotice", "No skill selected"); return; }
    el("newConvBtn").disabled = true;
    el("chatMsgs").innerHTML = `<div class="msg thinking">Starting…</div>`;
    try {
      const c = await API.post("/api/chat/conversations",
        { skill_id: skillId, model_id: el("modelSelect").value });
      Chat.convId = c.id;
      el("chatMsgs").innerHTML = `<div class="msg assistant">${esc(c.greeting)}</div>`;
      await Chat.loadConversations();
      await Chat.loadUsage();
      el("chatText").focus();
    } catch (e) {
      el("chatMsgs").innerHTML = "";
      flash("chatNotice", e.message);
    } finally { el("newConvBtn").disabled = false; }
  },

  async open(id) {
    Chat.convId = id;
    const msgs = await API.get(`/api/chat/conversations/${id}/messages`);
    el("chatMsgs").innerHTML = msgs
      .filter((m, i) => !(i === 0 && m.role === "user" && m.content === "start"))
      .map(m => `<div class="msg ${m.role}">${esc(m.content)}</div>`).join("");
    Chat.scroll();
    await Chat.loadConversations();
  },

  async send() {
    const text = el("chatText").value.trim();
    if (!text) return;
    if (!Chat.convId) { flash("chatNotice", "Start a new conversation first."); return; }

    el("chatText").value = "";
    el("chatMsgs").insertAdjacentHTML("beforeend", `<div class="msg user">${esc(text)}</div>`);
    el("chatMsgs").insertAdjacentHTML("beforeend", `<div class="msg thinking" id="thinking">Thinking…</div>`);
    el("chatSend").disabled = true;
    Chat.scroll();

    try {
      const r = await API.post(`/api/chat/conversations/${Chat.convId}/messages`, { content: text });
      el("thinking").outerHTML = `<div class="msg assistant">${esc(r.reply)}</div>`;
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
    <div class="chat-msgs" id="chatMsgs"></div>
    <div class="chat-input">
      <textarea id="chatText" placeholder="Type your message… (Enter to send, Shift+Enter for a new line)"></textarea>
      <button class="btn" id="chatSend">Send</button>
    </div>
  </div>`;

const CONV_SIDEBAR_HTML = `
  <div class="card">
    <h2>Conversations</h2>
    <div class="conv-list" id="convList"></div>
  </div>`;
