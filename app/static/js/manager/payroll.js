function money(v) {
  return `${new Intl.NumberFormat('vi-VN').format(Number(v || 0))}đ`
}

async function loadSalary() {
  const body = document.getElementById('salary-body')
  const stateBox = document.getElementById('salary-state')
  stateBox.hidden = true
  body.innerHTML = ''
  const params = {
    employee_name: document.getElementById('f-name').value,
    employee_code: document.getElementById('f-code').value,
    month: document.getElementById('month').value,
    year: document.getElementById('year').value,
    status: document.getElementById('f-status').value,
    employment_type: document.getElementById('f-employment').value,
    position: document.getElementById('f-position').value
  }

  try {
    const payload = await ManagerAPI.departmentPayroll(params)
    const rows = payload.items || []
    document.getElementById('sum-total').textContent = money(payload.summary?.total_payroll_fund)
    document.getElementById('sum-calculated').textContent = payload.summary?.calculated_employees || 0
    document.getElementById('sum-pending').textContent = payload.summary?.pending_confirmation || 0
    document.getElementById('sum-complaints').textContent = payload.summary?.complaints || 0
    document.getElementById('sum-abnormal').textContent = payload.summary?.abnormal || 0
    if (!rows.length) {
      stateBox.hidden = false
      stateBox.textContent = 'Không có dữ liệu payroll theo bộ lọc.'
      return
    }

    body.innerHTML = rows
      .map(
        (row) => `<tr>
      <td>${row.employee_code}</td><td>${row.employee_name}</td><td>${row.department}</td><td>${row.position}</td>
      <td>${money(row.basic_salary)}</td><td>${row.actual_work_days}</td><td>${row.leave_days}</td><td>${row.overtime_hours}</td>
      <td>${money(row.allowance)}</td><td>${money(row.deduction)}</td><td>${money(row.insurance)}</td><td>${money(row.tax)}</td>
      <td>${money(row.net_salary)}</td><td><span class="status">${row.status_label}</span></td>
      <td>
        <button onclick="detailPayroll(${row.salary_id})">Chi tiết</button>
        <button onclick="confirmPayroll(${row.salary_id})">Xác nhận</button>
        <button onclick="feedbackPayroll(${row.salary_id})">Phản hồi</button>
      </td>
    </tr>`
      )
      .join('')
    await loadComplaints()
  } catch (err) {
    stateBox.hidden = false
    stateBox.textContent = `Không thể tải dữ liệu: ${err.message}`
  }
}

async function detailPayroll(salaryId) {
  const row = await ManagerAPI.departmentPayrollDetail(salaryId)
  await Swal.fire({
    title: `Chi tiết payroll: ${row.employee_name}`,
    html: `
      <p>Lương cơ bản: <b>${money(row.basic_salary)}</b></p>
      <p>Phụ cấp: <b>${money(row.allowance)}</b></p>
      <p>OT: <b>${money(row.overtime)}</b></p>
      <p>Khấu trừ: <b>${money(row.deduction)}</b></p>
      <p>Bảo hiểm: <b>${money(row.insurance)}</b></p>
      <p>Thuế: <b>${money(row.tax)}</b></p>
      <p>Tổng thực nhận: <b>${money(row.net_salary)}</b></p>
    `
  })
}

async function confirmPayroll(salaryId) {
  const input = await Swal.fire({ title: 'Xác nhận payroll hợp lệ?', input: 'text', inputLabel: 'Ghi chú (tuỳ chọn)', showCancelButton: true })
  if (!input.isConfirmed) return
  await ManagerAPI.confirmDepartmentPayroll(salaryId, input.value || '')
  await Swal.fire({ icon: 'success', title: 'Đã chuyển trạng thái Chờ Admin duyệt' })
  await loadSalary()
}

async function feedbackPayroll(salaryId) {
  const result = await Swal.fire({
    title: 'Gửi phản hồi bất thường về HR',
    html: '<input id="issueType" class="swal2-input" placeholder="Loại lỗi (OT sai/công sai/...)"/><textarea id="issueDesc" class="swal2-textarea" placeholder="Mô tả chi tiết"></textarea>',
    focusConfirm: false,
    showCancelButton: true,
    preConfirm: () => ({
      issue_type: document.getElementById('issueType').value || 'salary_data_error',
      description: document.getElementById('issueDesc').value
    })
  })
  if (!result.isConfirmed) return
  await ManagerAPI.feedbackDepartmentPayroll(salaryId, result.value)
  await Swal.fire({ icon: 'success', title: 'Đã gửi phản hồi cho HR' })
  await loadSalary()
}

async function loadComplaints() {
  const box = document.getElementById('complaint-list')
  const rows = await ManagerAPI.payrollComplaints()
  if (!rows.length) {
    box.innerHTML = '<p>Không có complaint payroll.</p>'
    return
  }
  box.innerHTML = rows.slice(0, 8).map((c) => `<div class="complaint-item">
    <b>${c.employee_name}</b> - ${c.title}<br/>
    <small>${c.description}</small><br/>
    <small>File: ${(c.attachments || []).map((a) => `<a href="${a.url}" target="_blank">${a.name}</a>`).join(', ') || 'Không có'}</small><br/>
    <button onclick="approveComplaint(${c.id})">Approve complaint</button>
    <button onclick="rejectComplaint(${c.id})">Reject complaint</button>
  </div>`).join('')
}

async function approveComplaint(id) {
  const ok = await Swal.fire({ title: 'Xác nhận complaint hợp lý và chuyển HR?', showCancelButton: true })
  if (!ok.isConfirmed) return
  await ManagerAPI.approvePayrollComplaint(id)
  await Swal.fire({ icon: 'success', title: 'Đã chuyển complaint cho HR' })
  await loadComplaints()
}

async function rejectComplaint(id) {
  const ok = await Swal.fire({ title: 'Từ chối complaint không hợp lệ?', showCancelButton: true })
  if (!ok.isConfirmed) return
  await ManagerAPI.rejectPayrollComplaint(id)
  await Swal.fire({ icon: 'success', title: 'Đã từ chối complaint' })
  await loadComplaints()
}

document.getElementById('salary-view').addEventListener('click', loadSalary)
const now = new Date()
document.getElementById('month').value = now.getMonth() + 1
document.getElementById('year').value = now.getFullYear()
loadSalary()