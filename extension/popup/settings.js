chrome.storage.local.get(["token", "user"], d => {
  if (!d.token) { window.location.href = "login.html"; return; }
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
  chrome.storage.local.clear(() => { window.location.href = "login.html"; });
});

document.getElementById("test-btn").addEventListener("click", async () => {
  const url    = document.getElementById("api-url").value.trim();
  const status = document.getElementById("conn-status");
  status.textContent = "Testing...";
  status.style.color = "var(--t3)";
  try {
    const res  = await fetch(`${url}/health`);
    const data = await res.json();
    if (data.status === "ok") {
      status.textContent = "✓ Connected";
      status.style.color = "var(--real)";
    } else {
      status.textContent = "⚠ Unexpected response";
      status.style.color = "var(--warn)";
    }
  } catch(_) {
    status.textContent = "✗ Cannot connect — is the backend running?";
    status.style.color = "var(--fake)";
  }
});

// Toggle switches
["toggle-autocheck", "toggle-scores"].forEach(id => {
  document.getElementById(id).addEventListener("click", function() {
    this.classList.toggle("on");
  });
});
