// Review Queue - Active Learning Interface

let currentFilter = "all";
let reviewQueue = [];
let stats = null;

// Helper functions
function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function buildHeaders(extra = {}) {
  return { ...extra };
}

async function apiFetch(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

// Navigation
document.getElementById("back-btn").addEventListener("click", () => {
  window.location.href = chrome.runtime.getURL("popup/popup.html");
});

document.getElementById("refresh-btn").addEventListener("click", () => {
  loadReviewQueue();
});

// Filter buttons
document.querySelectorAll(".review-filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".review-filter-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter;
    loadReviewQueue();
  });
});

// Load stats
async function loadStats() {
  try {
    const token = (await chrome.storage.local.get("token")).token;
    if (!token) {
      window.location.href = chrome.runtime.getURL("popup/login.html");
      return;
    }

    stats = await apiFetch("/review/stats", {
      headers: buildHeaders({ "Authorization": `Bearer ${token}` })
    });

    document.getElementById("stat-pending").textContent = stats.total_pending;
    document.getElementById("stat-today").textContent = stats.reviewed_today;
    document.getElementById("stat-priority").textContent = stats.high_priority_count;
  } catch (e) {
    console.error("Failed to load stats:", e);
  }
}

// Load review queue
async function loadReviewQueue() {
  const content = document.getElementById("review-content");
  content.innerHTML = `
    <div class="review-loading">
      <div class="spin-ring"></div>
      <div style="margin-top:12px;font-size:12px;color:var(--t3)">Loading review queue...</div>
    </div>`;

  try {
    const token = (await chrome.storage.local.get("token")).token;
    if (!token) {
      window.location.href = chrome.runtime.getURL("popup/login.html");
      return;
    }

    reviewQueue = await apiFetch(`/review/queue?priority=${currentFilter}&limit=20`, {
      headers: buildHeaders({ "Authorization": `Bearer ${token}` })
    });

    if (reviewQueue.length === 0) {
      content.innerHTML = `
        <div class="empty-state">
          <span class="material-symbols-outlined ms-24" style="color:var(--accent);margin-bottom:8px">check_circle</span>
          <div style="font-size:13px;color:var(--t2)">No claims to review</div>
          <div style="font-size:11px;color:var(--t3);margin-top:4px">All ${currentFilter} claims have been reviewed</div>
        </div>`;
      return;
    }

    renderReviewQueue();
    loadStats(); // Refresh stats
  } catch (e) {
    console.error("Failed to load review queue:", e);
    content.innerHTML = `
      <div class="error-state">
        <span class="material-symbols-outlined ms-24" style="color:var(--fake)">error</span>
        <div style="font-size:13px;color:var(--t2);margin-top:8px">Failed to load review queue</div>
        <div style="font-size:11px;color:var(--t3);margin-top:4px">${esc(e.message)}</div>
      </div>`;
  }
}

// Render review queue
function renderReviewQueue() {
  const content = document.getElementById("review-content");
  content.innerHTML = "";

  reviewQueue.forEach(item => {
    const card = createReviewCard(item);
    content.appendChild(card);
  });
}

