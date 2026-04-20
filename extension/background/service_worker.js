/**
 * PiNE AI — Background Service Worker (Manifest V3)
 *
 * Responsibilities:
 *  - Keep backend alive (alarm-based ping every 4 min)
 *  - Context menu: "TruthScan this" on selected text
 *  - Keyboard shortcuts:
 *      Ctrl+Shift+Y  — open popup
 *      Ctrl+Shift+U  — fact-check selected text
 *      Ctrl+Shift+L  — fact-check visible page text
 *  - Message relay from content script
 */

// Load optional local inference module.
try {
  importScripts("onnx_inference.js");
} catch (_e) {
  // Keep background worker functional even when local inference script is unavailable.
}

// ── Backend URL (reads from storage if overridden in settings) ────────────────
// Default points to production Render deployment
let API_BASE = "https://fake-news-analyzer-j6ka.onrender.com";
const OFFLINE_QUEUE_KEY = "offlineClaimQueue";
const LOCAL_INFERENCE_ENABLED = true;
const INFERENCE_TIMEOUT_MS = 500;
const ANALYSIS_CACHE_TTL_MS = 24 * 60 * 60 * 1000;
const ANALYSIS_CACHE_LIMIT = 100;

let localInferenceReady = false;

chrome.storage.local.get("apiBase", ({ apiBase }) => {
  if (apiBase) API_BASE = apiBase;
});

// ── Keep-alive ────────────────────────────────────────────────────────────────
function pingBackend() {
  fetch(`${API_BASE}/health`, { method: "HEAD" }).catch(() => {});
}

async function initializeLocalInference() {
  if (!LOCAL_INFERENCE_ENABLED) {
    localInferenceReady = false;
    await chrome.storage.local.set({ localInferenceReady: false });
    return;
  }

  try {
    if (typeof localInference === "undefined") {
      localInferenceReady = false;
      await chrome.storage.local.set({ localInferenceReady: false });
      return;
    }

    await localInference.initialize();
    localInferenceReady = true;
    await chrome.storage.local.set({ localInferenceReady: true });
  } catch {
    localInferenceReady = false;
    await chrome.storage.local.set({ localInferenceReady: false });
  }
}

async function syncPendingQueueInBackground() {
  try {
    const data = await chrome.storage.local.get([OFFLINE_QUEUE_KEY, "token"]);
    const queue = Array.isArray(data[OFFLINE_QUEUE_KEY]) ? data[OFFLINE_QUEUE_KEY] : [];
    const token = data.token;
    if (!queue.length || !token) return;

    const remaining = [];
    for (const item of queue) {
      try {
        const body = {
          message: item.message,
          session_id: item.session_id || null,
          history: item.history || [],
        };
        if (item.image_url) body.image_url = item.image_url;

        const res = await fetch(`${API_BASE}/message`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
          },
          body: JSON.stringify(body),
        });

        if (!res.ok) remaining.push(item);
      } catch {
        remaining.push(item);
      }
    }

    await chrome.storage.local.set({ [OFFLINE_QUEUE_KEY]: remaining });
  } catch {
    // Keep background sync best-effort and non-blocking.
  }
}

// ── Install / update ──────────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(({ reason }) => {
  // Context menu
  chrome.contextMenus.create({
    id:       "analyze-fake-news",
    title:    "🔍 TruthScan with PiNE AI",
    contexts: ["selection"],
  });

  // Alarm-based keep-alive (MV3 service workers can be suspended;
  // setInterval is unreliable — alarms survive suspension)
  chrome.alarms.create("keepAlive", { periodInMinutes: 4 });

  // Ping immediately on install/update
  pingBackend();
  initializeLocalInference();

  if (reason === "install") {
    // Show a one-time welcome notification
    chrome.notifications.create("pine-welcome", {
      type:    "basic",
      iconUrl: chrome.runtime.getURL("icons/icon128.png"),
      title:   "PiNE AI installed",
      message: "Press Ctrl+Shift+Y to open, or right-click any text to fact-check.",
    });
  }
});

// ── Alarm handler ─────────────────────────────────────────────────────────────
chrome.alarms.onAlarm.addListener(({ name }) => {
  if (name === "keepAlive") {
    pingBackend();
    syncPendingQueueInBackground();
  }
});

