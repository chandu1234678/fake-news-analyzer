// API is defined in config.js (loaded before this script)
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
  await loadStats();
});

async function loadStats() {
  const list = document.getElementById("recent-list");
  list.innerHTML = `<div style="font-size:12px;color:var(--t3);text-align:center;padding:16px 0">Loading…</div>`;

  try {
    const res = await fetch(`${API}/history/sessions`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.status === 401) { navLogin(); return; }
    if (!res.ok) throw new Error(`${res.status}`);

    const sessions = await res.json();
    document.getElementById("stat-total").textContent = sessions.length || 0;

    // Recent list
    const recent = sessions.slice(0, 5);
    if (!recent.length) {
      list.innerHTML = `<div style="font-size:12px;color:var(--t3)">No chats yet. <span id="start-chat" style="color:var(--accent);cursor:pointer">Start one →</span></div>`;
      document.getElementById("start-chat").addEventListener("click", () => nav("popup.html"));
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

    // Count real/fake — batch fetch only last 5 sessions to avoid N+1 spam
    let real = 0, fake = 0;
    await Promise.allSettled(sessions.slice(0, 5).map(async s => {
      const mr = await fetch(`${API}/history/sessions/${s.id}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!mr.ok) return;
      const msgs = await mr.json();
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
    document.getElementById("refresh-link").addEventListener("click", loadStats);
    document.getElementById("stat-total").textContent = "—";
    document.getElementById("stat-real").textContent = "—";
    document.getElementById("stat-fake").textContent = "—";
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
