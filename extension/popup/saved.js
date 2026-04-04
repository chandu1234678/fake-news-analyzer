function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

chrome.storage.local.get(["token", "savedClaims"], d => {
  if (!d.token) { window.location.href = chrome.runtime.getURL("popup/login.html"); return; }
  render(d.savedClaims || []);
});

function render(claims) {
  const list = document.getElementById("saved-list");
  list.innerHTML = "";
  if (!claims.length) {
    list.innerHTML = `
      <div style="text-align:center;padding:40px 0">
        <span class="material-symbols-outlined ms-24" style="color:var(--t3)">bookmark_border</span>
        <div style="font-size:12px;color:var(--t3);margin-top:8px">No saved claims yet</div>
        <div style="font-size:12px;color:var(--t3);margin-top:3px">Fact-check a claim and save it here</div>
      </div>`;
    return;
  }
  claims.forEach((c, i) => {
    const v      = (c.verdict || "uncertain").toLowerCase();
    const vClass = v === "real" ? "v-real" : v === "fake" ? "v-fake" : "v-uncertain";
    const vIcon  = v === "real" ? "check_circle" : v === "fake" ? "cancel" : "help";
    const el     = document.createElement("div");
    el.className = "list-item";
    const confPct = Math.round((c.confidence || 0) * 100);
    const hasManip = c.manipulation_score > 0.15 && c.manipulation_signals?.length;
    const manipBadge = hasManip
      ? `<span class="manip-badge ${c.manipulation_score >= 0.5 ? 'manip-high' : 'manip-med'}" style="margin-top:5px;font-size:9px;padding:2px 6px">
           <span class="material-symbols-outlined ms-10">warning</span>
           ${c.manipulation_score >= 0.5 ? 'HIGH' : 'MED'} manipulation
         </span>` : "";
    const hlTags = c.highlights?.length
      ? c.highlights.slice(0, 3).map(h =>
          `<span class="hl-tag ${h.score >= 0.75 ? 'hl-high' : 'hl-med'}">${esc(h.phrase)}</span>`
        ).join("") : "";

    el.innerHTML = `
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:8px">
        <div style="font-size:12.5px;color:var(--t1);line-height:1.55;flex:1">${esc(c.content || c.explanation || "")}</div>
        <button class="icon-btn unsave-btn" style="flex-shrink:0;margin-top:-2px">
          <span class="material-symbols-outlined ms-14">bookmark_remove</span>
        </button>
      </div>
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
        <span class="material-symbols-outlined ms-14 ${vClass}">${vIcon}</span>
        <span style="font-size:11px;font-weight:600;text-transform:uppercase" class="${vClass}">${v}</span>
        <span style="font-size:11px;color:var(--t3);margin-left:auto">${confPct}% confidence</span>
      </div>
      ${manipBadge}
      ${hlTags ? `<div class="hl-tags" style="margin-top:5px">${hlTags}</div>` : ""}`;
    el.style.cursor = "pointer";
    el.addEventListener("click", e => {
      if (e.target.closest(".unsave-btn")) return;
      chrome.storage.local.set({ detailData: c }, () => nav("detail.html"));
    });
    el.querySelector(".unsave-btn").addEventListener("click", () => unsave(i));
    list.appendChild(el);
  });
}

function unsave(index) {
  chrome.storage.local.get("savedClaims", d => {
    const claims = d.savedClaims || [];
    claims.splice(index, 1);
    chrome.storage.local.set({ savedClaims: claims }, () => render(claims));
  });
}

// ── Navigation ──────────────────────────────────────────────────────────────
function nav(page) { window.location.href = chrome.runtime.getURL(`popup/${page}`); }
document.getElementById("back-btn").addEventListener("click",    () => nav("popup.html"));
document.getElementById("bn-chat").addEventListener("click",      () => nav("popup.html"));
document.getElementById("bn-dashboard").addEventListener("click", () => nav("dashboard.html"));
document.getElementById("bn-saved").addEventListener("click",     () => nav("saved.html"));
document.getElementById("bn-history").addEventListener("click",   () => nav("history.html"));
document.getElementById("bn-settings").addEventListener("click",  () => nav("settings.html"));
