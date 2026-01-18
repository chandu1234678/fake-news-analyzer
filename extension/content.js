document.addEventListener("mouseup", () => {
  const selectedText = window.getSelection().toString().trim();

  if (selectedText.length > 10) {
    chrome.runtime.sendMessage({
      type: "TEXT_SELECTED",
      payload: selectedText
    }).catch(err => {
      // Ignore errors if extension context is invalidated (e.g. after update)
      // or if no background listener is ready yet.
      console.log("Fake News Analyzer: Could not send selection", err);
    });
  }
});
