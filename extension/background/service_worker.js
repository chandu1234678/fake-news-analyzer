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
    chrome.storage.local.set({ selectedText: text }, () => {
      // Open the popup as a standalone window
      chrome.windows.create({
        url: chrome.runtime.getURL("popup/popup.html"),
        type: "popup",
        width: 420,
        height: 600
      });
    });
  }
});

// Handle Messages from Content Script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "TEXT_SELECTED") {
    chrome.storage.local.set({ selectedText: message.payload });
  }
  return true;
});
