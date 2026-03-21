// API is defined in config.js (loaded before this script)

let token = null;
let user = null;
let currentSessionId = null;
let history = [];
let sessions = [];

const chatContainer = document.getElementById("chat-container");
const inputText     = document.getElementById("input-text");
const sendBtn       = document.getElementById("send-btn");

// ── Wire buttons ──────────────────────────────────────────────
document.getElementById("open-sidebar-btn").addEventListener("click", openSidebar);
document.getElementById("close-sidebar-btn").addEventListener("click", closeSidebar);
document.getElementById("sidebar-overlay").addEventListener("click", closeSidebar);
document.getElementById("new-chat-btn").addEventListener("click", newChat);
document.getElementById("new-chat-sidebar-btn").addEventListener("click", newChat);
document.getElementById("logout-btn").addEventListener("click", doLogout);
sendBtn.addEventListener("click", send);
inputText.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
inputText.addEventListener("input", autoResize);

// Sidebar nav — use chrome.runtime.getURL for Kiwi compatibility
document.getElementById("nav-dashboard").addEventListener("click", () => { window.location.href = chrome.runtime.getURL("popup/dashboard.html"); });
document.getElementById("nav-saved").addEventListener("click",     () => { window.location.href = chrome.runtime.getURL("popup/saved.html"); });
document.getElementById("nav-history").addEventListener("click",   () => { window.location.href = chrome.runtime.getURL("popup/history.html"); });
document.getElementById("nav-settings").addEventListener("click",  () => { window.location.href = chrome.runtime.getURL("popup/settings.html"); });

// ── Init ──────────────────────────────────────────────────────
chrome.storage.local.get(["token", "user", "currentSessionId"], async d => {
  if (!d.token) { window.location.href = chrome.runtime.getURL("popup/login.html"); return; }
  token = d.token;
  user  = d.user;
  currentSessionId = d.currentSessionId || null;
  updateUserUI();
  await loadSessions();
  if (currentSessionId) {
    await loadSessionMessages(currentSessionId);
  } else {
    showWelcome();
  }
  // Small delay to ensure storage write from service worker is complete
  setTimeout(() => {
    chrome.storage.local.get(["selectedText", "pendingAnalysis"], sd => {
      if (sd.selectedText && sd.pendingAnalysis) {
        chrome.storage.local.remove(["selectedText", "pendingAnalysis"]);
        inputText.value = sd.selectedText;
        autoResize();
        send();
      }
    });
  }, 150);
});

chrome.runtime.onMessage.addListener(msg => {
  if (msg.type === "ANALYZE_TEXT") { inputText.value = msg.text; send(); }
});

// ── User UI ───────────────────────────────────────────────────
function updateUserUI() {
  if (!user) return;
  const initials = (user.name || user.email || "?").charAt(0).toUpperCase();
  const avatarEl = document.getElementById("sidebar-avatar");
  if (avatarEl) {
    if (user.picture) {
      avatarEl.innerHTML = `<img src="${user.picture}" alt="">`;
    } else {
      avatarEl.textContent = initials;
    }
  }
  const nameEl  = document.getElementById("sidebar-name");
  const emailEl = document.getElementById("sidebar-email");
  if (nameEl)  nameEl.textContent  = user.name  || "User";
  if (emailEl) emailEl.textContent = user.email || "";
}

function doLogout() {
  chrome.storage.local.clear(() => { window.location.href = chrome.runtime.getURL("popup/login.html"); });
}

// ── Sidebar ───────────────────────────────────────────────────
function openSidebar() {
  document.getElementById("sidebar").style.transform = "translateX(0)";
  document.getElementById("sidebar-overlay").classList.add("visible");
}
function closeSidebar() {
  document.getElementById("sidebar").style.transform = "";
  document.getElementById("sidebar-overlay").classList.remove("visible");
}

// ── Sessions ──────────────────────────────────────────────────
async function loadSessions() {
  try {
    const res = await authFetch("/history/sessions");
    if (!res.ok) return;
    sessions = await res.json();
    renderSessions();
  } catch(_) {}
}

function renderSessions() {
  const list = document.getElementById("sessions-list");
  if (!list) return;
  list.innerHTML = "";
  if (!sessions.length) {
    const p = document.createElement("p");
    p.style.cssText = "font-size:11px;color:var(--t3);padding:8px 10px;";
    p.textContent = "No chats yet";
    list.appendChild(p);
    return;
  }
  sessions.forEach(s => {
    const div = document.createElement("div");
    div.className = "session-item" + (s.id === currentSessionId ? " active" : "");
    div.innerHTML = `
      <span class="material-symbols-outlined ms-14" style="color:var(--t3);flex-shrink:0">chat_bubble</span>
      <span class="s-title">${esc(s.title)}</span>
      <button class="session-del"><span class="material-symbols-outlined ms-12">delete</span></button>`;
    div.addEventListener("click", () => switchSession(s.id));
    div.querySelector(".session-del").addEventListener("click", e => {
      e.stopPropagation(); deleteSession(s.id);
    });
    list.appendChild(div);
  });
}

