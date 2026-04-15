// ── Backend API URL ───────────────────────────────────────────
const API = "https://fake-news-analyzer-j6ka.onrender.com";

const API_TIMEOUT_MS = 20000;
const CLIENT_NAME = "edge-extension";
const CLIENT_VERSION = (chrome?.runtime?.getManifest?.().version) || "unknown";

function buildHeaders(extra = {}) {
	return {
		"X-Client": CLIENT_NAME,
		"X-Client-Version": CLIENT_VERSION,
		...extra,
	};
}

async function apiFetch(path, opts = {}, timeoutMs = API_TIMEOUT_MS) {
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), timeoutMs);
	const url = path.startsWith("http") ? path : `${API}${path}`;
	try {
		return await fetch(url, { ...opts, signal: controller.signal });
	} finally {
		clearTimeout(timer);
	}
}

async function readJsonSafe(res) {
	try {
		return await res.json();
	} catch (_) {
		return null;
	}
}
