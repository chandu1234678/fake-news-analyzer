// API is defined in config.js
let token = null;

function nav(page) { window.location.href = chrome.runtime.getURL(`popup/${page}`); }
function navLogin() { chrome.storage.local.clear(() => nav("login.html")); }
const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

chrome.storage.local.get(["token", "user"], async d => {
  if (!d.token) { nav("login.html"); return; }
  token = d.token;
  if (d.user) {
    document.getElementById("user-name").textContent = d.user.name || d.user.email || "User";
    const av = document.getElementById("user-avatar");
    if (d.user.picture) {
      av.innerHTML = `<img src="${d.user.picture}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
    } else {
      av.textContent = (d.user.name || d.user.email || "?").charAt(0).toUpperCase();
    }
  }
  await Promise.allSettled([loadSessions(), loadSystemStats()]);
});

// ── Session stats ─────────────────────────────────────────────
async function loadSessions() {
  const list = document.getElementById("recent-list");
  try {
    const res = await apiFetch("/history/sessions", {
      headers: buildHeaders({ Authorization: `Bearer ${token}` })
    });
    if (res.status === 401) { navLogin(); return; }
    if (!res.ok) throw new Error(`${res.status}`);

    const payload = await readJsonSafe(res) || {};
    const sessions = Array.isArray(payload) ? payload : (payload.sessions || []);
    document.getElementById("stat-total").textContent = sessions.length || 0;

    const recent = sessions.slice(0, 5);
    if (!recent.length) {
      list.innerHTML = `<div style="font-size:12px;color:var(--t3)">No chats yet. <span id="start-chat" style="color:var(--accent);cursor:pointer">Start one →</span></div>`;
      document.getElementById("start-chat")?.addEventListener("click", () => nav("popup.html"));
    } else {
      list.innerHTML = "";
      recent.forEach(s => {
        const a = document.createElement("div");
        a.className = "list-item";
        a.style.cssText = "display:flex;align-items:center;gap:10px;cursor:pointer";
        a.innerHTML = `
          <span class="material-symbols-outlined ms-16" style="color:var(--t3);flex-shrink:0">chat_bubble</span>
          <span class="list-item-title" style="flex:1">${esc(s.title)}</span>
          <span style="font-size:11px;color:var(--t3);flex-shrink:0">${timeAgo(s.updated_at)}</span>`;
        a.addEventListener("click", () => chrome.storage.local.set({ currentSessionId: s.id }, () => nav("popup.html")));
        list.appendChild(a);
      });
    }

    // Count real/fake from last 5 sessions
    let real = 0, fake = 0;
    await Promise.allSettled(sessions.slice(0, 5).map(async s => {
      const mr = await apiFetch(`/history/sessions/${s.id}/messages`, {
        headers: buildHeaders({ Authorization: `Bearer ${token}` })
      });
      if (!mr.ok) return;
      const msgs = await readJsonSafe(mr) || [];
      msgs.forEach(m => {
        if (m.is_claim) {
          if (m.verdict === "real") real++;
          else if (m.verdict === "fake") fake++;
        }
      });
    }));
    document.getElementById("stat-real").textContent = real;
    document.getElementById("stat-fake").textContent = fake;

  } catch(e) {
    list.innerHTML = `
      <div style="text-align:center;padding:16px 0">
        <div style="font-size:12px;color:var(--t3);margin-bottom:8px">Could not load — backend may be starting up</div>
        <button id="refresh-link" style="padding:6px 14px;border-radius:8px;border:1px solid var(--a-bdr);background:var(--a-dim);color:var(--accent);font-size:12px;font-family:Inter,sans-serif;cursor:pointer">Retry</button>
      </div>`;
    document.getElementById("refresh-link")?.addEventListener("click", loadSessions);
    document.getElementById("stat-total").textContent = "—";
    document.getElementById("stat-real").textContent = "—";
    document.getElementById("stat-fake").textContent = "—";
  }
}

// ── System stats (model + drift + credibility) ────────────────
async function loadSystemStats() {
  try {
    const res = await apiFetch("/stats/system", {
      headers: buildHeaders({ Authorization: `Bearer ${token}` })
    });
    if (!res.ok) return;
    const data = await readJsonSafe(res) || {};

    // Model info
    const mv = data.model || {};
    document.getElementById("model-version").textContent = mv.version || "unknown";
    document.getElementById("model-acc").textContent   = mv.accuracy   ? `${(mv.accuracy * 100).toFixed(1)}%` : "—";
    document.getElementById("model-f1").textContent    = mv.f1_macro   ? mv.f1_macro.toFixed(3) : "—";
    document.getElementById("model-brier").textContent = mv.brier_score ? mv.brier_score.toFixed(3) : "—";

    // Adversarial robustness (if available)
    if (mv.robustness_score != null) {
      const robEl = document.getElementById("model-robustness");
      if (robEl) {
        robEl.textContent = mv.robustness_score.toFixed(3);
        robEl.style.color = mv.robustness_score >= 0.80 ? "var(--real)"
                          : mv.robustness_score >= 0.60 ? "var(--warn)" : "var(--fake)";
      }
    }

    // Drift
    const drift = data.drift || {};
    const driftBody = document.getElementById("drift-body");
    if (drift.n > 0) {
      const alertHtml = drift.drift_alert
        ? `<span style="color:var(--fake);font-weight:600">⚠️ Drift detected</span>`
        : `<span style="color:var(--real)">✓ Stable</span>`;
      driftBody.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span style="font-size:11px;color:var(--t3)">Status</span>
          ${alertHtml}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;text-align:center">
          <div>
            <div style="font-size:13px;font-weight:600;color:var(--fake)">${(drift.fake_rate * 100).toFixed(0)}%</div>
            <div style="font-size:9px;color:var(--t3)">Fake rate</div>
          </div>
          <div>
            <div style="font-size:13px;font-weight:600;color:var(--warn)">${(drift.uncertain_rate * 100).toFixed(0)}%</div>
            <div style="font-size:9px;color:var(--t3)">Uncertain</div>
          </div>
          <div>
            <div style="font-size:13px;font-weight:600;color:var(--accent)">${drift.n}</div>
            <div style="font-size:9px;color:var(--t3)">Predictions</div>
          </div>
        </div>`;
    } else {
      driftBody.textContent = "No predictions yet in this session.";
    }

    // Top sources
    const srcList = document.getElementById("sources-list");
    const sources = data.top_sources || [];
    if (sources.length) {
      srcList.innerHTML = sources.map(s => {
        const pct = Math.round(s.score * 100);
        const cls = s.score >= 0.85 ? "cred-high" : s.score >= 0.65 ? "cred-med" : "cred-low";
        const bar = `<div style="flex:1;height:4px;background:var(--bg3);border-radius:2px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:var(--real);border-radius:2px"></div>
        </div>`;
        return `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--border)">
          <span style="font-size:11px;color:var(--t2);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s.domain)}</span>
          ${bar}
          <span class="src-cred ${cls}" style="flex-shrink:0">${pct}%</span>
        </div>`;
      }).join("");
    } else {
      srcList.textContent = "No source data yet.";
    }

  } catch(e) {
    document.getElementById("drift-body").textContent = "Unavailable";
    document.getElementById("sources-list").textContent = "Unavailable";
  }
}

// ── Navigation ────────────────────────────────────────────────
document.getElementById("back-btn").addEventListener("click",    () => nav("popup.html"));
document.getElementById("bn-chat").addEventListener("click",      () => nav("popup.html"));
document.getElementById("bn-dashboard").addEventListener("click", () => nav("dashboard.html"));
document.getElementById("bn-saved").addEventListener("click",     () => nav("saved.html"));
document.getElementById("bn-history").addEventListener("click",   () => nav("history.html"));
document.getElementById("bn-settings").addEventListener("click",  () => nav("settings.html"));
document.getElementById("qa-chat").addEventListener("click",      () => nav("popup.html"));
document.getElementById("qa-saved").addEventListener("click",     () => nav("saved.html"));
document.getElementById("qa-history").addEventListener("click",   () => nav("history.html"));
document.getElementById("qa-settings").addEventListener("click",  () => nav("settings.html"));
