// API is defined in config.js (loaded before this script)

// ── Tab switching ─────────────────────────────────────────────
document.getElementById("tab-login").addEventListener("click",  () => switchTab("login"));
document.getElementById("tab-signup").addEventListener("click", () => switchTab("signup"));

function switchTab(tab) {
  document.getElementById("form-login").style.display  = tab === "login"  ? "block" : "none";
  document.getElementById("form-signup").style.display = tab === "signup" ? "block" : "none";
  document.getElementById("form-forgot").style.display = "none";
  document.getElementById("form-reset").style.display  = "none";
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

// ── Button state ──────────────────────────────────────────────
function setLoading(btnId, loading, label) {
  const btn = document.getElementById(btnId);
  btn.disabled    = loading;
  btn.textContent = loading ? "Please wait…" : label;
}

// Show a subtle "server waking up" hint after 4s of waiting
function setLoadingWithHint(btnId, loading, label) {
  const btn = document.getElementById(btnId);
  btn.disabled    = loading;
  btn.textContent = loading ? "Please wait…" : label;
  if (loading) {
    const hint = setTimeout(() => {
      if (btn.disabled) btn.textContent = "Waking up server…";
    }, 4000);
    btn._hintTimer = hint;
  } else {
    clearTimeout(btn._hintTimer);
  }
}

async function apiPost(path, body, timeoutMs = 25000) {
  const res = await apiFetch(path, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body)
  }, timeoutMs);
  const data = await readJsonSafe(res) || {};
  return { res, data };
}

// ── Login ─────────────────────────────────────────────────────
document.getElementById("login-btn").addEventListener("click", doLogin);

async function doLogin() {
  hideError();
  const email    = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  if (!email || !password) return showError("Please fill in all fields");
  setLoadingWithHint("login-btn", true, "Sign In");
  try {
    const { res, data } = await apiPost("/auth/login", { email, password }, 25000);
    if (!res.ok) return showError(data.detail || "Login failed");
    await storeAuth(data);
    window.location.href = chrome.runtime.getURL("popup/popup.html");
  } catch(e) {
    if (e.name === "AbortError") showError("Server is starting up, please try again.");
    else showError("Cannot connect to server. Is the backend running?");
  } finally {
    setLoadingWithHint("login-btn", false, "Sign In");
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
  setLoadingWithHint("signup-btn", true, "Create Account");
  try {
    const { res, data } = await apiPost("/auth/signup", { email, password, name }, 25000);
    if (!res.ok) return showError(data.detail || "Signup failed");
    await storeAuth(data);
    window.location.href = chrome.runtime.getURL("popup/popup.html");
  } catch(e) {
    if (e.name === "AbortError") showError("Server is starting up, please try again.");
    else showError("Cannot connect to server. Is the backend running?");
  } finally {
    setLoadingWithHint("signup-btn", false, "Create Account");
  }
}

// ── Google ────────────────────────────────────────────────────
document.getElementById("google-login-btn").addEventListener("click",  doGoogle);
document.getElementById("google-signup-btn").addEventListener("click", doGoogle);

async function doGoogle() {
  hideError();
  // Edge doesn't support getAuthToken — always use launchWebAuthFlow
  // which works on both Chrome and Edge
  const isEdge = navigator.userAgent.includes("Edg/");

  if (!isEdge && chrome.identity.getAuthToken) {
    chrome.identity.getAuthToken({ interactive: true }, async (accessToken) => {
      if (!chrome.runtime.lastError && accessToken) {
        await exchangeAccessToken(accessToken);
      } else {
        await googleWebAuthFlow();
      }
    });
  } else {
    await googleWebAuthFlow();
  }
}

async function googleWebAuthFlow() {
  const CLIENT_ID = "595122585703-1geqe1e5uqd0lt4emf95kel6hsa3r64c.apps.googleusercontent.com";
  const REDIRECT  = chrome.identity.getRedirectURL("oauth2");
  const authURL   = "https://accounts.google.com/o/oauth2/auth" +
    `?client_id=${encodeURIComponent(CLIENT_ID)}` +
    `&response_type=token` +
    `&redirect_uri=${encodeURIComponent(REDIRECT)}` +
    `&scope=${encodeURIComponent("openid email profile")}`;

  chrome.identity.launchWebAuthFlow({ url: authURL, interactive: true }, async (responseUrl) => {
    if (chrome.runtime.lastError || !responseUrl) {
      showError(chrome.runtime.lastError?.message || "Google sign-in cancelled");
      return;
    }
    // Extract access_token from the redirect URL fragment
    const params = new URLSearchParams(new URL(responseUrl).hash.slice(1));
    const accessToken = params.get("access_token");
    if (!accessToken) { showError("Google sign-in failed: no token returned"); return; }
    await exchangeAccessToken(accessToken);
  });
}

async function exchangeAccessToken(accessToken) {
  try {
    // Show waking hint after 4s — Render cold start can take 30-60s
    const btn = document.querySelector("#google-login-btn, #google-signup-btn");
    let hintTimer;
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Signing in…";
      hintTimer = setTimeout(() => { btn.textContent = "Waking up server…"; }, 4000);
    }
    const { res, data } = await apiPost("/auth/google", { access_token: accessToken }, 60000);
    clearTimeout(hintTimer);
    if (btn) { btn.disabled = false; btn.textContent = "Continue with Google"; }
    if (!res.ok) return showError(data.detail || "Google sign-in failed");
    await storeAuth(data);
    window.location.href = chrome.runtime.getURL("popup/popup.html");
  } catch(e) {
    const btn = document.querySelector("#google-login-btn, #google-signup-btn");
    if (btn) { btn.disabled = false; btn.textContent = "Continue with Google"; }
    if (e.name === "AbortError") showError("Server is starting up — please try again in a moment.");
    else showError("Google sign-in failed: " + e.message);
  }
}

