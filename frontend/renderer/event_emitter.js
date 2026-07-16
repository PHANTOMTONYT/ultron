export default class EventEmitter {
  constructor() {
    this.listeners = {};
  }

  on(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
    return this;
  }

  emit(event, ...args) {
    if (!this.listeners[event]) return;
    for (const callback of this.listeners[event]) callback(...args);
  }
}
