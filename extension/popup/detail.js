function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function feedbackClaimText(data) {
  return data.primary_claim || data.content || data.explanation || "";
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
  const newsPct = data.evidence_score != null
    ? Math.round(data.evidence_score * 100)
    : (data.evidence_articles?.length || data.evidence?.length) ? 60 : 0;
  const mlFill   = mlPct > 50 ? "fill-fake" : "fill-real";
  const newsFill = newsPct > 50 ? "fill-real" : "fill-fake";
  const confColor = v === "real" ? "var(--real)" : v === "fake" ? "var(--fake)" : "var(--warn)";

  const content = document.getElementById("detail-content");
  content.innerHTML = "";

  // ── Verdict banner ────────────────────────────────────────
  const banner = document.createElement("div");
  banner.className = "card";
  banner.innerHTML = `
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px">
      <span class="material-symbols-outlined ms-24 ${vClass}">${vIcon}</span>
      <div>
        <div style="font-size:16px;font-weight:700;text-transform:uppercase" class="${vClass}">${v}</div>
        <div style="font-size:11px;color:var(--t3)">${confPct}% confidence</div>
      </div>
    </div>
    <div class="verdict-conf-bar" style="height:5px;border-radius:3px;background:var(--bg3);overflow:hidden">
      <div style="height:100%;width:${confPct}%;background:${confColor};border-radius:3px;transition:width .4s"></div>
    </div>
    ${data.verdict_changed ? `<div class="verdict-changed-note" style="margin-top:8px">⚠️ This claim's verdict has changed since it was last checked.</div>` : ""}
    ${v === "uncertain" ? `<div class="uncertain-note" style="margin-top:8px">Signals conflict or evidence is insufficient for a definitive verdict.</div>` : ""}`;
  content.appendChild(banner);

  // ── Moderation summary ───────────────────────────────────
  if (data.moderation_summary) {
    const mod = data.moderation_summary;
    const riskPct = Math.round((mod.risk || 0) * 100);
    const rec = (mod.recommendation || "allow").toLowerCase();
    const recLabel = rec === "review" ? "REVIEW" : "ALLOW";
    const recCls = rec === "review" ? "mod-review" : "mod-allow";
    const flags = Array.isArray(mod.flags) ? mod.flags.slice(0, 4).join(" · ") : "";
    const modEl = document.createElement("div");
    modEl.className = `card mod-summary ${recCls}`;
    modEl.innerHTML = `
      <div class="mod-row">
        <span class="material-symbols-outlined ms-12">policy</span>
        <span class="mod-label">Moderation: ${recLabel}</span>
        <span class="mod-risk">${riskPct}%</span>
      </div>
      <div class="mod-risk-bar"><div class="mod-risk-fill" style="width:${riskPct}%"></div></div>
      ${flags ? `<div class="mod-flags">${esc(flags)}</div>` : ""}`;
    content.appendChild(modEl);
  }

  // ── Claim text ────────────────────────────────────────────
  const claimText = data.content || data.explanation || "";
  if (claimText) {
    const claimEl = document.createElement("div");
    claimEl.className = "card";
    claimEl.innerHTML = `
      <div class="card-title">Claim</div>
      <div style="font-size:13px;color:var(--t1);line-height:1.6">${esc(claimText)}</div>`;
    content.appendChild(claimEl);
  }

  // ── Manipulation badge ────────────────────────────────────
  if (data.manipulation_score > 0.15 && data.manipulation_signals?.length) {
    const level = data.manipulation_score >= 0.5 ? "HIGH" : "MED";
    const cls   = data.manipulation_score >= 0.5 ? "manip-high" : "manip-med";
    const tags  = data.manipulation_signals.slice(0, 4).join(" · ");
    const manip = document.createElement("div");
    manip.className = `card manip-badge ${cls}`;
    manip.innerHTML = `
      <span class="material-symbols-outlined ms-12">warning</span>
      Manipulation signals (${level}): ${esc(tags)}`;
    content.appendChild(manip);
  }

  // ── Highlighted suspicious phrases ────────────────────────
  if (data.highlights?.length) {
    const hlEl = document.createElement("div");
    hlEl.className = "card";
    const tags = data.highlights.map(h => {
      const cls = h.score >= 0.75 ? "hl-high" : h.score >= 0.5 ? "hl-med" : "hl-low";
      const tip = h.reason === "sensational" ? "Sensational language"
                : h.reason === "emotional"   ? "Emotional language"
                : h.reason === "absolute_claim" ? "Absolute claim"
                : "ML signal";
      return `<span class="hl-tag ${cls}" title="${tip}">${esc(h.phrase)}</span>`;
    }).join("");
    hlEl.innerHTML = `
      <div class="card-title" style="display:flex;align-items:center;gap:4px">
        <span class="material-symbols-outlined ms-12">flag</span>
        Suspicious phrases
      </div>
      <div class="hl-tags">${tags}</div>`;
    content.appendChild(hlEl);
  }

  // ── Analysis scores ───────────────────────────────────────
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
      <div>
        <div style="display:flex;justify-content:space-between;margin-bottom:5px">
          <span style="font-size:11px;color:var(--t3)">News Evidence</span>
          <span style="font-size:11px;font-weight:600;color:var(--t1)">${newsPct}%</span>
        </div>
        <div class="score-track" style="height:5px"><div class="score-fill ${newsFill} news-bar"></div></div>
      </div>
    </div>`;
  content.appendChild(scoresEl);
  scoresEl.querySelector(".ml-bar").style.width   = `${mlPct}%`;
  scoresEl.querySelector(".ai-bar").style.width   = `${aiPct}%`;
  scoresEl.querySelector(".news-bar").style.width = `${newsPct}%`;

  // ── Contradiction meter ───────────────────────────────────
  const ss = data.stance_summary;
  if (ss && (ss.support + ss.contradict + ss.neutral) > 0) {
    const total  = ss.support + ss.contradict + ss.neutral;
    const supPct = Math.round((ss.support    / total) * 100);
    const conPct = Math.round((ss.contradict / total) * 100);
    const neuPct = 100 - supPct - conPct;
    const label  = ss.contradict > ss.support ? "⚠️ Sources conflict"
                 : ss.support > 0 ? "✓ Sources agree" : "Sources neutral";
    const stanceEl = document.createElement("div");
    stanceEl.className = "card";
    stanceEl.innerHTML = `
      <div class="card-title">Source Consensus</div>
      <div class="stance-meter">
        <div class="stance-label">${label}</div>
        <div class="stance-bar">
          <div class="stance-seg stance-sup" style="width:${supPct}%" title="Support: ${ss.support}"></div>
          <div class="stance-seg stance-neu" style="width:${neuPct}%" title="Neutral: ${ss.neutral}"></div>
          <div class="stance-seg stance-con" style="width:${conPct}%" title="Contradict: ${ss.contradict}"></div>
        </div>
        <div class="stance-counts">
          <span class="stance-sup-txt">${ss.support} support</span>
          <span class="stance-neu-txt">${ss.neutral} neutral</span>
          <span class="stance-con-txt">${ss.contradict} conflict</span>
        </div>
      </div>`;
    content.appendChild(stanceEl);
  }

  // ── AI Explanation ────────────────────────────────────────
  if (data.explanation) {
    const explEl = document.createElement("div");
    explEl.className = "card";
    explEl.innerHTML = `
      <div class="card-title">AI Explanation</div>
      <div style="font-size:12.5px;color:var(--t2);line-height:1.65">${esc(data.explanation)}</div>`;
    content.appendChild(explEl);
  }

  // ── Sub-claims ────────────────────────────────────────────
  if (data.sub_claims?.length > 1) {
    const scEl = document.createElement("div");
    scEl.className = "card";
    const items = data.sub_claims.map((c, i) =>
      `<div class="subclaim-item"><span class="subclaim-num">${i+1}</span>${esc(c)}</div>`
    ).join("");
    scEl.innerHTML = `
      <div class="card-title">Extracted Claims</div>
      ${items}
      <div class="subclaim-note">Verdict based on: "${esc(data.primary_claim)}"</div>`;
    content.appendChild(scEl);
  }

  // ── Evidence articles ─────────────────────────────────────
  const hasArticles = data.evidence_articles?.length;
  const hasUrls     = data.evidence?.length;
  if (hasArticles || hasUrls) {
    const srcEl = document.createElement("div");
    srcEl.className = "card";
    srcEl.innerHTML = `
      <div class="card-title" style="display:flex;align-items:center;gap:4px">
        <span class="material-symbols-outlined ms-12">newspaper</span>
        News Evidence
      </div>
      <div id="sources-list"></div>`;
    content.appendChild(srcEl);
    const srcList = srcEl.querySelector("#sources-list");

    if (hasArticles) {
      data.evidence_articles.slice(0, 5).forEach(a => {
        const stanceCls = a.stance === "support" ? "stance-sup-txt"
                        : a.stance === "contradict" ? "stance-con-txt" : "stance-neu-txt";
        const stanceLabel = a.stance === "support" ? "✓ supports"
                          : a.stance === "contradict" ? "✗ contradicts" : "· neutral";
        const trustLabel = a.trust_label || "MED";
        const trustCls   = trustLabel === "HIGH" ? "cred-high" : trustLabel === "LOW" ? "cred-low" : "cred-med";
        const el = document.createElement("a");
        el.href = a.url;
        el.target = "_blank";
        el.style.cssText = "display:flex;flex-direction:column;gap:3px;padding:8px 10px;border-radius:7px;border:1px solid var(--border);margin-bottom:6px;text-decoration:none;transition:background 0.15s;";
        el.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:space-between;gap:6px">
            <span style="font-size:10px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:0.04em">${esc(a.source)}</span>
            <div style="display:flex;gap:4px;align-items:center">
              <span class="src-cred ${trustCls}">${trustLabel}</span>
              <span style="font-size:9px" class="${stanceCls}">${stanceLabel}</span>
            </div>
          </div>
          <span style="font-size:11.5px;color:var(--t2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(a.title)}</span>`;
        el.addEventListener("mouseover", () => el.style.background = "var(--bg3)");
        el.addEventListener("mouseout",  () => el.style.background = "");
        srcList.appendChild(el);
      });
    } else {
      data.evidence.slice(0, 5).forEach(s => {
        const a = document.createElement("a");
        a.href = s; a.target = "_blank";
        a.style.cssText = "display:flex;align-items:center;gap:6px;font-size:12px;color:var(--accent);text-decoration:none;margin-bottom:5px;overflow:hidden";
        a.innerHTML = `<span class="material-symbols-outlined ms-12">open_in_new</span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s)}</span>`;
        srcList.appendChild(a);
      });
    }
  }
}