// ── Helpers ───────────────────────────────────────────────────
function storeAuth(data) {
  return new Promise(resolve => {
    chrome.storage.local.set({ token: data.token, user: data.user }, resolve);
  });
}

// Redirect if already logged in
chrome.storage.local.get(["token"], d => {
  if (d.token) window.location.href = chrome.runtime.getURL("popup/popup.html");
});

// Pre-warm Google token silently so clicking the button is instant
if (chrome.identity && chrome.identity.getAuthToken) {
  chrome.identity.getAuthToken({ interactive: false }, () => {
    // silent — just warms the cache, ignore result and errors
    void chrome.runtime.lastError;
  });
}

// Enter key
document.addEventListener("keydown", e => {
  if (e.key !== "Enter") return;
  const loginVisible  = document.getElementById("form-login").style.display  !== "none";
  const signupVisible = document.getElementById("form-signup").style.display !== "none";
  const forgotVisible = document.getElementById("form-forgot").style.display !== "none";
  const resetVisible  = document.getElementById("form-reset").style.display  !== "none";
  if (loginVisible)  doLogin();
  else if (signupVisible) doSignup();
  else if (forgotVisible) doSendOTP();
  else if (resetVisible)  doResetPassword();
});

// ── Forgot Password ───────────────────────────────────────────
let _forgotEmail = "";
let _resendTimer = null;

document.getElementById("forgot-btn").addEventListener("click", () => {
  hideError();
  document.getElementById("form-login").style.display  = "none";
  document.getElementById("form-signup").style.display = "none";
  document.getElementById("form-forgot").style.display = "block";
  document.getElementById("form-reset").style.display  = "none";
});

document.getElementById("back-to-login-btn").addEventListener("click", () => switchTab("login"));

document.getElementById("send-otp-btn").addEventListener("click", doSendOTP);

