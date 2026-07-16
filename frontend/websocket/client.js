import EventEmitter from '../renderer/event_emitter.js';

class WSClient extends EventEmitter {
  constructor(url) {
    super();
    this.url = url;
    this.socket = null;
    this.reconnectTimer = null;
    this.isConnected = false;
  }
  
  connect() {
    console.log(`Connecting to WebSocket server at ${this.url}...`);
    this.socket = new WebSocket(this.url);
    
    this.socket.onopen = () => {
      console.log('Connected to companion backend WebSocket!');
      this.isConnected = true;
      this.emit('connected');
      if (this.reconnectTimer) {
        clearInterval(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    };
    
    this.socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.emit('message', message);
        if (message.type) {
          this.emit(message.type, message);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };
    
    this.socket.onclose = () => {
      if (this.isConnected) {
        console.log('WebSocket connection closed.');
        this.isConnected = false;
        this.emit('disconnected');
      }
      this.scheduleReconnect();
    };
    
    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }
  
  scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setInterval(() => {
      if (!this.isConnected) {
        this.connect();
      }
    }, 3000); // Try reconnecting every 3 seconds
  }
  
  send(type, payload = {}) {
    if (!this.isConnected || !this.socket) {
      console.warn(`WebSocket not connected. Cannot send event: ${type}`);
      return;
    }
    const message = JSON.stringify({ type, ...payload });
    this.socket.send(message);
  }
  
  close() {
    if (this.reconnectTimer) {
      clearInterval(this.reconnectTimer);
    }
    if (this.socket) {
      this.socket.close();
    }
  }
}
export default WSClient;