document.getElementById("save-btn").addEventListener("click", () => {
  chrome.storage.local.get(["savedClaims", "detailData"], d => {
    if (!d.detailData) return;
    const claims = d.savedClaims || [];
    const key = d.detailData.content || d.detailData.explanation || "";
    if (claims.some(c => (c.content || c.explanation || "") === key)) {
      const btn = document.getElementById("save-btn");
      btn.querySelector(".material-symbols-outlined").textContent = "bookmark";
      btn.style.color = "var(--t3)";
      return;
    }
    claims.unshift(d.detailData);
    chrome.storage.local.set({ savedClaims: claims.slice(0, 50) });
    const btn = document.getElementById("save-btn");
    btn.querySelector(".material-symbols-outlined").textContent = "bookmark";
    btn.style.color = "var(--accent)";
  });
});

// ── Feedback button ───────────────────────────────────────────
document.getElementById("feedback-btn").addEventListener("click", () => {
  chrome.storage.local.get(["detailData", "token"], async d => {
    if (!d.detailData) return;
    const data = d.detailData;
    const current = (data.verdict || "uncertain").toLowerCase();
    const correct = current === "fake" ? "real" : "fake";
    const btn = document.getElementById("feedback-btn");
    btn.disabled = true;
    btn.querySelector(".material-symbols-outlined").textContent = "flag";
    btn.style.color = "var(--warn)";
    try {
      await apiFetch("/feedback", {
        method: "POST",
        headers: buildHeaders({
          "Content-Type": "application/json",
          "Authorization": `Bearer ${d.token}`
        }),
        body: JSON.stringify({
          claim_text: feedbackClaimText(data),
          predicted:  current,
          actual:     correct,
          confidence: data.confidence || null,
        })
      });
      btn.querySelector(".material-symbols-outlined").textContent = "flag_circle";
      btn.style.color = "var(--real)";
      btn.title = "Feedback recorded";
    } catch(e) {
      btn.disabled = false;
      btn.style.color = "";
    }
  });
});
