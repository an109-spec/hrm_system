let employeeRows = []

function fmtDate(value) {
  if (!value) return '--'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleDateString('vi-VN')
}

function renderCards(summary) {
  const cards = [
    ['Tổng nhân sự', summary.total_employees || 0],
    ['Đang làm việc', summary.active_employees || 0],
    ['Thử việc', summary.probation_employees || 0],
    ['Nghỉ hôm nay', summary.on_leave_today || 0],
    ['Sắp hết hợp đồng', summary.expiring_contracts || 0],
    ['Attendance bất thường', summary.attendance_alerts || 0]
  ]
  document.getElementById('summary-cards').innerHTML = cards
    .map(([label, val]) => `<article class="sum-card"><h4>${label}</h4><p>${val}</p></article>`)
    .join('')
}

function rowActions(employeeId) {
  return `
    <button class="btn-action" data-action="detail" data-id="${employeeId}">Xem chi tiết</button>
    <button class="btn-action btn-light" data-action="promotion" data-id="${employeeId}">Đề xuất thăng chức</button>
    <button class="btn-action btn-light" data-action="transfer" data-id="${employeeId}">Đề xuất điều chuyển</button>
    <button class="btn-action btn-light" data-action="official" data-id="${employeeId}">Đề xuất chuyển chính thức</button>
    <button class="btn-action btn-danger" data-action="termination" data-id="${employeeId}">Đề xuất chấm dứt</button>
  `
}

function renderTable() {
  const body = document.getElementById('employee-table-body')
  if (!employeeRows.length) {
    body.innerHTML = '<tr><td colspan="11">Không có dữ liệu nhân viên trong phạm vi phòng ban.</td></tr>'
    return
  }
  body.innerHTML = employeeRows
    .map((row) => `
      <tr>
        <td>${row.employee_code}</td>
        <td><div class="name-cell">${row.avatar ? `<img src="${row.avatar}" alt="avatar">` : ''}<span>${row.full_name}</span></div></td>
        <td>${row.position}</td>
        <td>${row.department}</td>
        <td>${fmtDate(row.hire_date)}</td>
        <td>${row.contract_type_label}</td>
        <td>${row.working_status_label}</td>
        <td>${row.attendance_today}</td>
        <td>${row.leave_days_month}</td>
        <td>${row.payroll_status_label}</td>
        <td class="actions">${rowActions(row.employee_id)}</td>
      </tr>
    `)
    .join('')
}
function collectFilters() {
  const form = document.getElementById('employee-filter-form')
  const data = new FormData(form)
  const params = {}
  for (const [k, v] of data.entries()) {
    if (typeof v === 'string' && v.trim()) params[k] = v.trim()
  }

  return params
}

