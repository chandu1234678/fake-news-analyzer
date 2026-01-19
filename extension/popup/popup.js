document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-container');
    const inputText = document.getElementById('input-text');
    const analyzeBtn = document.getElementById('analyze-btn');

    // Helper: Scroll to bottom
    const scrollToBottom = () => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    };

    // Helper: Add message to chat
    const addMessage = (content, type, isHtml = false) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${type}`;
        
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        
        if (isHtml) {
            bubble.innerHTML = content;
        } else {
            bubble.textContent = content;
        }
        
        msgDiv.appendChild(bubble);
        chatContainer.appendChild(msgDiv);
        scrollToBottom();
        return msgDiv; // Return for updates (e.g., loading)
    };

    // API Call
    const analyzeText = async (text) => {
        if (!text || !text.trim()) return;

        // Add user message
        addMessage(text, 'user');

        // Add loading message
        const loadingDiv = addMessage('⏳ Analyzing...', 'system');
        
        try {
            const response = await fetch("https://fake-news-analyzer-j6ka.onrender.com/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, explain: true })
            });

            if (!response.ok) {
                throw new Error("Backend connection failed");
            }

            const data = await response.json();
            
            // Format result
            const verdictClass = data.verdict === 'fake' ? 'fake' : (data.verdict === 'real' ? 'real' : '');
            
            let evidenceHtml = '';
            if (data.evidence && data.evidence.length > 0) {
                evidenceHtml = `<div class="evidence-section"><div class="evidence-title">Verified Sources:</div>`;
                data.evidence.forEach(url => {
                    evidenceHtml += `<a href="${url}" target="_blank" class="evidence-link">${url}</a>`;
                });
                evidenceHtml += `</div>`;
            } else {
                 evidenceHtml = `<div class="evidence-section"><div class="evidence-title">No direct evidence found.</div></div>`;
            }

            const resultHtml = `
                <div class="result-header">
                    <span class="verdict ${verdictClass}">${data.verdict.toUpperCase()}</span>
                    <span>${data.confidence}</span>
                </div>
                <div class="score-row">
                   <span>ML Score: ${data.ml_score}</span>
                   <span>AI Score: ${data.ai_score}</span>
                </div>
                <div class="explanation">
                   ${data.explanation}
                </div>
                ${evidenceHtml}
            `;

            // Remove loading and add result
            chatContainer.removeChild(loadingDiv);
            addMessage(resultHtml, 'system', true);

        } catch (error) {
            chatContainer.removeChild(loadingDiv);
            addMessage(`❌ Error: ${error.message}. Is the backend running?`, 'system');
        }
    };

    // 1. Check for pending text from context menu
    chrome.storage.local.get('selectedText', (data) => {
        if (data.selectedText) {
            analyzeText(data.selectedText);
            // Clear it so we don't re-analyze on reload (optional, but good UX)
            chrome.storage.local.remove('selectedText');
        }
    });

    // 2. Listen for new messages (if panel is already open)
    chrome.runtime.onMessage.addListener((message) => {
        if (message.type === 'ANALYZE_TEXT') {
            analyzeText(message.text);
        }
    });

    // 3. Manual Input
    analyzeBtn.addEventListener('click', () => {
        const text = inputText.value;
        if (text) {
            analyzeText(text);
            inputText.value = '';
        }
    });
    
    // Enter key support
    inputText.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            analyzeBtn.click();
        }
    });
});
