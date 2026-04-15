export class SocketClient {
  constructor(url = "") {
    this.url = url || window.location.origin;
    this.socket = null;
  }

  connect() {
    if (!window.io) {
      console.error("Socket.IO client not found");
      return;
    }

    this.socket = io(this.url);

    this.socket.on("connect", () => {
      console.log("Socket connected:", this.socket.id);
    });

    this.socket.on("disconnect", () => {
      console.log("Socket disconnected");
    });
  }

  on(event, callback) {
    if (!this.socket) return;
    this.socket.on(event, callback);
  }

  emit(event, data) {
    if (!this.socket) return;
    this.socket.emit(event, data);
  }
}