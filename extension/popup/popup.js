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
    <img src="../icons/logo.png" alt="" class="welcome-logo-img" style="width:56px;height:56px;object-fit:contain;margin-bottom:4px;">
    <div class="welcome-brand"><span class="brand-main">FactChecker</span><span class="brand-ai"> AI</span></div>
    <div class="welcome-sub">Ask me anything or paste a news claim.<br>I'll chat or fact-check automatically.</div>
    <div class="welcome-chips">
      <button class="welcome-chip" id="wc1">📰 Paste a headline to fact-check</button>
      <button class="welcome-chip" id="wc2">💬 Ask me anything</button>
      <button class="welcome-chip welcome-chip-page" id="wc3">🌐 Analyze this page</button>
    </div>`;
  chatContainer.innerHTML = "";
  chatContainer.appendChild(wrap);
  document.getElementById("wc1").addEventListener("click", () => setInput("Is this news real? [paste headline]"));
  document.getElementById("wc2").addEventListener("click", () => setInput("What is misinformation?"));
  document.getElementById("wc3").addEventListener("click", analyzeCurrentPage);
}

function setInput(text) {
  inputText.value = text;
  inputText.focus();
  autoResize();
}

async function analyzeCurrentPage() {
  // Get the active tab and extract its text via content script
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      addChatReply("Couldn't access the current tab. Try pasting the text manually.");
      return;
    }
    // Inject a one-shot script to grab visible text
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        // Grab main article text, fallback to body
        const article = document.querySelector("article, main, [role='main']");
        const el = article || document.body;
        return el.innerText.replace(/\s+/g, " ").trim().slice(0, 1200);
      }
    });
    const pageText = results?.[0]?.result;
    if (!pageText || pageText.length < 30) {
      addChatReply("Couldn't extract enough text from this page. Try pasting the claim manually.");
      return;
    }
    inputText.value = pageText;
    autoResize();
    send();
  } catch (err) {
    addChatReply("Page analysis isn't available here. Try on a news article page.");
  }
}

const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const scrollBottom = () => { chatContainer.scrollTop = chatContainer.scrollHeight; };

// ── Source credibility ────────────────────────────────────────
const HIGH_CRED_DOMAINS = new Set([
  "reuters.com","apnews.com","bbc.com","bbc.co.uk","npr.org",
  "theguardian.com","nytimes.com","washingtonpost.com","wsj.com",
  "bloomberg.com","ft.com","economist.com","nature.com","science.org",
  "who.int","cdc.gov","nih.gov","gov.uk","europa.eu","un.org",
  "snopes.com","factcheck.org","politifact.com","fullfact.org",
  "aljazeera.com","dw.com","france24.com","abc.net.au","cbc.ca"
]);

function getCredTag(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (HIGH_CRED_DOMAINS.has(host)) return { label: "HIGH", cls: "cred-high" };
    return { label: "MED", cls: "cred-med" };
  } catch { return { label: "MED", cls: "cred-med" }; }
}

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
    <div class="bot-avatar"><span class="material-symbols-outlined">fact_check</span></div>
    <div class="bot-bubble typing-status">
      <span class="typing-step active" id="ts1">Analyzing claim...</span>
      <span class="typing-step" id="ts2">Checking sources...</span>
      <span class="typing-step" id="ts3">Computing verdict...</span>
    </div>`;
  chatContainer.appendChild(row);
  scrollBottom();

  // Cycle through steps to feel alive
  let step = 0;
  const steps = row.querySelectorAll(".typing-step");
  const timer = setInterval(() => {
    steps.forEach(s => s.classList.remove("active"));
    step = (step + 1) % steps.length;
    steps[step].classList.add("active");
  }, 1400);
  row._clearTimer = () => clearInterval(timer);

  const origRemove = row.remove.bind(row);
  row.remove = () => { row._clearTimer(); origRemove(); };

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
  const newsPct  = data.evidence_score != null
    ? Math.round(data.evidence_score * 100)
    : (data.evidence_articles?.length || data.evidence?.length) ? 60 : 0;

  const srcCount = data.evidence_articles?.length || data.evidence?.length || 0;

  const vClass    = verdict === "real" ? "v-real" : verdict === "fake" ? "v-fake" : "v-uncertain";
  const vIcon     = verdict === "real" ? "check_circle" : verdict === "fake" ? "cancel" : "help";
  const vLabel    = verdict === "real" ? "REAL" : verdict === "fake" ? "FAKE" : "UNCERTAIN";
  const confColor = verdict === "real" ? "var(--real)" : verdict === "fake" ? "var(--fake)" : "var(--warn)";
  const mlFill    = mlPct > 50 ? "fill-fake" : "fill-real";
  const newsFill  = newsPct > 50 ? "fill-real" : "fill-fake";

  const hasArticles = data.evidence_articles && data.evidence_articles.length;
  const hasUrls     = data.evidence && data.evidence.length;

  let srcHtml = "";
  if (hasArticles) {
    srcHtml = data.evidence_articles.slice(0, 4).map(a => {
      const cred = getCredTag(a.url || "");
      return `<a href="${esc(a.url)}" target="_blank">
        <div class="src-name-row">
          <span class="src-name">${esc(a.source)}</span>
          <span class="src-cred ${cred.cls}">${cred.label}</span>
        </div>
        <span class="src-title">${esc(a.title)}</span>
      </a>`;
    }).join("");
  } else if (hasUrls) {
    srcHtml = data.evidence.slice(0, 4).map(s => {
      const cred = getCredTag(s);
      let domain = s;
      try { domain = new URL(s).hostname.replace(/^www\./, ""); } catch {}
      return `<a href="${esc(s)}" target="_blank">
        <div class="src-name-row">
          <span class="src-name">${esc(domain)}</span>
          <span class="src-cred ${cred.cls}">${cred.label}</span>
        </div>
      </a>`;
    }).join("");
  }

  const explHtml = data.explanation
    ? `<div class="fact-expl">${esc(data.explanation)}</div>` : "";

  // Contradiction meter
  const ss = data.stance_summary;
  let stanceHtml = "";
  if (ss && (ss.support + ss.contradict + ss.neutral) > 0) {
    const total = ss.support + ss.contradict + ss.neutral;
    const supPct  = Math.round((ss.support    / total) * 100);
    const conPct  = Math.round((ss.contradict / total) * 100);
    const neuPct  = 100 - supPct - conPct;
    const meterLabel = ss.contradict > ss.support
      ? "⚠️ Sources conflict"
      : ss.support > 0
        ? "✓ Sources agree"
        : "Sources neutral";
    stanceHtml = `
      <div class="stance-meter">
        <div class="stance-label">${meterLabel}</div>
        <div class="stance-bar">
          <div class="stance-seg stance-sup" style="width:${supPct}%" title="Support: ${ss.support}"></div>
          <div class="stance-seg stance-neu" style="width:${neuPct}%" title="Neutral: ${ss.neutral}"></div>
          <div class="stance-seg stance-con" style="width:${conPct}%" title="Contradict: ${ss.contradict}"></div>
        </div>
        <div class="stance-counts">
          <span class="stance-sup-txt">${ss.support} support</span>
          <span class="stance-neu-txt">${ss.neutral} neutral</span>
          <span class="stance-con-txt">${ss.contradict} conflict</span>
        </div>
      </div>`;
  }

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
    <div class="fact-verdict-hero">
      <div class="verdict-main">
        <span class="material-symbols-outlined verdict-icon-lg ${vClass}">${vIcon}</span>
        <span class="verdict-word ${vClass}">${vLabel}</span>
      </div>
      <div class="verdict-conf-row">
        <span class="verdict-conf-pct">${confPct}%</span>
        <span class="verdict-conf-label">confidence</span>
        <div class="verdict-conf-bar">
          <div class="verdict-conf-fill conf-bar" style="background:${confColor}"></div>
        </div>
      </div>
      <div class="verdict-meta">
        <span class="material-symbols-outlined ms-12">database</span>
        Analyzed from ${srcCount} source${srcCount !== 1 ? "s" : ""} · Bias checked · ML + AI + News
      </div>
      ${verdict === "uncertain" ? `<div class="uncertain-note">Signals conflict or evidence is insufficient for a definitive verdict.</div>` : ""}
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
      ${stanceHtml}
      ${srcSection}
      <div class="fact-actions">
        <button class="fact-btn view-btn">View Detail</button>
        <button class="fact-btn primary save-btn">Save Claim</button>
        <button class="fact-btn feedback-btn" title="Report wrong verdict">⚑ Wrong?</button>
      </div>
    </div>`;

  row.appendChild(avatar);
  row.appendChild(card);
  chatContainer.appendChild(row);

  card.querySelector(".ml-bar").style.width    = `${mlPct}%`;
  card.querySelector(".ai-bar").style.width    = `${aiPct}%`;
  card.querySelector(".news-bar").style.width  = `${newsPct}%`;
  card.querySelector(".conf-bar").style.width  = `${confPct}%`;
  card.querySelector(".view-btn").addEventListener("click", () => viewDetail(data));
  card.querySelector(".save-btn").addEventListener("click", () => saveCard(data));
  card.querySelector(".feedback-btn").addEventListener("click", () => showFeedback(card, data));

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

function showFeedback(card, data) {
  // Replace actions row with inline correction picker
  const actionsEl = card.querySelector(".fact-actions");
  actionsEl.innerHTML = `
    <span class="feedback-prompt">Correct verdict:</span>
    <button class="fact-btn feedback-real">✓ Real</button>
    <button class="fact-btn feedback-fake">✗ Fake</button>
    <button class="fact-btn feedback-cancel">Cancel</button>`;
  actionsEl.querySelector(".feedback-real").addEventListener("click", () => submitFeedback(card, data, "real"));
  actionsEl.querySelector(".feedback-fake").addEventListener("click", () => submitFeedback(card, data, "fake"));
  actionsEl.querySelector(".feedback-cancel").addEventListener("click", () => {
    actionsEl.innerHTML = `
      <button class="fact-btn view-btn">View Detail</button>
      <button class="fact-btn primary save-btn">Save Claim</button>
      <button class="fact-btn feedback-btn" title="Report wrong verdict">⚑ Wrong?</button>`;
    actionsEl.querySelector(".view-btn").addEventListener("click", () => viewDetail(data));
    actionsEl.querySelector(".save-btn").addEventListener("click", () => saveCard(data));
    actionsEl.querySelector(".feedback-btn").addEventListener("click", () => showFeedback(card, data));
  });
}

async function submitFeedback(card, data, actual) {
  const actionsEl = card.querySelector(".fact-actions");
  actionsEl.innerHTML = `<span class="feedback-prompt" style="color:var(--real)">✓ Feedback recorded</span>`;
  try {
    await authFetch("/feedback", {
      method: "POST",
      body: JSON.stringify({
        claim_text: data.explanation || "",
        predicted:  data.verdict || "uncertain",
        actual,
        confidence: data.confidence || null,
      })
    });
  } catch(_) {}
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