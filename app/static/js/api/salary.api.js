import request from "./http.client.js";

export const SalaryAPI = {
  mySalaries() {
    return request("/salary/my");
  },

  detail(id) {
    return request(`/salary/${id}`);
  },

  complain(id, data) {
    return request(`/salary/${id}/complaint`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  }
};