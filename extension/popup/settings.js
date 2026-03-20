chrome.storage.local.get(["token", "user"], d => {
  if (!d.token) { window.location.href = chrome.runtime.getURL("popup/login.html"); return; }
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
});

document.getElementById("logout-btn").addEventListener("click", () => {
  chrome.storage.local.clear(() => { window.location.href = chrome.runtime.getURL("popup/login.html"); });
});


// Toggle switches
["toggle-autocheck", "toggle-scores"].forEach(id => {
  document.getElementById(id).addEventListener("click", function() {
    this.classList.toggle("on");
  });
});

// ── Navigation ──────────────────────────────────────────────────────────────
function nav(page) { window.location.href = chrome.runtime.getURL(`popup/${page}`); }
document.getElementById("back-btn").addEventListener("click",    () => nav("popup.html"));
document.getElementById("bn-chat").addEventListener("click",      () => nav("popup.html"));
document.getElementById("bn-dashboard").addEventListener("click", () => nav("dashboard.html"));
document.getElementById("bn-saved").addEventListener("click",     () => nav("saved.html"));
document.getElementById("bn-history").addEventListener("click",   () => nav("history.html"));
document.getElementById("bn-settings").addEventListener("click",  () => nav("settings.html"));
