import { Store } from "../core/store.js";

class NotificationStore extends Store {
  constructor() {
    super({
      list: [],
      unreadCount: 0,
    });
  }

  setNotifications(list) {
    const unread = list.filter(n => !n.is_read).length;

    this.setState({
      list,
      unreadCount: unread,
    });
  }

  addNotification(notification) {
    const newList = [notification, ...this.state.list];

    const unread = newList.filter(n => !n.is_read).length;

    this.setState({
      list: newList,
      unreadCount: unread,
    });
  }

  markAsRead(id) {
    const updated = this.state.list.map(n =>
      n.id === id ? { ...n, is_read: true } : n
    );

    const unread = updated.filter(n => !n.is_read).length;

    this.setState({
      list: updated,
      unreadCount: unread,
    });
  }

  clear() {
    this.setState({
      list: [],
      unreadCount: 0,
    });
  }

  getUnread() {
    return this.state.unreadCount;
  }
}

export const notificationStore = new NotificationStore();