function detailHtml(detail) {
  const attendanceRows = (detail.attendance_recent || []).map((r) => `<li>${fmtDate(r.date)} - ${r.status} - In: ${r.check_in ? new Date(r.check_in).toLocaleTimeString('vi-VN') : '--'} - Out: ${r.check_out ? new Date(r.check_out).toLocaleTimeString('vi-VN') : '--'} - OT: ${r.overtime_hours}h</li>`).join('')
  const leaveRows = (detail.leave?.history || []).slice(0, 5).map((r) => `<li>${fmtDate(r.from_date)} → ${fmtDate(r.to_date)} (${r.status})</li>`).join('')
  const complaintRows = (detail.complaints || []).map((r) => `<li>${r.title} - ${r.status}</li>`).join('')
  return `
    <div class="detail-box">
      <p><b>Thông tin cá nhân:</b> ${detail.full_name} (${detail.employee_code})</p>
      <p><b>Contact:</b> ${detail.phone || '--'}</p>
      <p><b>Vị trí:</b> ${detail.position} - ${detail.department}</p>
      <p><b>Contract:</b> ${detail.contract?.contract_code || '--'} | ${fmtDate(detail.contract?.start_date)} - ${fmtDate(detail.contract?.end_date)}</p>
      <p><b>Payroll summary:</b> Basic ${detail.payroll_summary?.basic_salary || 0} | OT review | Allowance ${detail.payroll_summary?.allowance || 0} | Deduction ${detail.payroll_summary?.deduction || 0} | Status ${detail.payroll_summary?.status || '--'}</p>
      <p><b>Performance cơ bản:</b> Attendance warning 30 ngày: ${detail.performance?.attendance_warning_days_30 || 0} | Leave YTD: ${detail.performance?.approved_leave_days_ytd || 0}</p>
      <p><b>Leave:</b> Quota còn ${detail.leave?.remaining_quota || 0} | Đơn chờ xử lý ${detail.leave?.pending_requests || 0}</p>
      <h4>Attendance gần đây</h4>
      <ul>${attendanceRows || '<li>Không có dữ liệu</li>'}</ul>
      <h4>Leave history</h4>
      <ul>${leaveRows || '<li>Không có dữ liệu</li>'}</ul>
      <h4>Cảnh báo / complaint</h4>
      <ul>${complaintRows || '<li>Không có dữ liệu</li>'}</ul>
    </div>
  `
}
async function loadData(params = {}) {
  const [summary, rows] = await Promise.all([
    ManagerAPI.departmentEmployeeSummary(),
    ManagerAPI.departmentEmployeeList(params)
  ])
  employeeRows = rows || []
  renderCards(summary || {})
  renderTable()
}

async function doProposal(employeeId, proposalType, title) {
  const input = await Swal.fire({ title, input: 'textarea', inputLabel: 'Lý do đề xuất', inputPlaceholder: 'Nhập nội dung đề xuất...', showCancelButton: true })
  if (!input.isConfirmed) return
  if (!input.value || !input.value.trim()) {
    await Swal.fire({ icon: 'warning', title: 'Vui lòng nhập lý do đề xuất' })
    return
  }
  await ManagerAPI.createDepartmentEmployeeProposal(employeeId, { proposal_type: proposalType, reason: input.value.trim() })
  await Swal.fire({ icon: 'success', title: 'Đã gửi đề xuất tới HR/Admin' })
}

document.getElementById('employee-filter-form').addEventListener('submit', async (e) => {
  e.preventDefault()
  try {
    await loadData(collectFilters())
  } catch (err) {
    await Swal.fire({ icon: 'error', title: err.message || 'Không tải được dữ liệu nhân viên phòng ban' })
  }
})
document.addEventListener('click', async (e) => {
  const button = e.target.closest('button[data-action]')
  if (!button) return
  const employeeId = Number(button.dataset.id)
  const action = button.dataset.action
  try {
    if (action === 'detail') {
      const detail = await ManagerAPI.departmentEmployeeDetail(employeeId)
      await Swal.fire({ title: 'Hồ sơ nhân viên', html: detailHtml(detail), width: 900, confirmButtonText: 'Đóng' })
      return
    }
    if (action === 'promotion') return doProposal(employeeId, 'promotion', 'Đề xuất thăng chức')
    if (action === 'transfer') return doProposal(employeeId, 'transfer', 'Đề xuất điều chuyển')
    if (action === 'official') return doProposal(employeeId, 'probation_conversion', 'Đề xuất chuyển chính thức')
    if (action === 'termination') return doProposal(employeeId, 'termination', 'Đề xuất chấm dứt')
  } catch (err) {
    await Swal.fire({ icon: 'error', title: err.message || 'Không thể xử lý yêu cầu' })
  }
})

loadData().catch(async (err) => {
  document.getElementById('dept-emp-error').hidden = false
  document.getElementById('dept-emp-error').textContent = err.message || 'Lỗi tải dữ liệu'
  await Swal.fire({ icon: 'error', title: err.message || 'Lỗi tải dữ liệu' })
})