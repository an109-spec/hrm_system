export class NotificationSocket {
  constructor(socketClient) {
    this.socket = socketClient;
    this.handlers = new Map();
  }

  /**
   * Khởi tạo listeners mặc định cho HRM notification
   */
  init() {
    if (!this.socket) {
      console.error("Socket client not provided");
      return;
    }

    // Khi có notification mới từ server
    this.socket.on("notification:new", (payload) => {
      this.emitLocal("notification:new", payload);
    });

    // Khi leave request được xử lý
    this.socket.on("leave:updated", (payload) => {
      this.emitLocal("leave:updated", payload);
    });

    // Khi salary được cập nhật / chốt lương
    this.socket.on("salary:updated", (payload) => {
      this.emitLocal("salary:updated", payload);
    });

    // Khi complaint có phản hồi
    this.socket.on("complaint:replied", (payload) => {
      this.emitLocal("complaint:replied", payload);
    });

    // Attendance realtime update (check-in/out)
    this.socket.on("attendance:updated", (payload) => {
      this.emitLocal("attendance:updated", payload);
    });
  }

  /**
   * Đăng ký handler nội bộ (frontend event bus)
   */
  on(event, callback) {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event).push(callback);
  }

  /**
   * Emit event nội bộ tới UI components
   */
  emitLocal(event, data) {
    const callbacks = this.handlers.get(event);
    if (!callbacks) return;

    callbacks.forEach((cb) => {
      try {
        cb(data);
      } catch (err) {
        console.error(`Socket handler error [${event}]`, err);
      }
    });
  }

  /**
   * Gửi event lên server (optional use-case: attendance QR scan)
   */
  emit(event, data) {
    if (!this.socket) return;
    this.socket.emit(event, data);
  }

  /**
   * Subscribe nhanh cho notification UI
   */
  onNotification(callback) {
    this.on("notification:new", callback);
  }

  /**
   * Subscribe cho dashboard realtime update
   */
  onDashboardUpdate(callback) {
    this.on("attendance:updated", callback);
    this.on("salary:updated", callback);
    this.on("leave:updated", callback);
  }
}