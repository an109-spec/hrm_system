const PayrollApi = {
  async request(url, options = {}) {
    const res = await fetch(url, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.error || 'Có lỗi trong xử lý payroll')
    return data
  },
  meta() { return this.request('/hr/api/payroll/meta') },
  calculate(payload) { return this.request('/hr/api/payroll/calculate', { method: 'POST', body: JSON.stringify(payload) }) },
  list(params) { return this.request(`/hr/api/payroll?${new URLSearchParams(params).toString()}`) },
  detail(id) { return this.request(`/hr/api/payroll/${id}`) },
  saveAdjustments(id, payload) { return this.request(`/hr/api/payroll/${id}/adjustments`, { method: 'PUT', body: JSON.stringify(payload) }) },
  submit(id) { return this.request(`/hr/api/payroll/${id}/submit`, { method: 'POST' }) },
  approve(id, payload) { return this.request(`/hr/api/payroll/${id}/approve`, { method: 'POST', body: JSON.stringify(payload) }) },
  complaints(params) { return this.request(`/hr/api/payroll/complaints?${new URLSearchParams(params).toString()}`) },
  handleComplaint(id, payload) { return this.request(`/hr/api/payroll/complaints/${id}/handle`, { method: 'POST', body: JSON.stringify(payload) }) }
}

const state = { items: [], selectedId: null }
const money = new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 })

function toast(msg) {
  const t = document.getElementById('hrToast')
  t.textContent = msg
  t.hidden = false
  clearTimeout(toast.timer)
  toast.timer = setTimeout(() => { t.hidden = true }, 2500)
}

function formatMoney(v) { return money.format(Number(v || 0)) }

function collectFilters() {
  return {
    search: document.getElementById('searchInput').value.trim(),
    department_id: document.getElementById('departmentFilter').value,
    status: document.getElementById('statusFilter').value,
    month: document.getElementById('monthFilter').value,
    year: document.getElementById('yearFilter').value
  }
}

function renderTable() {
  const body = document.getElementById('payrollTableBody')
  body.innerHTML = state.items.map(row => `
    <tr>
      <td>${row.employee_code}</td><td>${row.employee_name}</td><td>${row.department}</td><td>${row.position}</td>
      <td>${formatMoney(row.basic_salary)}</td><td>${row.total_work_days}</td><td>${row.leave_days}</td><td>${row.overtime_hours}</td>
      <td>${formatMoney(row.allowance)}</td><td>${formatMoney(row.penalty)}</td><td>${formatMoney(row.net_salary)}</td>
      <td><span class="badge ${row.status}">${row.status_label}</span></td>
      <td><button class="btn" data-id="${row.id}">Chi tiết</button></td>
    </tr>
  `).join('')
}

function renderSummary(summary) {
  document.getElementById('sumPayrollFund').textContent = formatMoney(summary.payroll_fund)
  document.getElementById('sumPending').textContent = summary.pending_approval || 0
  document.getElementById('sumComplaints').textContent = summary.complaint_count || 0
  document.getElementById('sumMissing').textContent = summary.missing_payroll || 0
  document.getElementById('complaintShortcut').hidden = !(summary.complaint_count > 0)
}

function renderBreakdown(breakdown = {}) {
  const map = [
    ['Lương cơ bản', 'base_salary'], ['Phụ cấp', 'allowance'], ['Tăng ca', 'overtime_amount'], ['Đi muộn', 'late_penalty'],
    ['BHXH', 'social_insurance'], ['BHYT', 'health_insurance'], ['BHTN', 'unemployment_insurance'], ['Thuế TNCN', 'personal_income_tax'],
    ['Phạt nội bộ', 'manual_deduction'], ['Tổng cộng', 'gross_total'], ['Lương thực nhận', 'net_salary']
  ]
  document.getElementById('breakdownPanel').innerHTML = map.map(([label, key]) => `<dt>${label}</dt><dd>${formatMoney(breakdown[key])}</dd>`).join('')
}

function fillAdjustmentForm(detail) {
  document.getElementById('salaryId').value = detail.id
  document.getElementById('approvalStatus').textContent = detail.status_label
  const ma = detail.manual_allowances || {}
  const md = detail.manual_deductions || {}
  document.getElementById('fuelAllowance').value = ma.fuel_allowance || 0
  document.getElementById('mealAllowance').value = ma.meal_allowance || 0
  document.getElementById('responsibilityAllowance').value = ma.responsibility_allowance || 0
  document.getElementById('otherAllowance').value = ma.other_allowance || 0
  document.getElementById('latePenalty').value = md.late_penalty || 0
  document.getElementById('earlyPenalty').value = md.early_penalty || 0
  document.getElementById('unpaidLeavePenalty').value = md.unpaid_leave_penalty || 0
  document.getElementById('otherPenalty').value = md.other_penalty || 0

  document.getElementById('auditList').innerHTML = (detail.audit || []).map(log => (
    `<li><strong>${log.action}</strong><br>${log.description || ''}<br><small>${log.created_at || ''}</small></li>`
  )).join('') || '<li>Chưa có lịch sử chỉnh sửa.</li>'
}

async function loadPayroll() {
  const data = await PayrollApi.list(collectFilters())
  state.items = data.items || []
  renderTable()
  renderSummary(data.summary || {})
}

