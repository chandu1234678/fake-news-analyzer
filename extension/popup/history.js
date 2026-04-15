// API is defined in config.js (loaded before this script)
let token = null;
let sessions = [];

function nav(page) { window.location.href = chrome.runtime.getURL(`popup/${page}`); }

chrome.storage.local.get(["token"], async d => {
  if (!d.token) { nav("login.html"); return; }
  token = d.token;
  await load();
});

document.getElementById("clear-btn").addEventListener("click", clearAll);

// ── Navigation ────────────────────────────────────────────────
document.getElementById("back-btn").addEventListener("click",    () => nav("popup.html"));
document.getElementById("bn-chat").addEventListener("click",      () => nav("popup.html"));
document.getElementById("bn-dashboard").addEventListener("click", () => nav("dashboard.html"));
document.getElementById("bn-saved").addEventListener("click",     () => nav("saved.html"));
document.getElementById("bn-history").addEventListener("click",   () => nav("history.html"));
document.getElementById("bn-settings").addEventListener("click",  () => nav("settings.html"));

function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

async function load() {
  const list = document.getElementById("sessions-list");
  list.innerHTML = `<div style="font-size:12px;color:var(--t3);text-align:center;padding:32px 0">Loading...</div>`;
  try {
    const res = await apiFetch("/history/sessions", {
      headers: buildHeaders({ Authorization: `Bearer ${token}` })
    });
    if (!res.ok) {
      if (res.status === 401) { nav("login.html"); return; }
      throw new Error(`Server error ${res.status}`);
    }
    const data = await readJsonSafe(res) || {};
    sessions = Array.isArray(data) ? data : (data.sessions || []);
    render();
  } catch(e) {
    list.innerHTML = `
      <div style="text-align:center;padding:40px 16px">
        <div style="font-size:12px;color:var(--fake);margin-bottom:10px">Could not load history</div>
        <div style="font-size:11px;color:var(--t3);margin-bottom:14px">Backend may be waking up. Try again.</div>
        <button id="retry-btn" style="padding:7px 18px;border-radius:8px;border:1px solid var(--a-bdr);background:var(--a-dim);color:var(--accent);font-size:12px;font-family:Inter,sans-serif;cursor:pointer">Retry</button>
      </div>`;
    document.getElementById("retry-btn").addEventListener("click", load);
  }
}

function render() {
  const list = document.getElementById("sessions-list");
  list.innerHTML = "";
  if (!sessions.length) {
    list.innerHTML = `
      <div style="text-align:center;padding:40px 0">
        <span class="material-symbols-outlined ms-24" style="color:var(--t3)">history</span>
        <div style="font-size:12px;color:var(--t3);margin-top:8px">No chat history yet</div>
        <div style="font-size:12px;color:var(--accent);margin-top:4px;cursor:pointer" id="go-chat">Start a conversation</div>
      </div>`;
    document.getElementById("go-chat").addEventListener("click", () => nav("popup.html"));
    return;
  }
  sessions.forEach(s => {
    const el = document.createElement("div");
    el.className = "list-item";
    el.style.display = "flex";
    el.style.alignItems = "center";
    el.style.gap = "10px";
    el.innerHTML = `
      <span class="material-symbols-outlined ms-16" style="color:var(--accent);flex-shrink:0">chat_bubble</span>
      <div style="flex:1;min-width:0;cursor:pointer" class="s-open">
        <div class="list-item-title">${esc(s.title)}</div>
        <div class="list-item-meta">${new Date(s.updated_at).toLocaleDateString()}</div>
      </div>
      <button class="icon-btn s-del" style="flex-shrink:0">
        <span class="material-symbols-outlined ms-16">delete</span>
      </button>`;
    el.querySelector(".s-open").addEventListener("click", () => openSession(s.id));
    el.querySelector(".s-del").addEventListener("click", () => deleteSession(s.id));
    list.appendChild(el);
  });
}

function openSession(id) {
  chrome.storage.local.set({ currentSessionId: id }, () => nav("popup.html"));
}

async function deleteSession(id) {
  try {
    const res = await apiFetch(`/history/sessions/${id}`, {
      method: "DELETE",
      headers: buildHeaders({ Authorization: `Bearer ${token}` })
    });
    if (res.status === 401) { nav("login.html"); return; }
    sessions = sessions.filter(s => s.id !== id);
    render();
  } catch(e) {}
}

async function clearAll() {
  if (!confirm("Delete all chat history?")) return;
  await Promise.allSettled(sessions.map(s =>
    apiFetch(`/history/sessions/${s.id}`, {
      method: "DELETE",
      headers: buildHeaders({ Authorization: `Bearer ${token}` })
    })
  ));
  sessions = [];
  chrome.storage.local.remove("currentSessionId");
  render();
}