chrome.runtime.onStartup.addListener(() => {
  pingBackend();
  syncPendingQueueInBackground();
  initializeLocalInference();
});

function hashText(text) {
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    hash = ((hash << 5) - hash) + text.charCodeAt(i);
    hash |= 0;
  }
  return hash.toString(36);
}

async function getAnalysisCacheEntry(text) {
  const key = hashText(String(text || ""));
  const data = await chrome.storage.local.get(["analysisCache"]);
  const cache = data.analysisCache || {};
  const entry = cache[key];
  if (!entry) return null;
  if (Date.now() - entry.timestamp > ANALYSIS_CACHE_TTL_MS) return null;
  return entry;
}

async function setAnalysisCacheEntry(text, result) {
  const key = hashText(String(text || ""));
  const data = await chrome.storage.local.get(["analysisCache"]);
  const cache = data.analysisCache || {};

  const keys = Object.keys(cache);
  if (keys.length >= ANALYSIS_CACHE_LIMIT) {
    const oldest = keys.reduce((a, b) => cache[a].timestamp < cache[b].timestamp ? a : b);
    delete cache[oldest];
  }

  cache[key] = result;
  await chrome.storage.local.set({ analysisCache: cache });
}

async function clearAnalysisCache() {
  await chrome.storage.local.set({ analysisCache: {} });
}

