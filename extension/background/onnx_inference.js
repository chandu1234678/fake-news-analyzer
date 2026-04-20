/**
 * ONNX Runtime Web - Browser-Side Inference
 * 
 * Enables local fact-checking without backend dependency
 * Target: <200ms inference time, <100MB memory usage
 */

// Import ONNX Runtime Web (add to manifest.json)
// <script src="https://cdn.jsdelivr.net/npm/onnxruntime-web/dist/ort.min.js"></script>

class LocalInference {
    constructor() {
        this.session = null;
        this.tokenizer = null;
        this.modelLoaded = false;
        this.mode = 'uninitialized'; // onnx | heuristic | unavailable
        this.modelPath = 'models/model_optimized.onnx';
        this.tokenizerPath = 'models/tokenizer.json';
        this.ortRuntimePath = 'background/lib/ort.min.js';
        this.maxLength = 512;
        this.labels = ['real', 'fake'];
    }

    async ensureOrtRuntime() {
        if (typeof ort !== 'undefined' && ort.InferenceSession) return true;

        try {
            if (typeof importScripts === 'function') {
                importScripts(chrome.runtime.getURL(this.ortRuntimePath));
            }
        } catch (error) {
            console.warn('[LocalInference] ORT runtime script unavailable:', error);
        }

        return typeof ort !== 'undefined' && !!ort.InferenceSession;
    }
    
    /**
     * Initialize and load model
     * Called on extension install/update
     */
    async initialize() {
        console.log('[LocalInference] Initializing...');
        
        try {
            const ortReady = await this.ensureOrtRuntime();
            if (!ortReady) {
                console.warn('[LocalInference] ONNX runtime not found, using heuristic fallback');
                this.mode = 'heuristic';
                this.modelLoaded = true;
                return true;
            }

            await this.loadModel();
            await this.loadTokenizer();
            this.modelLoaded = true;
            this.mode = 'onnx';
            console.log('[LocalInference] ✓ Ready for inference');
            return true;
        } catch (error) {
            console.warn('[LocalInference] ONNX initialization failed, falling back to heuristic:', error);
            this.mode = 'heuristic';
            this.modelLoaded = true;
            return true;
        }
    }
    
    /**
     * Load ONNX model from cache or download
     */
    async loadModel() {
        console.log('[LocalInference] Loading model...');
        
        try {
            // Try to load from IndexedDB cache first
            let modelData = await this.getFromCache('model');
            
            if (!modelData) {
                console.log('[LocalInference] Model not cached, downloading...');
                
                // Download from extension resources
                const response = await fetch(chrome.runtime.getURL(this.modelPath));
                if (!response.ok) {
                    throw new Error(`Failed to fetch model: ${response.statusText}`);
                }
                
                modelData = await response.arrayBuffer();
                
                // Cache for future use
                await this.saveToCache('model', modelData);
                console.log('[LocalInference] Model cached');
            } else {
                console.log('[LocalInference] Model loaded from cache');
            }
            
            // Create ONNX session
            this.session = await ort.InferenceSession.create(modelData, {
                executionProviders: ['wasm'],
                graphOptimizationLevel: 'all'
            });
            
            const sizeMB = modelData.byteLength / (1024 * 1024);
            console.log(`[LocalInference] ✓ Model loaded (${sizeMB.toFixed(1)} MB)`);
            
        } catch (error) {
            console.error('[LocalInference] Model loading failed:', error);
            throw error;
        }
    }
    
    /**
     * Load tokenizer configuration
     */
    async loadTokenizer() {
        console.log('[LocalInference] Loading tokenizer...');
        
        try {
            // Load tokenizer config
            const response = await fetch(chrome.runtime.getURL(this.tokenizerPath));
            if (!response.ok) {
                throw new Error(`Failed to fetch tokenizer: ${response.statusText}`);
            }
            
            this.tokenizer = await response.json();
            console.log('[LocalInference] ✓ Tokenizer loaded');
            
        } catch (error) {
            console.error('[LocalInference] Tokenizer loading failed:', error);
            throw error;
        }
    }
    
