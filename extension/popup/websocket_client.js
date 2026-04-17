/**
 * WebSocket Client Manager
 * 
 * Manages real-time WebSocket connection to the backend for live updates.
 * Handles automatic reconnection, heartbeat, and message routing.
 */

class WebSocketManager {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000; // Start with 1 second
    this.maxReconnectDelay = 30000; // Max 30 seconds
    this.pingInterval = null;
    this.pingIntervalMs = 30000; // Ping every 30 seconds
    this.isConnecting = false;
    this.isIntentionallyClosed = false;
    this.messageHandlers = new Map();
    this.connectionStateCallbacks = [];
    
    // Connection state
    this.state = 'disconnected'; // disconnected, connecting, connected, reconnecting
  }
  
  /**
   * Connect to WebSocket server
   * @param {string} token - JWT token for authentication (optional)
   * @param {string} sessionKey - Session key for anonymous users (optional)
   */
  async connect(token = null, sessionKey = null) {
    if (this.isConnecting || this.state === 'connected') {
      return;
    }
    
    this.isIntentionallyClosed = false;
    this.isConnecting = true;
    this.updateState('connecting');
    
    try {
      // Get WebSocket URL from config
      const wsUrl = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
      
      // Build connection URL with auth
      let url = `${wsUrl}/ws/connect`;
      const params = [];
      if (token) {
        params.push(`token=${encodeURIComponent(token)}`);
      } else if (sessionKey) {
        params.push(`session_key=${encodeURIComponent(sessionKey)}`);
      }
      if (params.length > 0) {
        url += `?${params.join('&')}`;
      }
      
      this.ws = new WebSocket(url);
      
      this.ws.onopen = () => {
        console.log('[WS] Connected');
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.updateState('connected');
        this.startPing();
      };
      
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (err) {
          console.error('[WS] Failed to parse message:', err);
        }
      };
      
      this.ws.onerror = (error) => {
        console.error('[WS] Error:', error);
      };
      
      this.ws.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason);
        this.isConnecting = false;
        this.stopPing();
        this.updateState('disconnected');
        
        // Attempt reconnection if not intentionally closed
        if (!this.isIntentionallyClosed) {
          this.scheduleReconnect(token, sessionKey);
        }
      };
      
    } catch (err) {
      console.error('[WS] Connection failed:', err);
      this.isConnecting = false;
      this.updateState('disconnected');
      this.scheduleReconnect(token, sessionKey);
    }
  }
  
  /**
   * Schedule reconnection with exponential backoff
   */
  scheduleReconnect(token, sessionKey) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WS] Max reconnection attempts reached');
      this.updateState('disconnected');
      return;
    }
    
    this.reconnectAttempts++;
    this.updateState('reconnecting');
    
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    );
    
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    
    setTimeout(() => {
      this.connect(token, sessionKey);
    }, delay);
  }
  
  /**
   * Disconnect from WebSocket server
   */
  disconnect() {
    this.isIntentionallyClosed = true;
    this.stopPing();
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    
    this.updateState('disconnected');
  }
  
  /**
   * Send a message to the server
   */
  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
      return true;
    }
    console.warn('[WS] Cannot send message - not connected');
    return false;
  }
  
  /**
   * Start heartbeat ping
   */
  startPing() {
    this.stopPing();
    this.pingInterval = setInterval(() => {
      this.send({ type: 'ping' });
    }, this.pingIntervalMs);
  }
  
  /**
   * Stop heartbeat ping
   */
  stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
  
  /**
   * Handle incoming message from server
   */
  handleMessage(message) {
    const { type } = message;
    
    // Call registered handlers for this message type
    const handlers = this.messageHandlers.get(type) || [];
    handlers.forEach(handler => {
      try {
        handler(message);
      } catch (err) {
        console.error(`[WS] Handler error for ${type}:`, err);
      }
    });
    
    // Built-in message handlers
    switch (type) {
      case 'connected':
        console.log('[WS] Welcome:', message.message);
        break;
      
      case 'pong':
        // Heartbeat response
        break;
      
      case 'claim_verified':
        this.handleClaimVerified(message);
        break;
      
      case 'review_queue_update':
        this.handleReviewQueueUpdate(message);
        break;
      
      case 'model_accuracy_change':
        this.handleModelAccuracyChange(message);
        break;
      
      case 'ab_test_results':
        this.handleABTestResults(message);
        break;
      
      case 'system_alert':
        this.handleSystemAlert(message);
        break;
      
      case 'user_activity':
        this.handleUserActivity(message);
        break;
      
      case 'room_joined':
        console.log('[WS] Joined room:', message.room);
        break;
      
      case 'room_left':
        console.log('[WS] Left room:', message.room);
        break;
      
      case 'error':
        console.error('[WS] Server error:', message.message);
        break;
      
      default:
        console.log('[WS] Unknown message type:', type, message);
    }
  }
  
  /**
   * Register a message handler
   * @param {string} type - Message type to handle
   * @param {function} handler - Handler function
   */
  on(type, handler) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    this.messageHandlers.get(type).push(handler);
  }
  
  /**
   * Unregister a message handler
   */
  off(type, handler) {
    if (!this.messageHandlers.has(type)) return;
    const handlers = this.messageHandlers.get(type);
    const index = handlers.indexOf(handler);
    if (index > -1) {
      handlers.splice(index, 1);
    }
  }
  
  /**
   * Register connection state change callback
   */
  onStateChange(callback) {
    this.connectionStateCallbacks.push(callback);
  }
  
  /**
   * Update connection state and notify callbacks
   */
  updateState(newState) {
    if (this.state === newState) return;
    this.state = newState;
    this.connectionStateCallbacks.forEach(cb => {
      try {
        cb(newState);
      } catch (err) {
        console.error('[WS] State callback error:', err);
      }
    });
  }
  
  /**
   * Join a collaborative room
   */
  joinRoom(room) {
    this.send({ type: 'join_room', room });
  }
  
  /**
   * Leave a collaborative room
   */
  leaveRoom(room) {
    this.send({ type: 'leave_room', room });
  }
  
  // ── Built-in Message Handlers ──────────────────────────────
  
  handleClaimVerified(message) {
    console.log('[WS] Claim verified:', message.data);
    
    // Show notification
    this.showNotification('Claim Verified', {
      body: 'Your claim verification is complete',
      icon: chrome.runtime.getURL('icons/icon48.png'),
      tag: 'claim-verified'
    });
    
    // Update UI if on relevant page
    if (window.location.pathname.includes('history.html')) {
      // Reload history
      if (typeof loadHistory === 'function') {
        loadHistory();
      }
    }
  }
  
  handleReviewQueueUpdate(message) {
    console.log('[WS] Review queue updated:', message.priority);
    
    // Update badge if on review page
    if (window.location.pathname.includes('review.html')) {
      if (typeof loadReviewQueue === 'function') {
        loadReviewQueue();
      }
    }
  }
  
  handleModelAccuracyChange(message) {
    console.log('[WS] Model accuracy changed:', message.accuracy, message.time_window);
    
    // Show notification for significant changes
    if (Math.abs(message.accuracy - 0.85) > 0.05) {
      this.showNotification('Model Update', {
        body: `Model accuracy: ${Math.round(message.accuracy * 100)}%`,
        icon: chrome.runtime.getURL('icons/icon48.png'),
        tag: 'model-accuracy'
      });
    }
  }
  
  handleABTestResults(message) {
    console.log('[WS] A/B test results available:', message.test_name);
    
    this.showNotification('A/B Test Complete', {
      body: `Results available for: ${message.test_name}`,
      icon: chrome.runtime.getURL('icons/icon48.png'),
      tag: 'ab-test'
    });
  }
  
  handleSystemAlert(message) {
    console.log('[WS] System alert:', message.alert_type, message.severity);
    
    // Show notification for important alerts
    if (message.severity === 'warning' || message.severity === 'error') {
      this.showNotification('System Alert', {
        body: message.message,
        icon: chrome.runtime.getURL('icons/icon48.png'),
        tag: 'system-alert'
      });
    }
  }
  
  handleUserActivity(message) {
    console.log('[WS] User activity:', message.activity);
    // Handle collaborative features
  }
  
  /**
   * Show browser notification
   */
  showNotification(title, options) {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(title, options);
    }
  }
  
  /**
   * Get current connection state
   */
  getState() {
    return this.state;
  }
  
  /**
   * Check if connected
   */
  isConnected() {
    return this.state === 'connected';
  }
}

// Global WebSocket manager instance
const wsManager = new WebSocketManager();

// Auto-connect when token is available
chrome.storage.local.get(['token', 'user'], (data) => {
  if (data.token) {
    // Small delay to ensure page is ready
    setTimeout(() => {
      wsManager.connect(data.token);
    }, 500);
  }
});

// Reconnect when token changes
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.token) {
    if (changes.token.newValue) {
      wsManager.connect(changes.token.newValue);
    } else {
      wsManager.disconnect();
    }
  }
});
