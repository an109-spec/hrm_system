export class Table {
  constructor(tableId) {
    this.table = document.getElementById(tableId);
  }

  sort(columnIndex) {
    if (!this.table) return;

    const rows = Array.from(this.table.querySelectorAll("tbody tr"));

    rows.sort((a, b) => {
      const A = a.children[columnIndex].innerText;
      const B = b.children[columnIndex].innerText;
      return A.localeCompare(B, undefined, { numeric: true });
    });

    rows.forEach(row => this.table.querySelector("tbody").appendChild(row));
  }

  filter(keyword, columnIndex = 0) {
    if (!this.table) return;

    const rows = this.table.querySelectorAll("tbody tr");

    rows.forEach(row => {
      const text = row.children[columnIndex].innerText.toLowerCase();
      row.style.display = text.includes(keyword.toLowerCase()) ? "" : "none";
    });
  }
}