    /**
     * Run inference on text
     * @param {string} text - Input text to classify
     * @returns {Promise<Object>} Prediction result
     */
    async predict(text) {
        if (!this.modelLoaded) {
            throw new Error('Model not loaded. Call initialize() first.');
        }

        if (this.mode === 'heuristic') {
            return this.heuristicPredict(text);
        }
        
        const startTime = performance.now();
        
        try {
            // Step 1: Tokenize input
            const tokens = this.tokenize(text);
            
            // Step 2: Create input tensors
            const inputIds = new ort.Tensor('int64', 
                BigInt64Array.from(tokens.input_ids.map(x => BigInt(x))),
                [1, tokens.input_ids.length]
            );
            
            const attentionMask = new ort.Tensor('int64',
                BigInt64Array.from(tokens.attention_mask.map(x => BigInt(x))),
                [1, tokens.attention_mask.length]
            );
            
            // Step 3: Run inference
            const feeds = {
                input_ids: inputIds,
                attention_mask: attentionMask
            };
            
            const results = await this.session.run(feeds);
            
            // Step 4: Process output
            const logits = Array.from(results.logits.data);
            const probabilities = this.softmax(logits);
            
            const fakeProb = probabilities[1];
            const verdict = fakeProb > 0.5 ? 'fake' : 'real';
            const confidence = Math.max(...probabilities);
            
            const inferenceTime = performance.now() - startTime;
            
            console.log(`[LocalInference] Prediction: ${verdict} (${(confidence * 100).toFixed(1)}%) in ${inferenceTime.toFixed(0)}ms`);
            
            return {
                verdict: verdict,
                confidence: confidence,
                fake_probability: fakeProb,
                real_probability: probabilities[0],
                inference_time_ms: inferenceTime,
                source: 'local',
                model: 'deberta-v3-base-onnx'
            };
            
        } catch (error) {
            console.error('[LocalInference] Prediction failed:', error);
            throw error;
        }
    }