async function doSendOTP() {
  hideError();
  const email = document.getElementById("forgot-email").value.trim();
  if (!email) return showError("Please enter your email");
  setLoading("send-otp-btn", true, "Send Code");
  try {
    const { res, data } = await apiPost("/auth/forgot-password", { email }, 20000);
    if (res.status === 429) return showError(data.detail || "Too many requests. Wait a few minutes.");
    if (!res.ok) return showError(data.detail || "Failed to send code");
    _forgotEmail = email;    document.getElementById("form-forgot").style.display = "none";
    document.getElementById("form-reset").style.display  = "block";
    showSuccess("Code sent! Check your inbox.");
    startResendTimer(60);
  } catch(e) {
    if (e.name === "AbortError") {
      showError("Request timed out. The server may be starting up — try again in a moment.");
    } else {
      showError("Cannot connect to server.");
    }
  } finally {
    setLoading("send-otp-btn", false, "Send Code");
  }
}

function startResendTimer(seconds) {
  clearInterval(_resendTimer);
  const timerText = document.getElementById("resend-timer-text");
  const countdown = document.getElementById("resend-countdown");
  const resendBtn = document.getElementById("resend-otp-btn");

  timerText.style.display = "inline";
  resendBtn.style.display = "none";
  countdown.textContent = seconds;

  let remaining = seconds;
  _resendTimer = setInterval(() => {
    remaining--;
    countdown.textContent = remaining;
    if (remaining <= 0) {
      clearInterval(_resendTimer);
      timerText.style.display = "none";
      resendBtn.style.display = "inline";
    }
  }, 1000);
}

document.getElementById("resend-otp-btn").addEventListener("click", async () => {
  if (!_forgotEmail) {
    document.getElementById("form-reset").style.display  = "none";
    document.getElementById("form-forgot").style.display = "block";
    return;
  }
  hideError();
  document.getElementById("resend-otp-btn").style.display = "none";
  try {
    const { res, data } = await apiPost("/auth/forgot-password", { email: _forgotEmail }, 20000);
    if (!res.ok) {
      showError(res.status === 429 ? "Too many requests. Wait a few minutes." : (data.detail || "Failed to resend."));
      document.getElementById("resend-otp-btn").style.display = "inline";
      return;
    }
    showSuccess("New code sent!");
    startResendTimer(60);
  } catch(e) {
    showError("Failed to resend.");
    document.getElementById("resend-otp-btn").style.display = "inline";
  }
});

document.getElementById("reset-btn").addEventListener("click", doResetPassword);
document.getElementById("back-to-login-from-reset-btn").addEventListener("click", () => {
  clearInterval(_resendTimer);
  switchTab("login");
});

async function doResetPassword() {
  hideError();
  const otp         = document.getElementById("reset-otp").value.trim();
  const newPassword = document.getElementById("reset-password").value;
  if (!otp || otp.length !== 6) return showError("Enter the 6-digit code");
  if (!newPassword || newPassword.length < 6) return showError("Password must be at least 6 characters");
  setLoading("reset-btn", true, "Reset Password");
  try {
    const { res, data } = await apiPost("/auth/reset-password", { email: _forgotEmail, otp, new_password: newPassword }, 25000);
    if (!res.ok) return showError(data.detail || "Reset failed");
    showSuccess("Password reset! Signing you in…");
    // Auto-login with new password
    setTimeout(async () => {
      const { res: loginRes, data: loginData } = await apiPost("/auth/login", { email: _forgotEmail, password: newPassword }, 25000);
      if (loginRes.ok) {
        await storeAuth(loginData);
        window.location.href = chrome.runtime.getURL("popup/popup.html");
      } else {
        switchTab("login");
      }
    }, 1200);
  } catch(e) {
    showError("Cannot connect to server.");
  } finally {
    setLoading("reset-btn", false, "Reset Password");
  }
}

function showSuccess(msg) {
  const el = document.getElementById("error-box");
  el.textContent = msg;
  el.style.display = "block";
  el.style.background = "rgba(110,231,183,0.07)";
  el.style.borderColor = "rgba(110,231,183,0.25)";
  el.style.color = "var(--real)";
}

function hideError() {
  const el = document.getElementById("error-box");
  el.style.display = "none";
  el.style.background = "";
  el.style.borderColor = "";
  el.style.color = "";
}
