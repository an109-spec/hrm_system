import { NotificationAPI } from "../../api/notification.api.js";

export class NotificationWidget {
  constructor(limit = 5) {
    this.limit = limit;
    this.el = document.getElementById("notification-list");
  }

  async load() {
    const data = await NotificationAPI.getLatest(this.limit);
    this.render(data);
  }

  render(list) {
    if (!this.el) return;

    this.el.innerHTML = list.map(n => `
      <div class="notification-item ${n.is_read ? "" : "unread"}">
        <div class="title">${n.title}</div>
        <div class="content">${n.content}</div>
      </div>
    `).join("");
  }
}