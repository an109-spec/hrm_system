export class Dropdown {
  constructor(triggerSelector, menuSelector) {
    this.trigger = document.querySelector(triggerSelector);
    this.menu = document.querySelector(menuSelector);

    if (this.trigger) {
      this.trigger.addEventListener("click", () => this.toggle());
    }
  }

  toggle() {
    if (!this.menu) return;
    this.menu.classList.toggle("open");
  }

  close() {
    if (this.menu) {
      this.menu.classList.remove("open");
    }
  }
}