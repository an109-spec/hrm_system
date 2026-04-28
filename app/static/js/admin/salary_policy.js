async function policyApi(url, options = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || 'Request failed');
  return d;
}

let currentPolicy = null;
let policyHistory = [];

function money(v) { return Number(v || 0).toLocaleString('vi-VN'); }

function taxRows(brackets = []) {
  return brackets.map((b, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td><input data-k="from" data-i="${idx}" type="number" value="${b.from || 0}"></td>
      <td><input data-k="to" data-i="${idx}" type="number" value="${b.to || 0}"></td>
      <td><input data-k="rate_percent" data-i="${idx}" type="number" step="0.01" value="${b.rate_percent || 0}"></td>
      <td><input data-k="quick_deduction" data-i="${idx}" type="number" value="${b.quick_deduction || 0}"></td>
    </tr>`).join('');
}

function renderPolicy(policy) {
  currentPolicy = policy;
  document.getElementById('lateUnder15').value = policy.late_penalty.under_15 || 0;
  document.getElementById('late15to30').value = policy.late_penalty.from_15_to_30 || 0;
  document.getElementById('lateOver60HalfDay').checked = !!policy.late_penalty.over_60_half_day;
  document.getElementById('insSocial').value = policy.insurance.social_percent || 0;
  document.getElementById('insHealth').value = policy.insurance.health_percent || 0;
  document.getElementById('insUnemployment').value = policy.insurance.unemployment_percent || 0;
  document.getElementById('insTotal').textContent = (policy.insurance.total_percent || 0).toFixed(2);
  document.getElementById('dedPersonal').value = policy.deduction.personal || 0;
  document.getElementById('dedDependent').value = policy.deduction.dependent_per_person || 0;
  document.getElementById('taxBracketRows').innerHTML = taxRows(policy.tax.brackets || []);
  document.getElementById('btnPolicyLock').textContent = policy.config_edit_locked ? 'Mở khóa chỉnh sửa' : 'Khóa chỉnh sửa';
  renderExample();
}

function collectPolicy() {
  const brackets = Array.from(document.querySelectorAll('#taxBracketRows tr')).map((row, idx) => ({
    id: idx + 1,
    from: Number(row.querySelector('input[data-k="from"]').value || 0),
    to: Number(row.querySelector('input[data-k="to"]').value || 0),
    rate_percent: Number(row.querySelector('input[data-k="rate_percent"]').value || 0),
    quick_deduction: Number(row.querySelector('input[data-k="quick_deduction"]').value || 0),
  }));
  return {
    late_penalty: {
      under_15: Number(document.getElementById('lateUnder15').value || 0),
      from_15_to_30: Number(document.getElementById('late15to30').value || 0),
      over_60_half_day: document.getElementById('lateOver60HalfDay').checked,
    },
    insurance: {
      social_percent: Number(document.getElementById('insSocial').value || 0),
      health_percent: Number(document.getElementById('insHealth').value || 0),
      unemployment_percent: Number(document.getElementById('insUnemployment').value || 0),
    },
    deduction: {
      personal: Number(document.getElementById('dedPersonal').value || 0),
      dependent_per_person: Number(document.getElementById('dedDependent').value || 0),
    },
    tax: { brackets }
  };
}

function computeTax(base, brackets = []) {
  const b = brackets.find(x => base > Number(x.from || 0) && base <= Number(x.to || 0)) || brackets[brackets.length - 1];
  if (!b) return { tax: 0, bracket: 0 };
  const tax = Math.max(0, base * (Number(b.rate_percent || 0) / 100) - Number(b.quick_deduction || 0));
  return { tax, bracket: Number(b.id || 1) };
}

function renderExample() {
  if (!currentPolicy) return;
  const gross = 40_000_000;
  const dependentCount = 2;
  const personal = Number(document.getElementById('dedPersonal').value || 0);
  const dependent = Number(document.getElementById('dedDependent').value || 0) * dependentCount;
  const insurance = gross * ((Number(document.getElementById('insSocial').value || 0) + Number(document.getElementById('insHealth').value || 0) + Number(document.getElementById('insUnemployment').value || 0)) / 100);
  const taxable = Math.max(0, gross - personal - insurance - dependent);
  const t = computeTax(taxable, collectPolicy().tax.brackets);
  document.getElementById('realExampleBox').innerHTML = `
    Giảm trừ bản thân: <b>${money(personal)}</b><br>
    Bảo hiểm: <b>${money(insurance)}</b><br>
    Giảm trừ 2 người phụ thuộc: <b>${money(dependent)}</b><br>
    TNTT = 40,000,000 - ${money(personal)} - ${money(insurance)} - ${money(dependent)} = <b>${money(taxable)}</b><br>
    → Thuộc bậc <b>${t.bracket}</b><br>
    Thuế = <b>${money(t.tax)}</b> VNĐ
  `;
}

async function loadPolicy() {
  const data = await policyApi('/api/admin/salary-policy');
  renderPolicy(data);
}

async function loadHistory() {
  policyHistory = await policyApi('/api/admin/salary-policy/history');
}

async function savePolicy() {
  const c = await Swal.fire({ title: 'Cập nhật cấu hình Salary Policy Center?', icon: 'question', showCancelButton: true });
  if (!c.isConfirmed) return;
  await policyApi('/api/admin/salary-policy', { method: 'PUT', body: JSON.stringify(collectPolicy()) });
  await Swal.fire({ icon: 'success', title: 'Đã cập nhật cấu hình' });
  await loadPolicy();
}

async function showHistory() {
  await loadHistory();
  await Swal.fire({ title: 'History Log', html: (policyHistory || []).slice(0, 20).map(h => `<p>#${h.id} [${h.action}] ${h.time || ''}</p>`).join('') || 'Chưa có log', width: 700 });
}

async function restorePolicy() {
  await loadHistory();
  const options = (policyHistory || []).filter(h => h.action === 'UPDATE_SALARY_POLICY').map(h => `<option value="${h.id}">#${h.id} - ${h.time || ''}</option>`).join('');
  if (!options) return Swal.fire({ icon: 'info', title: 'Không có bản cấu hình để khôi phục' });
  const { isConfirmed, value } = await Swal.fire({ title: 'Khôi phục cấu hình', html: `<select id="restoreHistoryId" class="swal2-input">${options}</select>`, showCancelButton: true, preConfirm: () => Number(document.getElementById('restoreHistoryId').value || 0) });
  if (!isConfirmed) return;
  await policyApi('/api/admin/salary-policy/restore', { method: 'POST', body: JSON.stringify({ history_id: value }) });
  await Swal.fire({ icon: 'success', title: 'Đã khôi phục cấu hình' });
  await loadPolicy();
}

async function toggleLock() {
  const lockNow = !currentPolicy?.config_edit_locked;
  const ask = await Swal.fire({ title: lockNow ? 'Khóa chỉnh sửa?' : 'Mở khóa chỉnh sửa?', icon: 'warning', showCancelButton: true });
  if (!ask.isConfirmed) return;
  await policyApi('/api/admin/salary-policy/lock-edit', { method: 'POST', body: JSON.stringify({ locked: lockNow }) });
  await Swal.fire({ icon: 'success', title: lockNow ? 'Đã khóa chỉnh sửa' : 'Đã mở khóa chỉnh sửa' });
  await loadPolicy();
}

document.addEventListener('DOMContentLoaded', async () => {
  if (window.ADMIN_PAGE !== 'salary_policy') return;
  await loadPolicy();
  ['insSocial', 'insHealth', 'insUnemployment', 'dedPersonal', 'dedDependent', 'taxBracketRows'].forEach((id) => {
    document.getElementById(id)?.addEventListener('input', renderExample);
  });
  document.getElementById('btnPolicyUpdate')?.addEventListener('click', savePolicy);
  document.getElementById('btnPolicyHistory')?.addEventListener('click', showHistory);
  document.getElementById('btnPolicyRestore')?.addEventListener('click', restorePolicy);
  document.getElementById('btnPolicyLock')?.addEventListener('click', toggleLock);
});