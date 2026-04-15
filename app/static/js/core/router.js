export class Router {
  constructor() {
    this.routes = {};
    window.addEventListener("hashchange", () => this.resolve());
  }

  register(path, callback) {
    this.routes[path] = callback;
  }

  resolve() {
    const path = location.hash.replace("#", "") || "/";
    const handler = this.routes[path];

    if (handler) {
      handler();
    } else if (this.routes["404"]) {
      this.routes["404"]();
    }
  }

  navigate(path) {
    location.hash = path;
  }

  init() {
    this.resolve();
  }
}