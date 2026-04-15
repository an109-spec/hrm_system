export class Modal {
  constructor(id) {
    this.el = document.getElementById(id);
  }

  open() {
    if (!this.el) return;
    this.el.classList.add("show");
  }

  close() {
    if (!this.el) return;
    this.el.classList.remove("show");
  }

  toggle() {
    if (!this.el) return;
    this.el.classList.toggle("show");
  }
}