async function loadComplaints() {
  const data = await PayrollApi.complaints({ month: document.getElementById('monthFilter').value, year: document.getElementById('yearFilter').value })
  const list = document.getElementById('complaintList')
  list.innerHTML = (data || []).map(c => (`
    <li>
      <strong>${c.employee}</strong> - ${c.title}<br>
      <small>${c.description}</small>
      <div class="actions" style="margin-top:6px;">
        <button class="btn" data-cid="${c.id}" data-action="in_progress">Đang xử lý</button>
        <button class="btn" data-cid="${c.id}" data-action="resolved">Giải quyết</button>
        <button class="btn" data-cid="${c.id}" data-action="rejected">Từ chối</button>
      </div>
    </li>
  `)).join('') || '<li>Không có khiếu nại lương.</li>'
}

async function bootstrap() {
  try {
    const meta = await PayrollApi.meta()
    const dSelect = document.getElementById('departmentFilter')
    dSelect.innerHTML = '<option value="">Tất cả</option>' + (meta.departments || []).map(d => `<option value="${d.id}">${d.name}</option>`).join('')
    document.getElementById('statusFilter').innerHTML = (meta.payroll_statuses || []).map(s => `<option value="${s.value}">${s.label}</option>`).join('')

    const monthSel = document.getElementById('monthFilter')
    monthSel.innerHTML = Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}">Tháng ${i + 1}</option>`).join('')
    const now = new Date()
    monthSel.value = String(now.getMonth() + 1)

    const yearSel = document.getElementById('yearFilter')
    yearSel.innerHTML = [now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map(y => `<option value="${y}">${y}</option>`).join('')
    yearSel.value = String(now.getFullYear())

    await Promise.all([loadPayroll(), loadComplaints()])

    ;['searchInput', 'departmentFilter', 'statusFilter', 'monthFilter', 'yearFilter'].forEach(id => {
      document.getElementById(id).addEventListener(id === 'searchInput' ? 'input' : 'change', () => {
        loadPayroll().catch(e => toast(e.message))
        loadComplaints().catch(e => toast(e.message))
      })
    })

    document.getElementById('btnCalculate').addEventListener('click', async () => {
      const payload = { month: Number(monthSel.value), year: Number(yearSel.value), department_id: Number(dSelect.value) || null }
      const result = await PayrollApi.calculate(payload)
      toast(`Đã tính lương cho ${result.processed} nhân viên`)
      await loadPayroll(); await loadComplaints()
    })

    document.getElementById('btnExport').addEventListener('click', () => {
      const scope = window.prompt('Nhập phạm vi export (company/department):', 'company') || 'company'
      const format = window.prompt('Nhập định dạng (pdf/excel):', 'excel') || 'excel'
      const url = `/hr/api/payroll/export?month=${monthSel.value}&year=${yearSel.value}&scope=${scope}&format=${format}&department_id=${dSelect.value || ''}`
      window.open(url, '_blank')
    })

    document.getElementById('payrollTableBody').addEventListener('click', async (e) => {
      const btn = e.target.closest('button[data-id]')
      if (!btn) return
      const id = Number(btn.dataset.id)
      state.selectedId = id
      const detail = await PayrollApi.detail(id)
      fillAdjustmentForm(detail)
      renderBreakdown(detail.breakdown)
    })

    document.getElementById('adjustmentForm').addEventListener('submit', async (e) => {
      e.preventDefault()
      if (!state.selectedId) return toast('Vui lòng chọn payroll cần chỉnh sửa')
      const payload = {
        fuel_allowance: Number(document.getElementById('fuelAllowance').value || 0),
        meal_allowance: Number(document.getElementById('mealAllowance').value || 0),
        responsibility_allowance: Number(document.getElementById('responsibilityAllowance').value || 0),
        other_allowance: Number(document.getElementById('otherAllowance').value || 0),
        late_penalty: Number(document.getElementById('latePenalty').value || 0),
        early_penalty: Number(document.getElementById('earlyPenalty').value || 0),
        unpaid_leave_penalty: Number(document.getElementById('unpaidLeavePenalty').value || 0),
        other_penalty: Number(document.getElementById('otherPenalty').value || 0),
        note: document.getElementById('adjustmentNote').value
      }
      const detail = await PayrollApi.saveAdjustments(state.selectedId, payload)
      fillAdjustmentForm(detail)
      renderBreakdown(detail.breakdown)
      toast('Đã cập nhật phụ cấp / khấu trừ')
      await loadPayroll()
    })

    document.getElementById('btnSubmitApproval').addEventListener('click', async () => {
      if (!state.selectedId) return toast('Vui lòng chọn payroll để gửi duyệt')
      await PayrollApi.submit(state.selectedId)
      toast('Đã gửi duyệt payroll cho Admin')
      await loadPayroll()
    })

    document.querySelectorAll('[data-approval]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!state.selectedId) return toast('Vui lòng chọn payroll trước')
        await PayrollApi.approve(state.selectedId, { action: btn.dataset.approval })
        toast('Đã cập nhật trạng thái payroll')
        const detail = await PayrollApi.detail(state.selectedId)
        fillAdjustmentForm(detail)
        await loadPayroll()
      })
    })

    document.getElementById('complaintList').addEventListener('click', async (e) => {
      const btn = e.target.closest('button[data-cid]')
      if (!btn) return
      await PayrollApi.handleComplaint(btn.dataset.cid, { action: btn.dataset.action, payroll_status: 'complaint' })
      toast('Đã cập nhật khiếu nại')
      await loadComplaints(); await loadPayroll()
    })

    document.getElementById('btnProcessComplaints').addEventListener('click', () => {
      document.getElementById('complaintList').scrollIntoView({ behavior: 'smooth' })
    })
  } catch (error) {
    toast(error.message)
  }
}

bootstrap()