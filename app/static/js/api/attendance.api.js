import request from "./http.client.js";

export const AttendanceAPI = {
  getToday() {
    return request("/attendance/today");
  },

checkIn(simulated_now) {
  return request("/attendance/check", {
    method: "POST",
    body: JSON.stringify({
      simulated_now: simulated_now,
      qr_text: "QR"
    })
  });
},

  checkOut() {
    return request("/attendance/check-out", {
      method: "POST"
    });
  },

  history() {
    return request("/attendance/history");
  },
  deleteRecord(date) {
    return request("/attendance/", {
      method: "DELETE",
      body: JSON.stringify({ date: date })
    });
  }
};