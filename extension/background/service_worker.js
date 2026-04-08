// Initialize context menu
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "analyze-fake-news",
    title: "🔍 TruthScan this",
    contexts: ["selection"]
  });
});

// Handle Context Menu Click — open popup window with selected text
chrome.contextMenus.onClicked.addListener((info, tab) => {
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
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "TEXT_SELECTED") {
    chrome.storage.local.set({ selectedText: message.payload });
  }

  if (message.type === "OPEN_POPUP_WITH_TEXT") {
    const text = message.text;
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

  return true;
});
