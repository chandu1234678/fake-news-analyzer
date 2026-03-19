// API is defined in config.js (loaded before this script)

// ── Tab switching ─────────────────────────────────────────────
document.getElementById("tab-login").addEventListener("click",  () => switchTab("login"));
document.getElementById("tab-signup").addEventListener("click", () => switchTab("signup"));

function switchTab(tab) {
  document.getElementById("form-login").style.display  = tab === "login"  ? "block" : "none";
  document.getElementById("form-signup").style.display = tab === "signup" ? "block" : "none";
  document.getElementById("tab-login").className  = "login-tab" + (tab === "login"  ? " active" : "");
  document.getElementById("tab-signup").className = "login-tab" + (tab === "signup" ? " active" : "");
  hideError();
}

// ── Error helpers ─────────────────────────────────────────────
function showError(msg) {
  const el = document.getElementById("error-box");
  el.textContent = msg;
  el.style.display = "block";
}
function hideError() {
  const el = document.getElementById("error-box");
  el.style.display = "none";
}

// ── Button state ──────────────────────────────────────────────
function setLoading(btnId, loading, label) {
  const btn = document.getElementById(btnId);
  btn.disabled    = loading;
  btn.textContent = loading ? "Please wait..." : label;
}

// ── Login ─────────────────────────────────────────────────────
document.getElementById("login-btn").addEventListener("click", doLogin);

async function doLogin() {
  hideError();
  const email    = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  if (!email || !password) return showError("Please fill in all fields");
  setLoading("login-btn", true, "Sign In");
  try {
    const res  = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) return showError(data.detail || "Login failed");
    await storeAuth(data);
    window.location.href = "popup.html";
  } catch(e) {
    showError("Cannot connect to server. Is the backend running?");
  } finally {
    setLoading("login-btn", false, "Sign In");
  }
}

// ── Signup ────────────────────────────────────────────────────
document.getElementById("signup-btn").addEventListener("click", doSignup);

async function doSignup() {
  hideError();
  const name     = document.getElementById("signup-name").value.trim();
  const email    = document.getElementById("signup-email").value.trim();
  const password = document.getElementById("signup-password").value;
  if (!email || !password) return showError("Please fill in all fields");
  if (password.length < 6) return showError("Password must be at least 6 characters");
  setLoading("signup-btn", true, "Create Account");
  try {
    const res  = await fetch(`${API}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name })
    });
    const data = await res.json();
    if (!res.ok) return showError(data.detail || "Signup failed");
    await storeAuth(data);
    window.location.href = "popup.html";
  } catch(e) {
    showError("Cannot connect to server. Is the backend running?");
  } finally {
    setLoading("signup-btn", false, "Create Account");
  }
}

// ── Google ────────────────────────────────────────────────────
document.getElementById("google-login-btn").addEventListener("click",  doGoogle);
document.getElementById("google-signup-btn").addEventListener("click", doGoogle);

async function doGoogle() {
  hideError();
  // Use Chrome Identity API — no redirect needed
  chrome.identity.getAuthToken({ interactive: true }, async (accessToken) => {
    if (chrome.runtime.lastError || !accessToken) {
      showError(chrome.runtime.lastError?.message || "Google sign-in cancelled");
      return;
    }
    // Exchange access token for user info, then get an id_token via tokeninfo
    try {
      // Get user info with the access token
      const infoRes = await fetch(
        `https://www.googleapis.com/oauth2/v3/userinfo`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      if (!infoRes.ok) throw new Error("Failed to fetch Google user info");
      const googleUser = await infoRes.json();

      // Send to our backend — we pass the access token and let backend verify via userinfo
      const res  = await fetch(`${API}/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ access_token: accessToken })
      });
      const data = await res.json();
      if (!res.ok) return showError(data.detail || "Google sign-in failed");
      await storeAuth(data);
      window.location.href = "popup.html";
    } catch(e) {
      showError("Google sign-in failed: " + e.message);
    }
  });
}

// ── Helpers ───────────────────────────────────────────────────
function storeAuth(data) {
  return new Promise(resolve => {
    chrome.storage.local.set({ token: data.token, user: data.user }, resolve);
  });
}

// Redirect if already logged in
chrome.storage.local.get(["token"], d => {
  if (d.token) window.location.href = "popup.html";
});

// Enter key
document.addEventListener("keydown", e => {
  if (e.key !== "Enter") return;
  const loginHidden = document.getElementById("form-login").classList.contains("hidden");
  if (!loginHidden) doLogin(); else doSignup();
});
