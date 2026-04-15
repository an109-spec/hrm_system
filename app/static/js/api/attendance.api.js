import request from "./http.client.js";

export const AttendanceAPI = {
  getToday() {
    return request("/attendance/today");
  },

  checkIn() {
    return request("/attendance/check-in", {
      method: "POST"
    });
  },

  checkOut() {
    return request("/attendance/check-out", {
      method: "POST"
    });
  },

  history() {
    return request("/attendance/history");
  }
};