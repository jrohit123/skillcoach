// CSV upload + token rates handlers for headcoach.html

async function openBulkCoachModal() {
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-bg open" id="bcModal" onclick="if(event.target===this) this.remove()">
      <div class="card modal" style="max-width:620px;">
        <h2>Bulk upload coaches</h2>
        <p style="font-size:12px;color:var(--ink-soft);margin-bottom:12px;">
          CSV format: <code>name,email,password,opening_credits,validity_days</code>
          <br>Example: <code>Coach A,coacha@example.com,SecurePass123,50000,365</code>
          <br>Lines starting with # are skipped.</p>
        <div class="notice" id="bcNotice"></div>
        <textarea id="bcText" style="min-height:140px; font-size:11px; font-family:monospace;">
# name,email,password,opening_credits,validity_days
Coach A,coacha@example.com,SecurePass123,50000,365
Coach B,coachb@example.com,SecurePass456,75000,365
</textarea>
        <div style="display:flex; gap:10px; margin-top:14px;">
          <button class="btn" id="bcSubmit">Upload</button>
          <button class="btn ghost" onclick="el('bcModal').remove()">Cancel</button>
        </div>
      </div>
    </div>`);
  el("bcSubmit").onclick = async () => {
    try {
      const r = await API.post("/api/admin/bulk-coaches", { csv_text: el("bcText").value });
      if (r.ok) {
        flash("bcNotice", `Success: ${r.message}`, true);
        setTimeout(() => { el("bcModal").remove(); loadCoaches(); }, 1200);
      } else {
        let msg = r.message + "\n\nErrors:\n";
        r.results.errors.slice(0, 5).forEach(e => msg += `  Row ${e.row}: ${e.error}\n`);
        flash("bcNotice", msg);
      }
    } catch (e) { flash("bcNotice", e.message); }
  };
}

async function openBulkSkillModal() {
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-bg open" id="bsModal" onclick="if(event.target===this) this.remove()">
      <div class="card modal" style="max-width:620px;">
        <h2>Bulk upload skills</h2>
        <p style="font-size:12px;color:var(--ink-soft);margin-bottom:12px;">
          CSV format: <code>title,description,category,"system_prompt"</code>
          <br>Use quotes for multiline prompts. Lines starting with # are skipped.</p>
        <div class="notice" id="bsNotice"></div>
        <textarea id="bsText" style="min-height:160px; font-size:11px; font-family:monospace;">
# title,description,category,"system_prompt"
"Active Listening","Coach clients to listen deeply","Culture","You are a coaching expert..."
"Goal Setting","Help clients set SMART goals","Strategy","Guide the client through..."
</textarea>
        <div style="display:flex; gap:10px; margin-top:14px;">
          <button class="btn" id="bsSubmit">Upload</button>
          <button class="btn ghost" onclick="el('bsModal').remove()">Cancel</button>
        </div>
      </div>
    </div>`);
  el("bsSubmit").onclick = async () => {
    try {
      const r = await API.post("/api/admin/bulk-skills", { csv_text: el("bsText").value });
      if (r.ok) {
        flash("bsNotice", `Success: ${r.message}`, true);
        setTimeout(() => { el("bsModal").remove(); loadSkills(); }, 1200);
      } else {
        let msg = r.message + "\n\nErrors:\n";
        r.results.errors.slice(0, 5).forEach(e => msg += `  Row ${e.row}: ${e.error}\n`);
        flash("bsNotice", msg);
      }
    } catch (e) { flash("bsNotice", e.message); }
  };
}

async function openTokenRatesModal() {
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-bg open" id="rtModal" onclick="if(event.target===this) this.remove()">
      <div class="card modal" style="max-width:620px;">
        <h2>Manage Claude API token rates</h2>
        <p style="font-size:12px;color:var(--ink-soft);margin-bottom:12px;">
          Rates in USD per million tokens. Clients see these for cost transparency.
          Update if Anthropic's pricing changes.</p>
        <div class="notice" id="rtNotice"></div>
        <table style="width:100%; margin-bottom:14px;">
          <thead><tr><th>Model</th><th>Input ($/1M)</th><th>Output ($/1M)</th><th></th></tr></thead>
          <tbody id="rtRows"></tbody>
        </table>
        <button class="btn ghost" onclick="el('rtModal').remove()">Close</button>
      </div>
    </div>`);
  await loadTokenRateRows();
}

async function loadTokenRateRows() {
  const rows = await API.get("/api/admin/token-rates");
  el("rtRows").innerHTML = rows.map(r => `
    <tr>
      <td style="font-weight:700;">${esc(r.model_id)}</td>
      <td><input type="number" step="0.0001" value="${r.input}" id="in_${r.id}" style="width:90px;"></td>
      <td><input type="number" step="0.0001" value="${r.output}" id="out_${r.id}" style="width:90px;"></td>
      <td><button class="btn small" onclick="saveTokenRate(${r.id}, '${esc(r.model_id)}')">Save</button></td>
    </tr>`).join("");
}

async function saveTokenRate(id, model) {
  try {
    const inp = parseFloat(el(`in_${id}`).value);
    const out = parseFloat(el(`out_${id}`).value);
    if (inp < 0 || out < 0) throw new Error("Rates cannot be negative");
    await API.patch(`/api/admin/token-rates/${id}`,
      { model_id: model, input_rate_per_1m: inp, output_rate_per_1m: out });
    flash("rtNotice", "Rate updated.", true);
    setTimeout(() => loadTokenRateRows(), 1200);
  } catch (e) { flash("rtNotice", e.message); }
}
