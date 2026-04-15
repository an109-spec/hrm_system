import { NotificationAPI } from "../api/notification.api.js";

export class Notification {
  static async markAsRead(id) {
    await NotificationAPI.markAsRead(id);
  }

  static listen(socket) {
    socket.on("notification:new", (data) => {
      const event = new CustomEvent("new-notification", { detail: data });
      window.dispatchEvent(event);
    });
  }
}