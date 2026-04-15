import request from "./http.client.js";

export const AuthAPI = {
  login(data) {
    return request("/auth/login", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  logout() {
    return request("/auth/logout", {
      method: "POST"
    });
  },

  me() {
    return request("/auth/me");
  }
};