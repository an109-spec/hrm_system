export class Toast {
  static show(message, type = "info", duration = 3000) {
    const toast = document.createElement("div");

    toast.className = `toast toast-${type}`;
    toast.innerText = message;

    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add("show"), 100);

    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  static success(msg) {
    this.show(msg, "success");
  }

  static error(msg) {
    this.show(msg, "error");
  }

  static info(msg) {
    this.show(msg, "info");
  }
}