function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

document.getElementById("back-btn").addEventListener("click", () => {
  window.location.href = chrome.runtime.getURL("popup/popup.html");
});

chrome.storage.local.get(["token", "detailData"], d => {
  if (!d.token) { window.location.href = chrome.runtime.getURL("popup/login.html"); return; }
  if (!d.detailData) return;
  render(d.detailData);
});

function render(data) {
  const v       = (data.verdict || "uncertain").toLowerCase();
  const vClass  = v === "real" ? "v-real" : v === "fake" ? "v-fake" : "v-uncertain";
  const vIcon   = v === "real" ? "check_circle" : v === "fake" ? "cancel" : "help";
  const confPct = Math.round((data.confidence || 0) * 100);
  const mlPct   = Math.round((data.ml_score   || 0) * 100);
  const aiPct   = Math.round((data.ai_score   || 0) * 100);
  const mlFill  = mlPct > 60 ? "fill-fake" : "fill-real";

  const content = document.getElementById("detail-content");
  content.innerHTML = "";

  // Verdict banner
  const banner = document.createElement("div");
  banner.className = "card";
  banner.style.cssText = "display:flex;align-items:center;gap:14px;margin-bottom:10px";
  banner.innerHTML = `
    <span class="material-symbols-outlined ms-24 ${vClass}">${vIcon}</span>
    <div>
      <div style="font-size:16px;font-weight:700;text-transform:uppercase" class="${vClass}">${v}</div>
      <div style="font-size:11px;color:var(--t3)">${confPct}% confidence</div>
    </div>`;
  content.appendChild(banner);

  // Claim text
  const claimText = data.content || data.explanation || "";
  if (claimText) {
    const claimEl = document.createElement("div");
    claimEl.className = "card";
    claimEl.innerHTML = `
      <div class="card-title">Claim</div>
      <div style="font-size:13px;color:var(--t1);line-height:1.6">${esc(claimText)}</div>`;
    content.appendChild(claimEl);
  }

  // Scores
  const scoresEl = document.createElement("div");
  scoresEl.className = "card";
  scoresEl.innerHTML = `
    <div class="card-title">Analysis Scores</div>
    <div style="display:flex;flex-direction:column;gap:10px">
      <div>
        <div style="display:flex;justify-content:space-between;margin-bottom:5px">
          <span style="font-size:11px;color:var(--t3)">ML Model</span>
          <span style="font-size:11px;font-weight:600;color:var(--t1)">${mlPct}%</span>
        </div>
        <div class="score-track" style="height:5px"><div class="score-fill ${mlFill} ml-bar"></div></div>
      </div>
      <div>
        <div style="display:flex;justify-content:space-between;margin-bottom:5px">
          <span style="font-size:11px;color:var(--t3)">AI Analysis</span>
          <span style="font-size:11px;font-weight:600;color:var(--t1)">${aiPct}%</span>
        </div>
        <div class="score-track" style="height:5px"><div class="score-fill fill-ai ai-bar"></div></div>
      </div>
    </div>`;
  content.appendChild(scoresEl);
  scoresEl.querySelector(".ml-bar").style.width = `${mlPct}%`;
  scoresEl.querySelector(".ai-bar").style.width = `${aiPct}%`;

  // Explanation
  if (data.explanation) {
    const explEl = document.createElement("div");
    explEl.className = "card";
    explEl.innerHTML = `
      <div class="card-title">AI Explanation</div>
      <div style="font-size:12.5px;color:var(--t2);line-height:1.65">${esc(data.explanation)}</div>`;
    content.appendChild(explEl);
  }

  // Sources
  if (data.evidence && data.evidence.length) {
    const srcEl = document.createElement("div");
    srcEl.className = "card";
    srcEl.innerHTML = `<div class="card-title">Sources</div><div id="sources-list"></div>`;
    content.appendChild(srcEl);
    const srcList = document.getElementById("sources-list");
    data.evidence.forEach(s => {
      const a = document.createElement("a");
      a.href = s;
      a.target = "_blank";
      a.style.cssText = "display:flex;align-items:center;gap:6px;font-size:12px;color:var(--accent);text-decoration:none;margin-bottom:5px;overflow:hidden";
      a.innerHTML = `<span class="material-symbols-outlined ms-12">open_in_new</span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s)}</span>`;
      srcList.appendChild(a);
    });
  }
}

document.getElementById("save-btn").addEventListener("click", () => {
  chrome.storage.local.get(["savedClaims", "detailData"], d => {
    if (!d.detailData) return;
    const claims = d.savedClaims || [];
    claims.unshift(d.detailData);
    chrome.storage.local.set({ savedClaims: claims.slice(0, 50) });
    const btn = document.getElementById("save-btn");
    btn.querySelector(".material-symbols-outlined").textContent = "bookmark";
    btn.style.color = "var(--accent)";
  });
});
