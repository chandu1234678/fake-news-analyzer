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
// Show spinner immediately — before any async work
chatContainer.innerHTML = `
  <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:12px;opacity:0.5">
    <div class="spin-ring"></div>
    <span style="font-size:12px;color:var(--t3)">Loading…</span>
  </div>`;

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
    const data = await readJsonSafe(res) || {};
    // Handle both paginated {sessions, total} and legacy array response
    sessions = Array.isArray(data) ? data : (data.sessions || []);
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
  // Show skeleton while loading
  chatContainer.innerHTML = `
    <div class="skeleton-wrap">
      <div class="skeleton-line" style="width:60%"></div>
      <div class="skeleton-line" style="width:85%"></div>
      <div class="skeleton-line" style="width:45%"></div>
    </div>
    <div class="skeleton-wrap" style="align-items:flex-end">
      <div class="skeleton-line" style="width:50%"></div>
    </div>
    <div class="skeleton-wrap">
      <div class="skeleton-line" style="width:75%"></div>
      <div class="skeleton-line" style="width:90%"></div>
    </div>`;
  try {
    const res = await authFetch(`/history/sessions/${sessionId}/messages`);
    if (!res.ok) { showWelcome(); return; }
    const msgs = await readJsonSafe(res) || [];
    if (!msgs.length) { showWelcome(); return; }
    chatContainer.innerHTML = "";
    history = [];
    msgs.forEach(m => {
      if (m.role === "user") {
        addUserMsg(m.content, false);
        history.push({ role: "user", content: m.content });
      } else {
        if (m.is_claim) {
          addFactCard(m, false, false);
        } else {
          addChatReply(m.content, false, false);
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

const escapeHtml = s => String(s)
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;")
  .replace(/'/g, "&#39;");
const esc = escapeHtml;
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

function addUserMsg(text, scroll = true, imageUrl = null) {
  const el = document.createElement("div");
  el.className = "user-bubble";
  if (imageUrl) {
    const img = document.createElement("img");
    img.src = imageUrl;
    img.style.cssText = "max-width:100%;max-height:160px;border-radius:8px;display:block;margin-bottom:6px;object-fit:cover";
    img.alt = "attached image";
    el.appendChild(img);
  }
  const textNode = document.createElement("span");
  textNode.textContent = text || (imageUrl ? "Image attached" : "");
  el.appendChild(textNode);
  chatContainer.appendChild(el);
  if (scroll) scrollBottom();
}

function addTyping() {
  const row = document.createElement("div");
  row.className = "bot-row";
  row.innerHTML = `
    <div class="bot-avatar"><span class="material-symbols-outlined">fact_check</span></div>
    <div class="bot-bubble typing-status">
      <span class="typing-step" id="ts1">Analyzing claim...</span>
      <span class="typing-step" id="ts2">Checking sources...</span>
      <span class="typing-step" id="ts3">Computing verdict...</span>
    </div>`;
  chatContainer.appendChild(row);
  scrollBottom();

  // Show only one step at a time, cycling
  const steps = row.querySelectorAll(".typing-step");
  let step = 0;
  steps[0].classList.add("active");

  const timer = setInterval(() => {
    steps[step].classList.remove("active");
    step = (step + 1) % steps.length;
    steps[step].classList.add("active");
  }, 1400);

  row._clearTimer = () => clearInterval(timer);
  const origRemove = row.remove.bind(row);
  row.remove = () => { row._clearTimer(); origRemove(); };
  return row;
}

function addChatReply(text, scroll = true, animate = true) {
  const row = document.createElement("div");
  row.className = "bot-row";
  const avatar = document.createElement("div");
  avatar.className = "bot-avatar";
  avatar.innerHTML = `<span class="material-symbols-outlined">smart_toy</span>`;
  const bubble = document.createElement("div");
  bubble.className = "bot-bubble";
  row.appendChild(avatar);
  row.appendChild(bubble);
  chatContainer.appendChild(row);

  if (!animate) {
    bubble.innerHTML = renderMarkdown(text);
    if (scroll) scrollBottom();
    return;
  }

  // Word-by-word typewriter then render markdown at end
  const words = text.split(" ");
  let i = 0;
  const tw = setInterval(() => {
    i++;
    bubble.textContent = words.slice(0, i).join(" ");
    if (i >= words.length) {
      clearInterval(tw);
      bubble.innerHTML = renderMarkdown(text);
    }
    if (scroll) scrollBottom();
  }, 35);
}

function renderMarkdown(text) {
  const safe = escapeHtml(text || "");
  return safe
    // Bold **text**
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    // Italic *text*
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    // Numbered list: "1. item" at start of line
    .replace(/^(\d+)\.\s+(.+)$/gm, "<li style='margin:4px 0;list-style:decimal;margin-left:18px'>$2</li>")
    // Bullet list: "- item" or "• item"
    .replace(/^[-•]\s+(.+)$/gm, "<li style='margin:4px 0;list-style:disc;margin-left:18px'>$1</li>")
    // Wrap consecutive <li> in <ol> or <ul>
    .replace(/(<li[^>]*>.*<\/li>\n?)+/g, m => `<ul style="margin:6px 0;padding:0">${m}</ul>`)
    // Line breaks
    .replace(/\n/g, "<br>");
}

function ensureArray(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeMessageResponse(data) {
  const normalized = data && typeof data === "object" ? { ...data } : {};
  normalized.evidence_articles = ensureArray(normalized.evidence_articles);
  normalized.evidence = ensureArray(normalized.evidence);
  normalized.highlights = ensureArray(normalized.highlights);
  normalized.manipulation_signals = ensureArray(normalized.manipulation_signals);
  normalized.sub_claims = ensureArray(normalized.sub_claims);
  if (!normalized.stance_summary || typeof normalized.stance_summary !== "object") {
    normalized.stance_summary = { support: 0, contradict: 0, neutral: 0 };
  }
  return normalized;
}

function feedbackClaimText(data) {
  return data.primary_claim || data.content || data.explanation || "";
}

function addFactCard(data, scroll = true, animate = true) {
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

  // ── Phase 2: Cooldown friction UX ─────────────────────────────
  const cooldown = data.cooldown || null;
  if (cooldown && cooldown.cooldown_level) {
    const level = cooldown.cooldown_level;
    
    if (level === "VIRAL_PANIC") {
      showViralPanicInterstitial(data, cooldown, () => {
        _renderFactCard(data, scroll, animate);
      });
      return;
    } else if (level === "HIGH_CONCERN") {
      showHighConcernFriction(data, cooldown, () => {
        _renderFactCard(data, scroll, animate);
      });
      return;
    } else if (level === "CAUTION") {
      showCautionBanner(data, cooldown);
    }
  }

  // Normal rendering (no friction or CAUTION level)
  _renderFactCard(data, scroll, animate);
}

// ── Friction UX Components (Phase 2.3) ────────────────────────

function showViralPanicInterstitial(data, cooldown, onComplete) {
  const overlay = document.createElement("div");
  overlay.className = "friction-overlay viral-panic";
  overlay.innerHTML = `
    <div class="friction-modal">
      <div class="friction-icon">
        <span class="material-symbols-outlined">warning</span>
      </div>
      <div class="friction-title">⚠️ VIRAL MISINFORMATION ALERT</div>
      <div class="friction-subtitle">This claim is spreading rapidly and shows high risk of being false</div>
      <div class="friction-stats">
        <div class="friction-stat">
          <span class="friction-stat-label">Fake Probability</span>
          <span class="friction-stat-value">${Math.round((cooldown.breakdown?.components?.fake_probability?.value || 0) * 100)}%</span>
        </div>
        <div class="friction-stat">
          <span class="friction-stat-label">Velocity Score</span>
          <span class="friction-stat-value">${Math.round((cooldown.breakdown?.components?.velocity?.value || 0) * 100)}%</span>
        </div>
        <div class="friction-stat">
          <span class="friction-stat-label">Cooldown Score</span>
          <span class="friction-stat-value">${Math.round((cooldown.cooldown_score || 0) * 100)}%</span>
        </div>
      </div>
      <div class="friction-message">
        Please take a moment to review the evidence before sharing this content.
        Viral misinformation can cause real harm.
      </div>
      <div class="friction-countdown">
        <div class="countdown-ring">
          <svg class="countdown-svg" viewBox="0 0 36 36">
            <path class="countdown-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
            <path class="countdown-progress" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
          </svg>
          <div class="countdown-number" id="friction-countdown">10</div>
        </div>
        <div class="countdown-label">seconds remaining</div>
      </div>
      <button class="friction-btn friction-btn-disabled" id="friction-continue" disabled>Continue to Analysis</button>
      <button class="friction-btn-link" id="friction-bypass">I understand the risks, skip this</button>
    </div>
  `;
  
  document.body.appendChild(overlay);
  
  let secondsLeft = cooldown.delay_seconds || 10;
  const countdownEl = document.getElementById("friction-countdown");
  const continueBtn = document.getElementById("friction-continue");
  const bypassBtn = document.getElementById("friction-bypass");
  const progressPath = overlay.querySelector(".countdown-progress");
  
  const timer = setInterval(() => {
    secondsLeft--;
    countdownEl.textContent = secondsLeft;
    
    const progress = ((cooldown.delay_seconds - secondsLeft) / cooldown.delay_seconds) * 100;
    progressPath.style.strokeDasharray = `${progress}, 100`;
    
    if (secondsLeft <= 0) {
      clearInterval(timer);
      continueBtn.disabled = false;
      continueBtn.classList.remove("friction-btn-disabled");
      continueBtn.classList.add("friction-btn-enabled");
    }
  }, 1000);
  
  continueBtn.addEventListener("click", () => {
    clearInterval(timer);
    trackFrictionEvent("viral_panic_completed", cooldown);
    overlay.remove();
    onComplete();
  });
  
  bypassBtn.addEventListener("click", () => {
    clearInterval(timer);
    trackFrictionEvent("viral_panic_bypassed", cooldown);
    overlay.remove();
    onComplete();
  });
}

function showHighConcernFriction(data, cooldown, onComplete) {
  const row = document.createElement("div");
  row.className = "bot-row";
  
  const avatar = document.createElement("div");
  avatar.className = "bot-avatar";
  avatar.innerHTML = `<span class="material-symbols-outlined">warning</span>`;
  
  const card = document.createElement("div");
  card.className = "friction-card high-concern";
  card.innerHTML = `
    <div class="friction-card-header">
      <span class="material-symbols-outlined friction-card-icon">report</span>
      <div class="friction-card-title">High-Risk Content Detected</div>
    </div>
    <div class="friction-card-body">
      <div class="friction-card-message">
        This claim shows signs of rapid spread and potential misinformation.
        Please review the analysis carefully before sharing.
      </div>
      <div class="friction-card-stats">
        <div class="friction-mini-stat">
          <span class="friction-mini-label">Cooldown Score</span>
          <span class="friction-mini-value">${Math.round((cooldown.cooldown_score || 0) * 100)}%</span>
        </div>
        <div class="friction-mini-stat">
          <span class="friction-mini-label">Velocity</span>
          <span class="friction-mini-value">${Math.round((cooldown.breakdown?.components?.velocity?.value || 0) * 100)}%</span>
        </div>
      </div>
      <div class="friction-card-countdown">
        <div class="friction-countdown-bar">
          <div class="friction-countdown-fill" id="friction-countdown-fill"></div>
        </div>
        <div class="friction-countdown-text">
          Please wait <span id="friction-countdown-seconds">5</span> seconds...
        </div>
      </div>
      <button class="friction-card-btn friction-btn-disabled" id="friction-card-continue" disabled>
        View Analysis
      </button>
    </div>
  `;
  
  row.appendChild(avatar);
  row.appendChild(card);
  chatContainer.appendChild(row);
  scrollBottom();
  
  let secondsLeft = cooldown.delay_seconds || 5;
  const secondsEl = document.getElementById("friction-countdown-seconds");
  const fillEl = document.getElementById("friction-countdown-fill");
  const continueBtn = document.getElementById("friction-card-continue");
  
  const timer = setInterval(() => {
    secondsLeft--;
    secondsEl.textContent = secondsLeft;
    
    const progress = ((cooldown.delay_seconds - secondsLeft) / cooldown.delay_seconds) * 100;
    fillEl.style.width = `${progress}%`;
    
    if (secondsLeft <= 0) {
      clearInterval(timer);
      continueBtn.disabled = false;
      continueBtn.classList.remove("friction-btn-disabled");
      continueBtn.classList.add("friction-btn-enabled");
      continueBtn.textContent = "Continue to Analysis";
    }
  }, 1000);
  
  continueBtn.addEventListener("click", () => {
    clearInterval(timer);
    trackFrictionEvent("high_concern_completed", cooldown);
    row.remove();
    onComplete();
  });
}

function showCautionBanner(data, cooldown) {
  const banner = document.createElement("div");
  banner.className = "friction-banner caution";
  banner.innerHTML = `
    <span class="material-symbols-outlined friction-banner-icon">info</span>
    <div class="friction-banner-content">
      <div class="friction-banner-title">Caution: Verify Before Sharing</div>
      <div class="friction-banner-text">
        This content shows moderate risk signals. Review the analysis below.
      </div>
    </div>
    <button class="friction-banner-close" id="friction-banner-close">
      <span class="material-symbols-outlined">close</span>
    </button>
  `;
  
  chatContainer.appendChild(banner);
  scrollBottom();
  
  document.getElementById("friction-banner-close").addEventListener("click", () => {
    trackFrictionEvent("caution_dismissed", cooldown);
    banner.remove();
  });
  
  trackFrictionEvent("caution_shown", cooldown);
}

function trackFrictionEvent(eventType, cooldown) {
  try {
    chrome.storage.local.get("frictionAnalytics", d => {
      const analytics = d.frictionAnalytics || [];
      analytics.push({
        event: eventType,
        cooldown_level: cooldown.cooldown_level,
        cooldown_score: cooldown.cooldown_score,
        timestamp: Date.now()
      });
      chrome.storage.local.set({ frictionAnalytics: analytics.slice(-100) });
    });
  } catch (e) {
    console.warn("Failed to track friction event:", e);
  }
}

// ── Internal fact card renderer ───────────────────────────────

function _renderFactCard(data, scroll = true, animate = true) {
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

  const evidenceArticles = ensureArray(data.evidence_articles);
  const evidenceUrls = ensureArray(data.evidence);
  const hasArticles = evidenceArticles.length;
  const hasUrls     = evidenceUrls.length;

  let srcHtml = "";
  if (hasArticles) {
    srcHtml = evidenceArticles.slice(0, 4).map(a => {
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
    srcHtml = evidenceUrls.slice(0, 4).map(s => {
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

  // Sub-claims extracted from long input
  let subClaimsHtml = "";
  if (data.sub_claims?.length > 1) {
    const items = data.sub_claims.map((c, i) =>
      `<div class="subclaim-item"><span class="subclaim-num">${i + 1}</span>${esc(c)}</div>`
    ).join("");
    subClaimsHtml = `
      <div class="subclaims-section">
        <div class="src-label">
          <span class="material-symbols-outlined ms-12">format_list_bulleted</span>
          Extracted claims
        </div>
        ${items}
        <div class="subclaim-note">Verdict based on: "${esc(data.primary_claim)}"</div>
      </div>`;
  }

  // Highlighted suspicious phrases
  let highlightHtml = "";
  if (data.highlights?.length) {
    const tags = data.highlights.map(h => {
      const cls = h.score >= 0.75 ? "hl-high" : h.score >= 0.5 ? "hl-med" : "hl-low";
      const tip = h.reason === "sensational" ? "Sensational language"
                : h.reason === "emotional"   ? "Emotional language"
                : h.reason === "absolute_claim" ? "Absolute claim"
                : "ML signal";
      return `<span class="hl-tag ${cls}" title="${tip}">${esc(h.phrase)}</span>`;
    }).join("");
    highlightHtml = `
      <div class="highlights-section">
        <div class="src-label">
          <span class="material-symbols-outlined ms-12">flag</span>
          Suspicious phrases
        </div>
        <div class="hl-tags">${tags}</div>
      </div>`;
  }

  const explHtml = data.explanation
    ? `<div class="fact-expl">${esc(data.explanation)}</div>` : "";

  // Manipulation badge
  let manipHtml = "";
  if (data.manipulation_score > 0.15 && data.manipulation_signals?.length) {
    const level = data.manipulation_score >= 0.5 ? "HIGH" : "MED";
    const cls   = data.manipulation_score >= 0.5 ? "manip-high" : "manip-med";
    const tags  = data.manipulation_signals.slice(0, 3).join(" · ");
    manipHtml = `
      <div class="manip-badge ${cls}">
        <span class="material-symbols-outlined ms-12">warning</span>
        Manipulation signals (${level}): ${esc(tags)}
      </div>`;
  }

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

  const moderation = data.moderation_summary || null;
  let moderationHtml = "";
  if (moderation) {
    const riskPct = Math.round((moderation.risk || 0) * 100);
    const rec = (moderation.recommendation || "allow").toLowerCase();
    const recLabel = rec === "review" ? "REVIEW" : "ALLOW";
    const recCls = rec === "review" ? "mod-review" : "mod-allow";
    const flags = ensureArray(moderation.flags).slice(0, 3).join(" · ");
    moderationHtml = `
      <div class="mod-summary ${recCls}">
        <div class="mod-row">
          <span class="material-symbols-outlined ms-12">policy</span>
          <span class="mod-label">Moderation: ${recLabel}</span>
          <span class="mod-risk">${riskPct}%</span>
        </div>
        <div class="mod-risk-bar"><div class="mod-risk-fill" style="width:${riskPct}%"></div></div>
        ${flags ? `<div class="mod-flags">${esc(flags)}</div>` : ""}
      </div>`;
  }

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
      ${data.verdict_changed ? `<div class="verdict-changed-note">⚠️ This claim's verdict has changed since it was last checked.</div>` : ""}
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
      ${moderationHtml}
      ${manipHtml}
      ${subClaimsHtml}
      ${highlightHtml}
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
  card.querySelector(".save-btn").addEventListener("click", e => saveCard(data, e.currentTarget));
  card.querySelector(".feedback-btn").addEventListener("click", () => showFeedback(card, data));

  // Typewriter effect on explanation (only for new messages)
  const explEl = card.querySelector(".fact-expl");
  if (explEl && data.explanation && animate) {
    const full = data.explanation;
    explEl.textContent = "";
    let i = 0;
    const tw = setInterval(() => {
      explEl.textContent += full[i];
      i++;
      if (i >= full.length) clearInterval(tw);
      scrollBottom();
    }, 12);
  }

  if (scroll) scrollBottom();
}


function viewDetail(data) {
  chrome.storage.local.set({ detailData: data }, () => { window.location.href = chrome.runtime.getURL("popup/detail.html"); });
}

function saveCard(data, btn) {
  chrome.storage.local.get("savedClaims", d => {
    const claims = d.savedClaims || [];
    const key = data.content || data.explanation || "";
    if (claims.some(c => (c.content || c.explanation || "") === key)) {
      if (btn) { btn.textContent = "Already saved"; btn.disabled = true; }
      return;
    }
    claims.unshift(data);
    chrome.storage.local.set({ savedClaims: claims.slice(0, 50) });
    if (btn) {
      btn.textContent = "Saved ✓";
      btn.style.background = "var(--real)";
      btn.style.color = "#fff";
      btn.disabled = true;
    }
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
        claim_text: feedbackClaimText(data),
        predicted:  data.verdict || "uncertain",
        actual,
        confidence: data.confidence || null,
      })
    });
  } catch(_) {}
}

// ── Attach menu ───────────────────────────────────────────────
let attachedImageUrl = null;
let attachedFileText = null;
let attachedFileName = null;

const attachBtn  = document.getElementById("attach-btn");
const attachMenu = document.getElementById("attach-menu");

attachBtn.addEventListener("click", e => {
  e.stopPropagation();
  attachMenu.style.display = attachMenu.style.display === "none" ? "block" : "none";
});
document.addEventListener("click", () => { attachMenu.style.display = "none"; });

function _showPreview(icon, name) {
  document.getElementById("attach-preview-icon").textContent = icon;
  document.getElementById("attach-preview-name").textContent = name;
  document.getElementById("attach-preview-bar").style.display = "flex";
  attachMenu.style.display = "none";
}

function _clearAttach() {
  attachedImageUrl = null;
  attachedFileText = null;
  attachedFileName = null;
  document.getElementById("attach-preview-bar").style.display = "none";
  ["file-image","file-pdf","file-txt"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
}

document.getElementById("attach-remove-btn").addEventListener("click", _clearAttach);

// Image — compress to JPEG max 800px before sending to avoid 413
document.getElementById("file-image").addEventListener("change", e => {
  const file = e.target.files[0];
  if (!file) return;
  const img = new Image();
  const objectUrl = URL.createObjectURL(file);
  img.onload = () => {
    URL.revokeObjectURL(objectUrl);
    const MAX = 800;
    let w = img.width, h = img.height;
    if (w > MAX || h > MAX) {
      const ratio = Math.min(MAX / w, MAX / h);
      w = Math.round(w * ratio);
      h = Math.round(h * ratio);
    }
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    canvas.getContext("2d").drawImage(img, 0, 0, w, h);
    // Compress to JPEG at 0.6 quality — keeps base64 under 300KB for most images
    attachedImageUrl = canvas.toDataURL("image/jpeg", 0.6);
    attachedFileName = file.name;
    _showPreview("image", `${file.name} (compressed)`);
  };
  img.src = objectUrl;
});

// PDF — extract text using PDF.js (loaded from CDN) or send filename as hint
document.getElementById("file-pdf").addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;
  attachedFileName = file.name;
  _showPreview("picture_as_pdf", `${file.name} (reading...)`);

  try {
    // Try to extract text using FileReader + basic text extraction
    const arrayBuffer = await file.arrayBuffer();
    // Simple PDF text extraction — look for text between BT/ET markers
    const bytes = new Uint8Array(arrayBuffer);
    const text  = new TextDecoder('latin1').decode(bytes);
    const matches = text.match(/\(([^)]{5,200})\)/g) || [];
    const extracted = matches
      .map(m => m.slice(1, -1).replace(/\\n/g, ' ').replace(/\\/g, '').trim())
      .filter(s => /[a-zA-Z]{3,}/.test(s))
      .join(' ')
      .slice(0, 2000);

    if (extracted.length > 50) {
      attachedFileText = extracted;
      inputText.value  = extracted.slice(0, 500);
      autoResize();
      _showPreview("picture_as_pdf", file.name);
    } else {
      // Fallback: just use filename as context
      attachedFileText = `PDF document: ${file.name}`;
      inputText.value  = `Fact-check this PDF: ${file.name}`;
      autoResize();
      _showPreview("picture_as_pdf", file.name);
    }
  } catch (err) {
    attachedFileText = `PDF: ${file.name}`;
    inputText.value  = `Fact-check this document: ${file.name}`;
    autoResize();
    _showPreview("picture_as_pdf", file.name);
  }
  inputText.focus();
});

// Text / DOC file
document.getElementById("file-txt").addEventListener("change", e => {
  const file = e.target.files[0];
  if (!file) return;

  // DOCX/DOC are binary ZIP files — can't read as text
  if (file.name.endsWith('.docx') || file.name.endsWith('.doc')) {
    attachedFileText = `Document: ${file.name}`;
    attachedFileName = file.name;
    inputText.value  = `Summarize and fact-check this document: ${file.name}`;
    autoResize();
    _showPreview("description", `${file.name} (name only — open file to copy text)`);
    inputText.focus();
    return;
  }

  const reader = new FileReader();
  reader.onload = ev => {
    const text = ev.target.result.slice(0, 3000);
    attachedFileText = text;
    attachedFileName = file.name;
    inputText.value  = text;
    autoResize();
    _showPreview("description", file.name);
    inputText.focus();
  };
  reader.readAsText(file);
});
async function send() {
  const text = inputText.value.trim();
  // Allow send if there's an image attached even with no text
  if (!text && !attachedImageUrl) return;
  inputText.value = "";
  autoResize();

  if (chatContainer.querySelector(".welcome-screen")) {
    chatContainer.innerHTML = "";
  }

  // Capture and clear attachments before async
  const imageUrl = attachedImageUrl;
  _clearAttach();

  // If image attached with no/short message, use a descriptive prompt
  let sendText = text;
  if (imageUrl && text.length < 10) {
    sendText = text.length > 0 ? text : "What does this image show? Is there any misinformation or fake news in it?";
  }
  // Ensure sendText is never empty (backend requires non-empty message)
  if (!sendText) sendText = "Analyze this content";
  addUserMsg(text, true, imageUrl);
  const typing = addTyping();
  sendBtn.disabled = true;

  try {
    const body = { message: sendText, session_id: currentSessionId, history };
    if (imageUrl) body.image_url = imageUrl;
    const res  = await authFetch("/message", { method: "POST", body: JSON.stringify(body) });
    const data = await readJsonSafe(res);
    if (!res.ok) {
      let detail = `Server error ${res.status}`;
      if (data) {
        if (typeof data.detail === "string") detail = data.detail;
        else if (Array.isArray(data.detail)) detail = data.detail.map(e => e.msg || JSON.stringify(e)).join("; ");
        else if (typeof data.message === "string") detail = data.message;
      }
      throw new Error(detail);
    }
    typing.remove();

    if (data.session_id && data.session_id !== currentSessionId) {
      currentSessionId = data.session_id;
      chrome.storage.local.set({ currentSessionId });
      await loadSessions();
    }

    const normalized = normalizeMessageResponse(data || {});
    if (normalized.is_claim) {
      addFactCard(normalized);
    } else {
      addChatReply(normalized.reply || "");
      history.push({ role: "user", content: text });
      history.push({ role: "assistant", content: normalized.reply || "" });
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
  const res = await apiFetch(path, {
    ...opts,
    headers: buildHeaders({
      "Content-Type": "application/json",
      ...(token ? { "Authorization": `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    })
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