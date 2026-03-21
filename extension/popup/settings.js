const PREF_KEYS = ["pref_autocheck", "pref_scores"];

chrome.storage.local.get(["token", "user", ...PREF_KEYS], d => {
  if (!d.token) { window.location.href = chrome.runtime.getURL("popup/login.html"); return; }

  // Profile
  if (d.user) {
    const u = d.user;
    document.getElementById("profile-name").textContent  = u.name  || "User";
    document.getElementById("profile-email").textContent = u.email || "";
    const av = document.getElementById("profile-avatar");
    if (u.picture) {
      av.innerHTML = `<img src="${u.picture}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
    } else {
      av.textContent = (u.name || u.email || "?").charAt(0).toUpperCase();
    }
  }

  // Restore toggle states (default ON if never set)
  const autocheck = d.pref_autocheck !== false;
  const scores    = d.pref_scores    !== false;
  setToggle("toggle-autocheck", autocheck);
  setToggle("toggle-scores",    scores);
});

// Version from manifest
const manifest = chrome.runtime.getManifest();
const vEl = document.getElementById("app-version");
if (vEl) vEl.textContent = manifest.version || "—";

function setToggle(id, on) {
  const el = document.getElementById(id);
  if (!el) return;
  if (on) el.classList.add("on"); else el.classList.remove("on");
}

// Toggle switches — persist state
document.getElementById("toggle-autocheck").addEventListener("click", function() {
  this.classList.toggle("on");
  chrome.storage.local.set({ pref_autocheck: this.classList.contains("on") });
});
document.getElementById("toggle-scores").addEventListener("click", function() {
  this.classList.toggle("on");
  chrome.storage.local.set({ pref_scores: this.classList.contains("on") });
});

document.getElementById("logout-btn").addEventListener("click", () => {
  chrome.storage.local.clear(() => { window.location.href = chrome.runtime.getURL("popup/login.html"); });
});

// ── Navigation ──────────────────────────────────────────────────────────────
function nav(page) { window.location.href = chrome.runtime.getURL(`popup/${page}`); }
document.getElementById("back-btn").addEventListener("click",    () => nav("popup.html"));
document.getElementById("bn-chat").addEventListener("click",      () => nav("popup.html"));
document.getElementById("bn-dashboard").addEventListener("click", () => nav("dashboard.html"));
document.getElementById("bn-saved").addEventListener("click",     () => nav("saved.html"));
document.getElementById("bn-history").addEventListener("click",   () => nav("history.html"));
document.getElementById("bn-settings").addEventListener("click",  () => nav("settings.html"));
