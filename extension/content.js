(() => {
  let tooltip = null;
  let hideTimer = null;

  // ── Create tooltip element once ───────────────────────────
  function createTooltip() {
    const el = document.createElement("div");
    el.id = "__factcheck_tooltip__";
    el.innerHTML = `
      <span style="font-size:13px;line-height:1;">🔍</span>
      <span style="font-size:12px;font-weight:600;letter-spacing:0.01em;">TruthScan this</span>
    `;
    Object.assign(el.style, {
      position:        "fixed",
      zIndex:          "2147483647",
      display:         "flex",
      alignItems:      "center",
      gap:             "6px",
      padding:         "7px 12px",
      background:      "#1e2228",
      color:           "#e8eaed",
      borderRadius:    "8px",
      border:          "1px solid rgba(192,193,255,0.18)",
      boxShadow:       "0 4px 16px rgba(0,0,0,0.5)",
      cursor:          "pointer",
      fontFamily:      "-apple-system, 'Inter', sans-serif",
      userSelect:      "none",
      pointerEvents:   "all",
      opacity:         "0",
      transform:       "translateY(4px)",
      transition:      "opacity 0.15s ease, transform 0.15s ease",
      whiteSpace:      "nowrap",
    });

    el.addEventListener("mouseenter", () => clearTimeout(hideTimer));
    el.addEventListener("mouseleave", () => scheduleHide(800));
    el.addEventListener("mousedown", e => {
      e.preventDefault();
      e.stopPropagation();
      const text = window.getSelection().toString().trim();
      if (text) {
        chrome.storage.local.set({ selectedText: text, pendingAnalysis: true }, () => {
          chrome.runtime.sendMessage({ type: "OPEN_POPUP_WITH_TEXT", text });
        });
      }
      removeTooltip();
    });

    document.body.appendChild(el);
    return el;
  }

  function showTooltip(x, y) {
    if (!tooltip) tooltip = createTooltip();

    // Position above the selection, centered
    const tw = 160;
    const left = Math.min(Math.max(x - tw / 2, 8), window.innerWidth - tw - 8);
    const top  = Math.max(y - 44, 8);

    tooltip.style.left    = `${left}px`;
    tooltip.style.top     = `${top}px`;
    tooltip.style.opacity = "1";
    tooltip.style.transform = "translateY(0)";
  }

  function removeTooltip() {
    if (!tooltip) return;
    tooltip.style.opacity   = "0";
    tooltip.style.transform = "translateY(4px)";
    setTimeout(() => {
      if (tooltip && tooltip.parentNode) tooltip.parentNode.removeChild(tooltip);
      tooltip = null;
    }, 150);
  }

  function scheduleHide(delay = 300) {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(removeTooltip, delay);
  }

  // ── Listen for mouseup to detect selection ────────────────
  document.addEventListener("mouseup", e => {
    // Small delay so selection is finalised
    setTimeout(() => {
      const selected = window.getSelection().toString().trim();

      if (selected.length > 20) {
        clearTimeout(hideTimer);
        showTooltip(e.clientX, e.clientY);

        // Also notify background (existing behaviour)
        chrome.runtime.sendMessage({
          type: "TEXT_SELECTED",
          payload: selected
        }).catch(() => {});
      } else {
        scheduleHide(100);
      }
    }, 10);
  });

  // Hide on click elsewhere
  document.addEventListener("mousedown", e => {
    if (tooltip && !tooltip.contains(e.target)) {
      scheduleHide(100);
    }
  });

  // Hide on scroll
  document.addEventListener("scroll", () => scheduleHide(100), { passive: true });

})();
