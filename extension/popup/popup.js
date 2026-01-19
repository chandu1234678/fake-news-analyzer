document.addEventListener('DOMContentLoaded', () => {
  const chatContainer = document.getElementById('chat-container');
  const inputText = document.getElementById('input-text');
  const sendBtn = document.getElementById('send-btn');
  const BACKEND_URL = "https://fake-news-analyzer-j6ka.onrender.com/analyze";

  // Auto-resize textarea
  inputText.addEventListener('input', () => {
    inputText.style.height = 'auto';
    inputText.style.height = Math.min(inputText.scrollHeight, 120) + 'px';
  });

  const scrollToBottom = () => {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  };

  const addMessage = (content, type) => {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}`;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    if (typeof content === 'string') {
      bubble.textContent = content;
    } else if (content instanceof Node) {
      bubble.appendChild(content);
    }

    msgDiv.appendChild(bubble);
    chatContainer.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
  };

  const showTypingIndicator = () => {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system typing';
    msgDiv.innerHTML = `
      <div class="bubble typing-indicator">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
      </div>
    `;
    chatContainer.appendChild(msgDiv);
    scrollToBottom();
    return msgDiv;
  };

  const sendMessage = async (text) => {
    if (!text || !text.trim()) return;

    // UI Updates
    addMessage(text, 'user');
    inputText.value = '';
    inputText.style.height = 'auto'; // Reset height
    inputText.focus();

    sendBtn.disabled = true;
    const typingMsg = showTypingIndicator();

    try {
      const response = await fetch(BACKEND_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
      });

      // Remove typing indicator
      if (chatContainer.contains(typingMsg)) {
        chatContainer.removeChild(typingMsg);
      }

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();
      renderResponse(data);

    } catch (error) {
      if (chatContainer.contains(typingMsg)) {
        chatContainer.removeChild(typingMsg);
      }
      addMessage(`Error: ${error.message}`, 'system error-message');
    } finally {
      sendBtn.disabled = false;
      inputText.focus();
    }
  };

  const renderResponse = (data) => {
    const fragment = document.createDocumentFragment();

    // Verdict Badge (only if present and meaningful)
    if (data.verdict) {
      const verdictDiv = document.createElement('div');
      verdictDiv.className = `verdict-badge ${data.verdict.toLowerCase()}`;
      verdictDiv.textContent = data.verdict;
      fragment.appendChild(verdictDiv);
    }

    // Explanation (Main content)
    const explanationDiv = document.createElement('div');
    explanationDiv.className = 'response-content';
    explanationDiv.textContent = data.explanation || "No explanation provided.";
    fragment.appendChild(explanationDiv);

    // Evidence
    if (data.evidence && Array.isArray(data.evidence) && data.evidence.length > 0) {
      const validEvidence = data.evidence.filter(e => e && typeof e === 'string' && !e.includes("No verified sources"));

      if (validEvidence.length > 0) {
        const evidenceList = document.createElement('div');
        evidenceList.className = 'evidence-list';

        const header = document.createElement('div');
        header.className = 'evidence-header';
        header.textContent = 'Sources:';
        evidenceList.appendChild(header);

        validEvidence.forEach(url => {
            let item;
            if (url.startsWith('http')) {
                 item = document.createElement('a');
                 item.href = url;
                 item.target = "_blank";
                 item.className = 'evidence-link';
                 item.textContent = url;
            } else {
                 item = document.createElement('div');
                 item.className = 'evidence-link';
                 item.textContent = url;
            }
            evidenceList.appendChild(item);
        });
        fragment.appendChild(evidenceList);
      }
    }

    addMessage(fragment, 'system');
  };

  // Event Listeners
  sendBtn.addEventListener('click', () => {
    sendMessage(inputText.value);
  });

  inputText.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputText.value);
    }
  });

  // Check for selected text on open
  chrome.storage.local.get('selectedText', (data) => {
    if (data.selectedText) {
      sendMessage(data.selectedText);
      chrome.storage.local.remove('selectedText');
    } else {
      addMessage("Hi! I'm your fact-checking assistant. Send me a claim or ask a question.", 'system');
    }
  });

  // Listen for new messages (e.g. from context menu while popup is open)
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'TEXT_SELECTED') {
      sendMessage(message.payload);
    }
  });
});
