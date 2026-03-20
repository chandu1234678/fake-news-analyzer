// API is defined in config.js (loaded before this script)
let token = null;

function nav(page) { window.location.href = chrome.runtime.getURL(`popup/${page}`); }
function navLogin() { chrome.storage.local.clear(() => nav("login.html")); }

chrome.storage.local.get(["token", "user"], async d => {
  if (!d.token) { nav("login.html"); return; }
  token = d.token;
  if (d.user) {
    document.getElementById("user-name").textContent = d.user.name || d.user.email;
    const av = document.getElementById("user-avatar");
    if (d.user.picture) {
      av.innerHTML = `<img src="${d.user.picture}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
    } else {
      av.textContent = (d.user.name || d.user.email || "?").charAt(0).toUpperCase();
    }
  }
  await loadStats();
});

function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

async function loadStats() {
  try {
    const res = await fetch(`${API}/history/sessions`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) {
      if (res.status === 401) { navLogin(); return; }
      throw new Error(`${res.status}`);
    }
    const sessions = await res.json();
    document.getElementById("stat-total").textContent = sessions.length;

    const list = document.getElementById("recent-list");
    const recent = sessions.slice(0, 5);
    if (!recent.length) {
      list.innerHTML = `<div style="font-size:12px;color:var(--t3)">No chats yet. <span id="start-chat" style="color:var(--accent);cursor:pointer">Start one</span></div>`;
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
        a.addEventListener("click", () => {
          chrome.storage.local.set({ currentSessionId: s.id }, () => nav("popup.html"));
        });
        list.appendChild(a);
      });
    }

    // Count real/fake from recent sessions
    let real = 0, fake = 0;
    for (const s of sessions.slice(0, 10)) {
      try {
        const mr = await fetch(`${API}/history/sessions/${s.id}/messages`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (!mr.ok) continue;
        const msgs = await mr.json();
        msgs.forEach(m => {
          if (m.is_claim) {
            if (m.verdict === "real") real++;
            else if (m.verdict === "fake") fake++;
          }
        });
      } catch(e) {}
    }
    document.getElementById("stat-real").textContent = real;
    document.getElementById("stat-fake").textContent = fake;
  } catch(e) {
    document.getElementById("user-name").textContent = "Could not load — backend waking up";
    document.getElementById("recent-list").innerHTML = `
      <div style="font-size:12px;color:var(--t3)">
        Backend may be starting up.
        <span id="refresh-link" style="color:var(--accent);cursor:pointer">Refresh</span>
      </div>`;
    document.getElementById("refresh-link").addEventListener("click", () => nav("dashboard.html"));
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
