// API is defined in config.js (loaded before this script)
let token = null;
let sessions = [];

chrome.storage.local.get(["token"], async d => {
  if (!d.token) { window.location.href = "login.html"; return; }
  token = d.token;
  await load();
});

document.getElementById("clear-btn").addEventListener("click", clearAll);

function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

async function load() {
  try {
    const res = await fetch(`${API}/history/sessions`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) return;
    sessions = await res.json();
    render();
  } catch(e) {}
}

function render() {
  const list = document.getElementById("sessions-list");
  list.innerHTML = "";
  if (!sessions.length) {
    list.innerHTML = `
      <div style="text-align:center;padding:40px 0">
        <span class="material-symbols-outlined ms-24" style="color:var(--t3)">history</span>
        <div style="font-size:12px;color:var(--t3);margin-top:8px">No chat history yet</div>
        <a href="popup.html" style="font-size:12px;color:var(--accent);display:block;margin-top:4px">Start a conversation</a>
      </div>`;
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
  chrome.storage.local.set({ currentSessionId: id }, () => {
    window.location.href = "popup.html";
  });
}

async function deleteSession(id) {
  try {
    await fetch(`${API}/history/sessions/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` }
    });
    sessions = sessions.filter(s => s.id !== id);
    render();
  } catch(e) {}
}

async function clearAll() {
  if (!confirm("Delete all chat history?")) return;
  for (const s of sessions) {
    try {
      await fetch(`${API}/history/sessions/${s.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
    } catch(e) {}
  }
  sessions = [];
  chrome.storage.local.remove("currentSessionId");
  render();
}