// Create review card
function createReviewCard(item) {
  const card = document.createElement("div");
  card.className = "review-card";
  if (item.already_reviewed) {
    card.classList.add("review-card-reviewed");
  }

  const confPct = Math.round(item.confidence * 100);
  const mlPct = Math.round(item.ml_score * 100);
  const aiPct = item.ai_score ? Math.round(item.ai_score * 100) : null;
  const evidencePct = item.evidence_score ? Math.round(item.evidence_score * 100) : null;

  // Priority badges
  let priorityBadges = "";
  if (item.is_viral) {
    priorityBadges += `<span class="priority-badge priority-viral">🔥 Viral</span>`;
  }
  if (item.is_trending) {
    priorityBadges += `<span class="priority-badge priority-trending">📈 Trending</span>`;
  }
  if (item.cluster_size && item.cluster_size > 5) {
    priorityBadges += `<span class="priority-badge priority-cluster">🔗 ${item.cluster_size} similar</span>`;
  }

  card.innerHTML = `
    <div class="review-card-header">
      <div class="review-card-verdict ${item.current_verdict === 'fake' ? 'v-fake' : item.current_verdict === 'real' ? 'v-real' : 'v-uncertain'}">
        ${item.current_verdict.toUpperCase()}
      </div>
      <div class="review-card-conf">${confPct}%</div>
    </div>

    ${priorityBadges ? `<div class="review-card-badges">${priorityBadges}</div>` : ""}

    <div class="review-card-claim">${esc(item.claim_text)}</div>

    <div class="review-card-scores">
      <div class="review-score-item">
        <span class="review-score-label">ML</span>
        <div class="review-score-bar">
          <div class="review-score-fill" style="width:${mlPct}%;background:${mlPct > 50 ? 'var(--fake)' : 'var(--real)'}"></div>
        </div>
        <span class="review-score-val">${mlPct}%</span>
      </div>
      ${aiPct !== null ? `
      <div class="review-score-item">
        <span class="review-score-label">AI</span>
        <div class="review-score-bar">
          <div class="review-score-fill" style="width:${aiPct}%;background:var(--accent)"></div>
        </div>
        <span class="review-score-val">${aiPct}%</span>
      </div>` : ""}
      ${evidencePct !== null ? `
      <div class="review-score-item">
        <span class="review-score-label">Evidence</span>
        <div class="review-score-bar">
          <div class="review-score-fill" style="width:${evidencePct}%;background:${evidencePct > 50 ? 'var(--real)' : 'var(--fake)'}"></div>
        </div>
        <span class="review-score-val">${evidencePct}%</span>
      </div>` : ""}
    </div>

    ${item.already_reviewed ? `
      <div class="review-card-reviewed-note">
        <span class="material-symbols-outlined ms-12">check_circle</span>
        Already reviewed by you
      </div>
    ` : `
      <div class="review-card-actions">
        <button class="review-btn review-btn-real" data-id="${item.id}" data-verdict="real">
          <span class="material-symbols-outlined ms-14">check_circle</span>
          Real
        </button>
        <button class="review-btn review-btn-fake" data-id="${item.id}" data-verdict="fake">
          <span class="material-symbols-outlined ms-14">cancel</span>
          Fake
        </button>
        <button class="review-btn review-btn-skip" data-id="${item.id}">
          <span class="material-symbols-outlined ms-14">skip_next</span>
          Skip
        </button>
      </div>
    `}

    <div class="review-card-meta">
      <span class="material-symbols-outlined ms-12">schedule</span>
      ${formatDate(item.created_at)}
    </div>
  `;

  // Add event listeners for review buttons
  if (!item.already_reviewed) {
    card.querySelector(".review-btn-real").addEventListener("click", () => submitReview(item.id, "real", card));
    card.querySelector(".review-btn-fake").addEventListener("click", () => submitReview(item.id, "fake", card));
    card.querySelector(".review-btn-skip").addEventListener("click", () => skipReview(card));
  }

  return card;
}

// Submit review
async function submitReview(claimId, verdict, cardElement) {
  const buttons = cardElement.querySelectorAll(".review-btn");
  buttons.forEach(btn => btn.disabled = true);

  try {
    const token = (await chrome.storage.local.get("token")).token;
    
    await apiFetch("/review/submit", {
      method: "POST",
      headers: buildHeaders({
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      }),
      body: JSON.stringify({
        claim_id: claimId,
        verdict: verdict
      })
    });

    // Show success feedback
    cardElement.classList.add("review-card-submitted");
    cardElement.innerHTML = `
      <div class="review-success">
        <span class="material-symbols-outlined ms-24" style="color:var(--real)">check_circle</span>
        <div style="font-size:13px;color:var(--t1);margin-top:8px">Review submitted!</div>
        <div style="font-size:11px;color:var(--t3);margin-top:4px">Verdict: ${verdict.toUpperCase()}</div>
      </div>`;

    // Remove card after animation
    setTimeout(() => {
      cardElement.style.opacity = "0";
      cardElement.style.transform = "translateX(-20px)";
      setTimeout(() => {
        cardElement.remove();
        // Reload if queue is empty
        if (document.querySelectorAll(".review-card").length === 0) {
          loadReviewQueue();
        }
      }, 300);
    }, 1500);

    // Refresh stats
    loadStats();

  } catch (e) {
    console.error("Failed to submit review:", e);
    buttons.forEach(btn => btn.disabled = false);
    
    // Show error
    const errorDiv = document.createElement("div");
    errorDiv.className = "review-error";
    errorDiv.textContent = "Failed to submit review";
    cardElement.appendChild(errorDiv);
    setTimeout(() => errorDiv.remove(), 3000);
  }
}

// Skip review
function skipReview(cardElement) {
  cardElement.style.opacity = "0";
  cardElement.style.transform = "translateX(20px)";
  setTimeout(() => {
    cardElement.remove();
    if (document.querySelectorAll(".review-card").length === 0) {
      loadReviewQueue();
    }
  }, 300);
}

// Format date
function formatDate(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now - date;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

// Initialize
chrome.storage.local.get("token", d => {
  if (!d.token) {
    window.location.href = chrome.runtime.getURL("popup/login.html");
    return;
  }
  loadStats();
  loadReviewQueue();
});