async function switchSession(id) {
  currentSessionId = id;
  chrome.storage.local.set({ currentSessionId: id });
  closeSidebar();
  const s = sessions.find(x => x.id === id);
  if (s) document.getElementById("chat-title").textContent = s.title;
  chatContainer.innerHTML = "";
  await loadSessionMessages(id);
  renderSessions();
}

async function loadSessionMessages(sessionId) {
  try {
    const res = await authFetch(`/history/sessions/${sessionId}/messages`);
    if (!res.ok) { showWelcome(); return; }
    const msgs = await res.json();
    if (!msgs.length) { showWelcome(); return; }
    chatContainer.innerHTML = "";
    history = [];
    msgs.forEach(m => {
      if (m.role === "user") {
        addUserMsg(m.content, false);
        history.push({ role: "user", content: m.content });
      } else {
        if (m.is_claim) {
          addFactCard(m, false);
        } else {
          addChatReply(m.content, false);
          history.push({ role: "assistant", content: m.content });
        }
      }
    });
    scrollBottom();
  } catch(_) { showWelcome(); }
}

async function newChat() {
  currentSessionId = null;
  history = [];
  chrome.storage.local.remove("currentSessionId");
  document.getElementById("chat-title").textContent = "FactCheck AI";
  chatContainer.innerHTML = "";
  showWelcome();
  closeSidebar();
}

async function deleteSession(id) {
  try {
    await authFetch(`/history/sessions/${id}`, { method: "DELETE" });
    sessions = sessions.filter(s => s.id !== id);
    if (currentSessionId === id) newChat();
    renderSessions();
  } catch(_) {}
}

// ── Chat UI ───────────────────────────────────────────────────
function showWelcome() {
  const wrap = document.createElement("div");
  wrap.className = "welcome-screen";
  wrap.innerHTML = `
    <div class="welcome-brand"><span class="brand-main">FactChecker</span><span class="brand-ai"> AI</span></div>
    <div class="welcome-sub">Ask me anything or paste a news claim.<br>I'll chat or fact-check automatically.</div>
    <div class="welcome-chips">
      <button class="welcome-chip" id="wc1">📰 Paste a headline to fact-check</button>
      <button class="welcome-chip" id="wc2">💬 Ask me anything</button>
    </div>`;
  chatContainer.innerHTML = "";
  chatContainer.appendChild(wrap);
  document.getElementById("wc1").addEventListener("click", () => setInput("Is this news real? [paste headline]"));
  document.getElementById("wc2").addEventListener("click", () => setInput("What is misinformation?"));
}

function setInput(text) {
  inputText.value = text;
  inputText.focus();
  autoResize();
}

const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const scrollBottom = () => { chatContainer.scrollTop = chatContainer.scrollHeight; };

function addUserMsg(text, scroll = true) {
  const el = document.createElement("div");
  el.className = "user-bubble";
  el.textContent = text;
  chatContainer.appendChild(el);
  if (scroll) scrollBottom();
}

function addTyping() {
  const row = document.createElement("div");
  row.className = "bot-row";
  row.innerHTML = `
    <div class="bot-avatar"><span class="material-symbols-outlined">smart_toy</span></div>
    <div class="bot-bubble"><div class="typing-dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>`;
  chatContainer.appendChild(row);
  scrollBottom();
  return row;
}

function addChatReply(text, scroll = true) {
  const row = document.createElement("div");
  row.className = "bot-row";
  const avatar = document.createElement("div");
  avatar.className = "bot-avatar";
  avatar.innerHTML = `<span class="material-symbols-outlined">smart_toy</span>`;
  const bubble = document.createElement("div");
  bubble.className = "bot-bubble";
  bubble.textContent = text;
  row.appendChild(avatar);
  row.appendChild(bubble);
  chatContainer.appendChild(row);
  if (scroll) scrollBottom();
}

