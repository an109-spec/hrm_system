import request from "./http.client.js";

export const EmployeeAPI = {
  getProfile() {
    return request("/employee/profile");
  },

  updateProfile(data) {
    return request("/employee/profile", {
      method: "PUT",
      body: JSON.stringify(data)
    });
  },

  search(query) {
    return request(`/employee/search?q=${query}`);
  }
};