const API = "http://127.0.0.1:8000";

// ── Keep-alive ping every 4 minutes to prevent Render free tier sleep ─────────
function pingBackend() {
  fetch(`${API}/health`, { method: "HEAD" }).catch(() => {});
}
// Ping on startup
pingBackend();
// Ping every 4 minutes (Render sleeps after 15 min of inactivity)
setInterval(pingBackend, 4 * 60 * 1000);

// ── Context menu ──────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "analyze-fake-news",
    title: "🔍 TruthScan this",
    contexts: ["selection"]
  });
  // Schedule periodic alarm for keep-alive (more reliable than setInterval in MV3)
  chrome.alarms.create("keepAlive", { periodInMinutes: 4 });
});

// Alarm-based keep-alive (MV3 service workers can be suspended)
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "keepAlive") pingBackend();
});

// Handle Context Menu Click
chrome.contextMenus.onClicked.addListener((info, _tab) => {
  if (info.menuItemId === "analyze-fake-news") {
    const text = info.selectionText;
    chrome.storage.local.set({ selectedText: text, pendingAnalysis: true }, () => {
      chrome.windows.getCurrent(win => {
        const width  = 440;
        const height = 640;
        const left   = (win.left + win.width) - width - 20;
        const top    = win.top + 60;
        chrome.windows.create({
          url: chrome.runtime.getURL("popup/popup.html"),
          type: "popup",
          width, height, left, top,
          focused: true
        });
      });
    });
  }
});

// Handle Messages from Content Script
chrome.runtime.onMessage.addListener((message, _sender, _sendResponse) => {
  if (message.type === "TEXT_SELECTED") {
    chrome.storage.local.set({ selectedText: message.payload });
  }
  if (message.type === "OPEN_POPUP_WITH_TEXT") {
    chrome.storage.local.set({ selectedText: message.text, pendingAnalysis: true }, () => {
      chrome.windows.getCurrent(win => {
        const width  = 440;
        const height = 640;
        const left   = (win.left + win.width) - width - 20;
        const top    = win.top + 60;
        chrome.windows.create({
          url: chrome.runtime.getURL("popup/popup.html"),
          type: "popup",
          width, height, left, top,
          focused: true
        });
      });
    });
  }
  return true;
});
