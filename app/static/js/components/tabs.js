export class Tabs {
  constructor(tabButtonsSelector, tabContentsSelector) {
    this.buttons = document.querySelectorAll(tabButtonsSelector);
    this.contents = document.querySelectorAll(tabContentsSelector);

    this.buttons.forEach(btn => {
      btn.addEventListener("click", () => {
        this.activate(btn.dataset.tab);
      });
    });
  }

  activate(tabName) {
    this.contents.forEach(c => {
      c.style.display = c.dataset.tab === tabName ? "block" : "none";
    });

    this.buttons.forEach(b => {
      b.classList.toggle("active", b.dataset.tab === tabName);
    });
  }
}