function addFactCard(data, scroll = true) {
  const verdict  = (data.verdict || "uncertain").toLowerCase();
  const confPct  = Math.round((data.confidence || 0) * 100);
  const mlPct    = Math.round((data.ml_score   || 0) * 100);
  const aiPct    = Math.round((data.ai_score   || 0) * 100);
  // News score: evidence_score is a REAL signal (1=real), display as corroboration %
  const newsPct  = data.evidence_score != null
    ? Math.round(data.evidence_score * 100)
    : (data.evidence_articles?.length || data.evidence?.length) ? 60 : 0;

  const vClass  = verdict === "real" ? "v-real" : verdict === "fake" ? "v-fake" : "v-uncertain";
  const vIcon   = verdict === "real" ? "check_circle" : verdict === "fake" ? "cancel" : "help";
  const mlFill  = mlPct > 50 ? "fill-fake" : "fill-real";
  const newsFill = newsPct > 50 ? "fill-real" : "fill-fake";

  // Evidence section — shown after explanation
  const hasArticles = data.evidence_articles && data.evidence_articles.length;
  const hasUrls     = data.evidence && data.evidence.length;

  let srcHtml = "";
  if (hasArticles) {
    srcHtml = data.evidence_articles.slice(0, 4).map(a =>
      `<a href="${esc(a.url)}" target="_blank">
        <span class="src-name">${esc(a.source)}</span>
        <span class="src-title">${esc(a.title)}</span>
      </a>`
    ).join("");
  } else if (hasUrls) {
    srcHtml = data.evidence.slice(0, 4).map(s =>
      `<a href="${esc(s)}" target="_blank">↗ ${esc(s)}</a>`
    ).join("");
  }

  const explHtml = data.explanation
    ? `<div class="fact-expl">${esc(data.explanation)}</div>` : "";

  const srcSection = srcHtml
    ? `<div class="fact-sources">
        <div class="src-label">
          <span class="material-symbols-outlined ms-12">newspaper</span>
          News Evidence
        </div>
        ${srcHtml}
      </div>` : "";

  const row = document.createElement("div");
  row.className = "bot-row";

  const avatar = document.createElement("div");
  avatar.className = "bot-avatar";
  avatar.innerHTML = `<span class="material-symbols-outlined">fact_check</span>`;

  const card = document.createElement("div");
  card.className = "fact-card";
  card.innerHTML = `
    <div class="fact-header">
      <div class="verdict-badge ${vClass}">
        <span class="material-symbols-outlined ms-14">${vIcon}</span>
        ${verdict}
      </div>
      <span class="conf-text">Confidence: <strong>${confPct}%</strong></span>
    </div>
    <div class="fact-body">
      <div class="score-row">
        <span class="score-lbl">ML</span>
        <div class="score-track"><div class="score-fill ${mlFill} ml-bar"></div></div>
        <span class="score-num">${mlPct}%</span>
      </div>
      <div class="score-row">
        <span class="score-lbl">AI</span>
        <div class="score-track"><div class="score-fill fill-ai ai-bar"></div></div>
        <span class="score-num">${aiPct}%</span>
      </div>
      <div class="score-row">
        <span class="score-lbl">News</span>
        <div class="score-track"><div class="score-fill ${newsFill} news-bar"></div></div>
        <span class="score-num">${newsPct}%</span>
      </div>
      ${explHtml}
      ${srcSection}
      <div class="fact-actions">
        <button class="fact-btn view-btn">View Detail</button>
        <button class="fact-btn primary save-btn">Save Claim</button>
      </div>
    </div>`;

  row.appendChild(avatar);
  row.appendChild(card);
  chatContainer.appendChild(row);

  card.querySelector(".ml-bar").style.width   = `${mlPct}%`;
  card.querySelector(".ai-bar").style.width   = `${aiPct}%`;
  card.querySelector(".news-bar").style.width = `${newsPct}%`;
  card.querySelector(".view-btn").addEventListener("click", () => viewDetail(data));
  card.querySelector(".save-btn").addEventListener("click", () => saveCard(data));

  if (scroll) scrollBottom();
}

function viewDetail(data) {
  chrome.storage.local.set({ detailData: data }, () => { window.location.href = chrome.runtime.getURL("popup/detail.html"); });
}

function saveCard(data) {
  chrome.storage.local.get("savedClaims", d => {
    const claims = d.savedClaims || [];
    const key = data.content || data.explanation || "";
    if (claims.some(c => (c.content || c.explanation || "") === key)) return;
    claims.unshift(data);
    chrome.storage.local.set({ savedClaims: claims.slice(0, 50) });
  });
}

// ── Send ──────────────────────────────────────────────────────
async function send() {
  const text = inputText.value.trim();
  if (!text) return;
  inputText.value = "";
  autoResize();

  // Clear welcome screen if present
  if (chatContainer.querySelector(".welcome-screen")) {
    chatContainer.innerHTML = "";
  }

  addUserMsg(text);
  const typing = addTyping();
  sendBtn.disabled = true;

  try {
    const body = { message: text, session_id: currentSessionId, history };
    const res  = await authFetch("/message", { method: "POST", body: JSON.stringify(body) });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();
    typing.remove();

    if (data.session_id && data.session_id !== currentSessionId) {
      currentSessionId = data.session_id;
      chrome.storage.local.set({ currentSessionId });
      await loadSessions();
    }

    if (data.is_claim) {
      addFactCard(data);
    } else {
      addChatReply(data.reply);
      history.push({ role: "user", content: text });
      history.push({ role: "assistant", content: data.reply });
      if (history.length > 20) history = history.slice(-20);
    }

    if (currentSessionId) {
      const s = sessions.find(x => x.id === currentSessionId);
      if (s) document.getElementById("chat-title").textContent = s.title;
    }
  } catch(err) {
    typing.remove();
    addChatReply(`Connection error: ${err.message}. Make sure the backend is running.`);
  } finally {
    sendBtn.disabled = false;
  }
}

// ── Helpers ───────────────────────────────────────────────────
async function authFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "Authorization": `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    }
  });
  if (res.status === 401) {
    chrome.storage.local.clear(() => { window.location.href = chrome.runtime.getURL("popup/login.html"); });
  }
  return res;
}

function autoResize() {
  inputText.style.height = "auto";
  inputText.style.height = Math.min(inputText.scrollHeight, 88) + "px";
}