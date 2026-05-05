import request from "./http.client.js";

const ENDPOINTS = {
  attendance: {
    today: "/attendance/today",
    history: "/attendance/history",
    check: "/attendance/check",
    checkOut: "/attendance/check-out",
    delete: "/attendance/",
  },
  employee: {
    check: "/employee/attendance/check",
    delete: "/employee/attendance/delete",
    overtimeRequest: "/employee/attendance/overtime-request",
    overtimeRequestReset: "/employee/attendance/overtime-request/reset",
    state: "/employee/attendance/state",
    systemTime: "/employee/system/time",
  },
};
function postJson(url, payload = {}) {
  return request(url, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

function deleteJson(url, payload = {}) {
  return request(url, {
    method: "DELETE",
    body: JSON.stringify(payload),
  });
}

export const AttendanceAPI = {
  // ===== Generic attendance module endpoints =====
  getToday(params = {}) {
    const query = params.simulated_now ? `?simulated_now=${encodeURIComponent(params.simulated_now)}` : "";
    return request(`${ENDPOINTS.attendance.today}${query}`);
  },

  getHistory(params = {}) {
    const query = params.simulated_now ? `?simulated_now=${encodeURIComponent(params.simulated_now)}` : "";
    return request(`${ENDPOINTS.attendance.history}${query}`);
  },

  checkIn(payload = {}) {
    return postJson(ENDPOINTS.attendance.check, payload);
  },

  checkOut(payload = {}) {
    return postJson(ENDPOINTS.attendance.checkOut, payload);
  },
  deleteRecord(date) {
    return deleteJson(ENDPOINTS.attendance.delete, { date });
  },

  // ===== Employee flow endpoints (QR + OT decision flow) =====
  submitEmployeeAttendance(payload = {}) {
    return postJson(ENDPOINTS.employee.check, payload);
  },

  deleteEmployeeAttendance(date) {
    return deleteJson(ENDPOINTS.employee.delete, { date });
  },

  createOvertimeRequest(payload = {}) {
    return postJson(ENDPOINTS.employee.overtimeRequest, payload);
  },

  resetOvertimeRequest(date = null) {
    return request(ENDPOINTS.employee.overtimeRequestReset, {
      method: "DELETE",
      body: JSON.stringify({ date })
    });
  },

  getEmployeeAttendanceState() {
    return request(ENDPOINTS.employee.state);
  },

  setSystemTime(payload = {}) {
    return postJson(ENDPOINTS.employee.systemTime, payload);
  },

  getSystemTime() {
    return request(ENDPOINTS.employee.systemTime);
  },

  // Backward compatibility aliases
  history(params = {}) {
    return this.getHistory(params);
  },
};