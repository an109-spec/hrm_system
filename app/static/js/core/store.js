export class Store {
  constructor(initialState = {}) {
    this.state = { ...initialState };
    this.listeners = [];
  }

  getState() {
    return this.state;
  }

  setState(partial) {
    this.state = {
      ...this.state,
      ...partial,
    };

    this.notify();
  }

  subscribe(listener) {
    this.listeners.push(listener);

    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  notify() {
    this.listeners.forEach(listener => listener(this.state));
  }

  clear() {
    this.state = {};
    this.notify();
  }
}