async function backendAnalysis(text) {
  const storage = await chrome.storage.local.get(["token"]);
  const token = storage.token;
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}/message`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message: text })
  });

  if (!response.ok) throw new Error(`Backend API error: ${response.status}`);
  const data = await response.json();

  return {
    verdict: data.verdict,
    confidence: data.confidence,
    fake_probability: data.ml_score || 0,
    explanation: data.explanation,
    evidence: data.evidence || [],
    is_claim: data.is_claim,
    source: "backend"
  };
}

async function handleAnalysis(text, options = {}) {
  const startedAt = performance.now();
  const input = String(text || "").trim();
  if (!input) throw new Error("Text is required");

  if (options.useCache !== false) {
    const cached = await getAnalysisCacheEntry(input);
    if (cached) {
      return {
        ...cached,
        cached: true,
        total_time_ms: performance.now() - startedAt,
      };
    }
  }

  const settings = await chrome.storage.local.get(["useLocalInference", "fallbackToBackend"]);
  const useLocal = settings.useLocalInference !== false;
  const useFallback = settings.fallbackToBackend !== false;

  let result = null;
  let method = null;

  if (useLocal && localInferenceReady && typeof localInference !== "undefined") {
    try {
      result = await Promise.race([
        localInference.predict(input),
        new Promise((_, reject) => setTimeout(() => reject(new Error("Local inference timeout")), INFERENCE_TIMEOUT_MS))
      ]);
      method = "local";
    } catch (_err) {
      if (!useFallback) throw _err;
    }
  }

  if (!result && useFallback) {
    result = await backendAnalysis(input);
    method = "backend";
  }

  if (!result) throw new Error("No analysis method available");

  const enriched = {
    ...result,
    method,
    timestamp: Date.now(),
    total_time_ms: performance.now() - startedAt,
  };

  if (options.useCache !== false) {
    await setAnalysisCacheEntry(input, enriched);
  }

  return enriched;
}

// ── Shared helpers ────────────────────────────────────────────────────────────

/**
 * Open the PiNE AI popup window anchored to the top-right of the current window.
 */
function openAnalysisPopup() {
  chrome.windows.getCurrent((win) => {
    const width  = 440;
    const height = 640;
    const left   = Math.max(0, (win.left + win.width) - width - 20);
    const top    = win.top + 60;
    chrome.windows.create({
      url:     chrome.runtime.getURL("popup/popup.html"),
      type:    "popup",
      width, height, left, top,
      focused: true,
    });
  });
}

/**
 * Store text in local storage and open the popup.
 * The popup reads selectedText + pendingAnalysis on load and auto-sends.
 */
function openPopupWithText(text) {
  const safeText = (text || "").trim();
  chrome.storage.local.set(
    { selectedText: safeText, pendingAnalysis: !!safeText },
    openAnalysisPopup
  );
}

/**
 * Get the currently selected text from a tab via scripting injection.
 */
async function getSelectedTextFromPage(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func:   () => (window.getSelection()?.toString() ?? "").trim(),
    });
    return results?.[0]?.result || "";
  } catch {
    return "";
  }
}

/**
 * Get the main visible text from a tab (article > main > body, max 1200 chars).
 */
async function getVisiblePageText(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const el = document.querySelector("article, main, [role='main']") || document.body;
        return (el?.innerText || "").replace(/\s+/g, " ").trim().slice(0, 1200);
      },
    });
    return results?.[0]?.result || "";
  } catch {
    return "";
  }
}

/**
 * Get the currently active tab in the focused window.
 */
async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs?.[0] ?? null;
}

/**
 * Show a brief notification (used for shortcut feedback when no text found).
 */
function notify(message) {
  chrome.notifications.create({
    type:    "basic",
    iconUrl: chrome.runtime.getURL("icons/icon48.png"),
    title:   "PiNE AI",
    message,
  });
}

// ── Context menu ──────────────────────────────────────────────────────────────
chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === "analyze-fake-news") {
    openPopupWithText(info.selectionText || "");
  }
});

// ── Keyboard shortcuts ────────────────────────────────────────────────────────
chrome.commands.onCommand.addListener(async (command) => {
  // Ctrl+Shift+Y — just open the popup
  if (command === "open-factchecker") {
    openPopupWithText("");
    return;
  }

  const tab = await getActiveTab();

  // Ctrl+Shift+U — fact-check selected text
  if (command === "analyze-selected-text") {
    if (!tab?.id) { openPopupWithText(""); return; }
    const text = await getSelectedTextFromPage(tab.id);
    if (text) {
      openPopupWithText(text);
    } else {
      notify("No text selected. Select some text on the page first.");
      openPopupWithText("");
    }
    return;
  }

  // Ctrl+Shift+L — fact-check visible page text
  if (command === "analyze-current-page") {
    if (!tab?.id) { openPopupWithText(""); return; }
    const text = await getVisiblePageText(tab.id);
    if (text) {
      openPopupWithText(text);
    } else {
      notify("Could not extract text from this page.");
      openPopupWithText("");
    }
  }
});

// ── Messages from content script / popup ─────────────────────────────────────
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  switch (message.type) {
    case "TEXT_SELECTED":
      // Content script reports a text selection (passive — no popup)
      chrome.storage.local.set({ selectedText: message.payload || "" });
      break;

    case "OPEN_POPUP_WITH_TEXT":
      // Any page can request the popup with specific text
      openPopupWithText(message.text || "");
      break;

    case "PING_BACKEND":
      // Popup can request an immediate ping (e.g. on load to check connectivity)
      pingBackend();
      break;

    case "SYNC_OFFLINE_QUEUE":
      syncPendingQueueInBackground()
        .then(() => sendResponse({ ok: true }))
        .catch(() => sendResponse({ ok: false }));
      return true;

    case "ANALYZE_TEXT":
      handleAnalysis(message.text || message.payload, message.options || {})
        .then((result) => sendResponse({ success: true, ...result }))
        .catch((error) => sendResponse({ success: false, error: error.message }));
      return true;

    case "GET_MODEL_INFO": {
      const info = {
        localInferenceReady,
        localInferenceEnabled: LOCAL_INFERENCE_ENABLED,
      };
      if (typeof localInference !== "undefined" && localInference.getInfo) {
        Object.assign(info, localInference.getInfo());
      }
      sendResponse({ success: true, info });
      break;
    }

    case "CLEAR_CACHE":
      clearAnalysisCache()
        .then(() => sendResponse({ success: true }))
        .catch((error) => sendResponse({ success: false, error: error.message }));
      return true;

    case "GET_API_BASE":
      // Popup asks for the current API base URL
      sendResponse({ apiBase: API_BASE });
      break;

    case "SET_API_BASE":
      // Settings page updates the API base URL
      if (message.apiBase) {
        API_BASE = message.apiBase;
        chrome.storage.local.set({ apiBase: API_BASE });
      }
      break;
  }
  // Return true to keep the message channel open for async sendResponse
  return true;
});
