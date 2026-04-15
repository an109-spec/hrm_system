import request from "./http.client.js";

export const DashboardAPI = {
  getEmployeeDashboard() {
    return request("/employee/dashboard");
  }
};