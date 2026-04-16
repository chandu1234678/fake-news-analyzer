/**
 * Enhanced Service Worker with Local Inference Support
 * Combines existing functionality with browser-side ONNX inference
 */

// Import local inference (will be added via importScripts)
// importScripts('onnx_inference.js');

const API = "http://127.0.0.1:8000";
const LOCAL_INFERENCE_ENABLED = true; // Toggle for local inference
const INFERENCE_TIMEOUT = 500; // 500ms timeout for local inference

// ── Keep-alive ping every 4 minutes to prevent Render free tier sleep ─────────
function pingBackend() {
  fetch(`${API}/health`, { method: "HEAD" }).catch(() => {});
}

// Ping on startup
pingBackend();

// Ping every 4 minutes (Render sleeps after 15 min of inactivity)
setInterval(pingBackend, 4 * 60 * 1000);

// ── Local Inference Initialization ────────────────────────────────────────────
let localInferenceReady = false;

async function initializeLocalInference() {
  if (!LOCAL_INFERENCE_ENABLED) {
    console.log('[ServiceWorker] Local inference disabled');
    return;
  }
  
  try {
    console.log('[ServiceWorker] Initializing local inference...');
    
    // Check if onnx_inference.js is loaded
    if (typeof localInference === 'undefined') {
      console.warn('[ServiceWorker] Local inference module not loaded');
      return;
    }
    
    await localInference.initialize();
    localInferenceReady = true;
    console.log('[ServiceWorker] ✓ Local inference ready');
    
    // Store status
    await chrome.storage.local.set({ localInferenceReady: true });
    
  } catch (error) {
    console.error('[ServiceWorker] Local inference initialization failed:', error);
    localInferenceReady = false;
    await chrome.storage.local.set({ localInferenceReady: false });
  }
}

// ── Context menu ──────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(async () => {
  chrome.contextMenus.create({
    id: "analyze-fake-news",
    title: "🔍 TruthScan this",
    contexts: ["selection"]
  });
  
  // Schedule periodic alarm for keep-alive (more reliable than setInterval in MV3)
  chrome.alarms.create("keepAlive", { periodInMinutes: 4 });
  
  // Initialize local inference
  await initializeLocalInference();
  
  // Set default settings
  await chrome.storage.local.set({
    useLocalInference: true,
    fallbackToBackend: true,
    cacheResults: true
  });
});

// Alarm-based keep-alive (MV3 service workers can be suspended)
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "keepAlive") pingBackend();
});

// Handle Context Menu Click
chrome.contextMenus.onClicked.addListener((info, _tab) => {
  if (info.menuItemId === "analyze-fake-news") {
    const text = info.selectionText;
    chrome.storage.local.set({ selectedText: text, pendingAnalysis: true }, () => {
      chrome.windows.getCurrent(win => {
        const width  = 440;
        const height = 640;
        const left   = (win.left + win.width) - width - 20;
        const top    = win.top + 60;
        chrome.windows.create({
          url: chrome.runtime.getURL("popup/popup.html"),
          type: "popup",
          width, height, left, top,
          focused: true
        });
      });
    });
  }
});

