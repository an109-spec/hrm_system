import request from "./http.client.js";

export const NotificationAPI = {
  getAll(limit = 10) {
    return request(`/notifications?limit=${limit}`);
  },

  markRead(id) {
    return request(`/notifications/${id}/read`, {
      method: "POST"
    });
  },

  markAllRead() {
    return request("/notifications/read-all", {
      method: "POST"
    });
  }
};