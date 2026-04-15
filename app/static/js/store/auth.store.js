import { Store } from "../core/store.js";

class AuthStore extends Store {
  constructor() {
    super({
      user: null,
      token: null,
      isAuthenticated: false,
    });
  }

  setAuth(user, token) {
    this.setState({
      user,
      token,
      isAuthenticated: true,
    });
  }

  logout() {
    this.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
  }

  getUser() {
    return this.state.user;
  }
}

export const authStore = new AuthStore();