    /**
     * Lightweight fallback scoring for offline mode when ONNX runtime/assets are unavailable.
     */
    heuristicPredict(text) {
        const startTime = performance.now();
        const t = String(text || '').toLowerCase();

        const sensational = /\b(shocking|must\s+read|they\s+don't\s+want\s+you\s+to\s+know|breaking|urgent)\b/g;
        const absolutist = /\b(always|never|everyone|nobody|all|none|proved|guaranteed)\b/g;
        const conspiracy = /\b(hoax|cover[-\s]?up|deep state|mainstream media lies|fake media)\b/g;
        const sourceHints = /\b(reuters|ap\s?news|bbc|who|cdc|nih|nature|science)\b/g;

        const s = (t.match(sensational) || []).length;
        const a = (t.match(absolutist) || []).length;
        const c = (t.match(conspiracy) || []).length;
        const good = (t.match(sourceHints) || []).length;

        // Heuristic risk blend, clipped to [0.05, 0.95]
        let fakeProb = 0.35 + s * 0.12 + a * 0.07 + c * 0.15 - good * 0.08;
        fakeProb = Math.max(0.05, Math.min(0.95, fakeProb));

        const verdict = fakeProb > 0.5 ? 'fake' : 'real';
        const confidence = verdict === 'fake' ? fakeProb : (1 - fakeProb);

        return {
            verdict,
            confidence,
            fake_probability: fakeProb,
            real_probability: 1 - fakeProb,
            inference_time_ms: performance.now() - startTime,
            source: 'local',
            model: 'heuristic-fallback'
        };
    }
    
    /**
     * Tokenize text using loaded tokenizer
     * @param {string} text - Input text
     * @returns {Object} Tokenized input
     */
    tokenize(text) {
        // Simple tokenization (in production, use proper tokenizer library)
        // For now, this is a placeholder - you'll need to implement proper tokenization
        // or use a library like @xenova/transformers
        
        // Truncate text if too long
        const words = text.toLowerCase().split(/\s+/).slice(0, this.maxLength - 2);
        
        // Add special tokens: [CLS] text [SEP]
        const tokens = [101, ...words.map(w => this.wordToId(w)), 102]; // 101=CLS, 102=SEP
        
        // Pad to max length
        const paddedTokens = [...tokens];
        while (paddedTokens.length < this.maxLength) {
            paddedTokens.push(0); // 0 = PAD
        }
        
        // Create attention mask (1 for real tokens, 0 for padding)
        const attentionMask = paddedTokens.map(t => t === 0 ? 0 : 1);
        
        return {
            input_ids: paddedTokens.slice(0, this.maxLength),
            attention_mask: attentionMask.slice(0, this.maxLength)
        };
    }
    
    /**
     * Simple word to ID mapping (placeholder)
     * In production, use proper tokenizer vocabulary
     */
    wordToId(word) {
        // This is a placeholder - implement proper vocabulary lookup
        let hash = 0;
        for (let i = 0; i < word.length; i++) {
            hash = ((hash << 5) - hash) + word.charCodeAt(i);
            hash = hash & hash;
        }
        return Math.abs(hash) % 30000 + 1000; // Map to vocab range
    }
    
    /**
     * Softmax function for probability calculation
     * @param {Array<number>} arr - Logits array
     * @returns {Array<number>} Probabilities
     */
    softmax(arr) {
        const max = Math.max(...arr);
        const exp = arr.map(x => Math.exp(x - max));
        const sum = exp.reduce((a, b) => a + b, 0);
        return exp.map(x => x / sum);
    }
    
    /**
     * Get data from IndexedDB cache
     * @param {string} key - Cache key
     * @returns {Promise<ArrayBuffer|null>} Cached data or null
     */
    async getFromCache(key) {
        return new Promise((resolve) => {
            const request = indexedDB.open('FactCheckerAI', 1);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains('models')) {
                    db.createObjectStore('models');
                }
            };
            
            request.onsuccess = (event) => {
                const db = event.target.result;
                
                if (!db.objectStoreNames.contains('models')) {
                    resolve(null);
                    return;
                }
                
                const transaction = db.transaction(['models'], 'readonly');
                const store = transaction.objectStore('models');
                const getRequest = store.get(key);
                
                getRequest.onsuccess = () => resolve(getRequest.result || null);
                getRequest.onerror = () => resolve(null);
            };
            
            request.onerror = () => resolve(null);
        });
    }
    
    /**
     * Save data to IndexedDB cache
     * @param {string} key - Cache key
     * @param {ArrayBuffer} data - Data to cache
     */
    async saveToCache(key, data) {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('FactCheckerAI', 1);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains('models')) {
                    db.createObjectStore('models');
                }
            };
            
            request.onsuccess = (event) => {
                const db = event.target.result;
                const transaction = db.transaction(['models'], 'readwrite');
                const store = transaction.objectStore('models');
                const putRequest = store.put(data, key);
                
                putRequest.onsuccess = () => resolve();
                putRequest.onerror = () => reject(putRequest.error);
            };
            
            request.onerror = () => reject(request.error);
        });
    }
    
    /**
     * Clear model cache
     */
    async clearCache() {
        return new Promise((resolve) => {
            const request = indexedDB.deleteDatabase('FactCheckerAI');
            request.onsuccess = () => {
                console.log('[LocalInference] Cache cleared');
                resolve();
            };
            request.onerror = () => resolve();
        });
    }
    
    /**
     * Get model info
     */
    getInfo() {
        return {
            loaded: this.modelLoaded,
            mode: this.mode,
            modelPath: this.modelPath,
            tokenizerPath: this.tokenizerPath,
            ortRuntimePath: this.ortRuntimePath,
            ortAvailable: typeof ort !== 'undefined' && !!ort.InferenceSession,
            maxLength: this.maxLength,
            labels: this.labels
        };
    }
}

// Export singleton instance
const localInference = new LocalInference();

// Auto-initialize on script load
if (typeof chrome !== 'undefined' && chrome.runtime) {
    localInference.initialize().catch(console.error);
}

// Export for use in service worker
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { localInference };
}
