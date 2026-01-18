// Initialize context menu
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "analyze-fake-news",
    title: "Analyze with Fake News Analyzer",
    contexts: ["selection"]
  });
});

// Handle Context Menu Click
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "analyze-fake-news") {
    const text = info.selectionText;
    
    // Store the text
    chrome.storage.local.set({ selectedText: text }, () => {
      // We cannot open the popup programmatically.
      // We can try to notify the user or just let them know to open the popup.
      // For now, silent save is standard. The popup will pick it up on open.
      console.log("Text saved for analysis.");
    });
  }
});

// Handle Messages from Content Script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "TEXT_SELECTED") {
    chrome.storage.local.set({
      selectedText: message.payload
    });
  }
  return true;
});