// ── Enhanced Message Handler with Local Inference ─────────────────────────────
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  // Existing handlers
  if (message.type === "TEXT_SELECTED") {
    chrome.storage.local.set({ selectedText: message.payload });
    return true;
  }
  
  if (message.type === "OPEN_POPUP_WITH_TEXT") {
    chrome.storage.local.set({ selectedText: message.text, pendingAnalysis: true }, () => {
      chrome.windows.getCurrent(win => {
        const width  = 440;
        const height = 640;
        const left   = (win.left + win.width) - width - 20;
        const top    = win.top + 60;
        chrome.windows.create({
          url: chrome.runtime.getURL("popup/popup.html"),
          type: "popup",
          width, height, left, top,
          focused: true
        });
      });
    });
    return true;
  }
  
  // New: Direct analysis request
  if (message.type === "ANALYZE_TEXT" || message.action === "analyze") {
    handleAnalysis(message.text || message.payload, message.options || {})
      .then(result => sendResponse({ success: true, ...result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // Async response
  }
  
  // New: Get model info
  if (message.type === "GET_MODEL_INFO") {
    const info = {
      localInferenceReady,
      localInferenceEnabled: LOCAL_INFERENCE_ENABLED
    };
    
    if (typeof localInference !== 'undefined') {
      Object.assign(info, localInference.getInfo());
    }
    
    sendResponse({ success: true, info });
    return false;
  }
  
  // New: Clear cache
  if (message.type === "CLEAR_CACHE") {
    clearAnalysisCache()
      .then(() => sendResponse({ success: true }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
  
  return true;
});

/**
 * Main analysis handler with local inference + fallback
 */
async function handleAnalysis(text, options = {}) {
  const startTime = performance.now();
  
  // Check cache first
  if (options.useCache !== false) {
    const cached = await getFromCache(text);
    if (cached) {
      console.log('[ServiceWorker] ✓ Cache hit');
      return {
        ...cached,
        cached: true,
        total_time_ms: performance.now() - startTime
      };
    }
  }
  
  // Get settings
  const settings = await chrome.storage.local.get([
    'useLocalInference',
    'fallbackToBackend'
  ]);
  
  const useLocal = settings.useLocalInference !== false;
  const useFallback = settings.fallbackToBackend !== false;
  
  let result = null;
  let method = null;
  
  // Try local inference first
  if (useLocal && localInferenceReady && typeof localInference !== 'undefined') {
    try {
      console.log('[ServiceWorker] Trying local inference...');
      
      // Run with timeout
      result = await Promise.race([
        localInference.predict(text),
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Local inference timeout')), 
          INFERENCE_TIMEOUT)
        )
      ]);
      
      method = 'local';
      console.log(`[ServiceWorker] ✓ Local inference: ${result.inference_time_ms.toFixed(0)}ms`);
      
    } catch (error) {
      console.warn('[ServiceWorker] Local inference failed:', error.message);
      
      if (!useFallback) {
        throw error;
      }
    }
  }
  
  // Fallback to backend API
  if (!result && useFallback) {
    try {
      console.log('[ServiceWorker] Using backend API...');
      result = await backendAnalysis(text);
      method = 'backend';
      console.log('[ServiceWorker] ✓ Backend analysis complete');
      
    } catch (error) {
      console.error('[ServiceWorker] Backend analysis failed:', error);
      throw new Error('Both local and backend analysis failed');
    }
  }
  
  if (!result) {
    throw new Error('No analysis method available');
  }
  
  // Add metadata
  result.method = method;
  result.total_time_ms = performance.now() - startTime;
  result.timestamp = Date.now();
  
  // Cache result
  if (options.useCache !== false) {
    await saveToCache(text, result);
  }
  
  return result;
}

/**
 * Backend API analysis
 */
async function backendAnalysis(text) {
  const response = await fetch(`${API}/message`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ message: text })
  });
  
  if (!response.ok) {
    throw new Error(`Backend API error: ${response.status}`);
  }
  
  const data = await response.json();
  
  return {
    verdict: data.verdict,
    confidence: data.confidence,
    fake_probability: data.ml_score || 0,
    explanation: data.explanation,
    evidence: data.evidence || [],
    is_claim: data.is_claim,
    source: 'backend'
  };
}

/**
 * Cache management
 */
const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours
const MAX_CACHE_SIZE = 100;

async function getFromCache(text) {
  const key = hashText(text);
  const cache = await chrome.storage.local.get(['analysisCache']);
  const cached = cache.analysisCache?.[key];
  
  if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
    return cached;
  }
  
  return null;
}

async function saveToCache(text, result) {
  const key = hashText(text);
  const cache = await chrome.storage.local.get(['analysisCache']);
  const analysisCache = cache.analysisCache || {};
  
  // Limit cache size
  const keys = Object.keys(analysisCache);
  if (keys.length >= MAX_CACHE_SIZE) {
    // Remove oldest entry
    const oldest = keys.reduce((a, b) => 
      analysisCache[a].timestamp < analysisCache[b].timestamp ? a : b
    );
    delete analysisCache[oldest];
  }
  
  analysisCache[key] = result;
  await chrome.storage.local.set({ analysisCache });
}

async function clearAnalysisCache() {
  await chrome.storage.local.set({ analysisCache: {} });
  console.log('[ServiceWorker] Cache cleared');
}

function hashText(text) {
  // Simple hash function
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return hash.toString(36);
}

console.log('[ServiceWorker] Enhanced service worker loaded');
console.log(`[ServiceWorker] Local inference: ${LOCAL_INFERENCE_ENABLED ? 'enabled' : 'disabled'}`);
