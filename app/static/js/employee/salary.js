import { SalaryAPI } from "../api/salary.api.js";
import { formatCurrency } from "../core/utils.js";

export class Salary {
  static async loadList() {
    return await SalaryAPI.getMySalaries();
  }

  static renderDetail(data) {
    const el = document.getElementById("salary-detail");
    if (!el) return;

    el.innerHTML = `
      <h3>Phiếu lương ${data.month}/${data.year}</h3>
      <p>Lương cơ bản: ${formatCurrency(data.basic_salary)}</p>
      <p>Phụ cấp: ${formatCurrency(data.total_allowance)}</p>
      <p>Thưởng: ${formatCurrency(data.bonus)}</p>
      <p>Khấu trừ: ${formatCurrency(data.penalty)}</p>
      <h2>Thực nhận: ${formatCurrency(data.net_salary)}</h2>
    `;
  }
}