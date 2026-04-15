import { formatCurrency } from "../../core/utils.js";

export class SummaryCard {
  static render(data) {
    const el = document.getElementById("summary-cards");
    if (!el) return;

    el.innerHTML = `
      <div class="card">
        <h4>Công hôm nay</h4>
        <p>${data.working_hours || 0}h</p>
      </div>

      <div class="card">
        <h4>Phép còn lại</h4>
        <p>${data.remaining_days || 0} ngày</p>
      </div>

      <div class="card">
        <h4>Lương gần nhất</h4>
        <p>${formatCurrency(data.net_salary || 0)}</p>
      </div>
    `;
  }
}