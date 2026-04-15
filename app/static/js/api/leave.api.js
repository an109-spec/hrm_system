import request from "./http.client.js";

export const LeaveAPI = {
  getTypes() {
    return request("/leave/types");
  },

  create(data) {
    return request("/leave/request", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  myRequests() {
    return request("/leave/my-requests");
  },

  cancel(id) {
    return request(`/leave/request/${id}/cancel`, {
      method: "POST"
    });
  }
};