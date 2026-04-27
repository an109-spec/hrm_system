const HRApi = {
  async request(url, options = {}) {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.error || 'Đã có lỗi xảy ra')
    }
    return data
  },
  getMeta() {
    return this.request('/hr/api/meta')
  },
  getEmployees(params) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/hr/api/employees?${query}`)
  },
  getEmployeeDetail(employeeId) {
    return this.request(`/hr/api/employees/${employeeId}`)
  },
  createEmployee(payload) {
    return this.request('/hr/api/employees', { method: 'POST', body: JSON.stringify(payload) })
  },
  updateEmployee(employeeId, payload) {
    return this.request(`/hr/api/employees/${employeeId}`, { method: 'PUT', body: JSON.stringify(payload) })
  },
  createContract(payload) {
    return this.request('/hr/api/contracts', { method: 'POST', body: JSON.stringify(payload) })
  },
  updateAccountStatus(employeeId, isActive) {
    return this.request(`/hr/api/accounts/${employeeId}/status`, { method: 'PATCH', body: JSON.stringify({ is_active: isActive }) })
  },
  listResignations(status = '') {
    const query = status ? `?status=${encodeURIComponent(status)}` : ''
    return this.request(`/hr/api/resignations${query}`)
  },
  processResignation(requestId, payload) {
    return this.request(`/hr/api/resignations/${requestId}/process`, { method: 'POST', body: JSON.stringify(payload) })
  },
}

const state = {
  meta: { departments: [], positions: [], managers: [] },
  employees: [],
  selectedEmployee: null
}

const STATUS_LABELS = {
  active: 'Đang làm',
  probation: 'Thử việc',
  on_leave: 'Nghỉ phép',
  pending_resignation: 'Chờ nghỉ việc',
  resigned: 'Đã nghỉ việc',
  inactive: 'Inactive',
  terminated: 'Chấm dứt',
  retired: 'Nghỉ hưu'
}

function showToast(message) {
  const toast = document.getElementById('hrToast')
  toast.textContent = message
  toast.hidden = false
  clearTimeout(showToast.timer)
  showToast.timer = setTimeout(() => {
    toast.hidden = true
  }, 2500)
}

function fillSelect(node, list, placeholder = 'Tất cả') {
  if (!node) return
  node.innerHTML = `<option value="">${placeholder}</option>${list.map((item) => `<option value="${item.id}">${item.name}</option>`).join('')}`
}

function renderEmployeeTable() {
  const body = document.getElementById('employeeTableBody')
  body.innerHTML = state.employees.map((emp) => `
    <tr>
      <td>${emp.employee_code}</td>
      <td>${emp.full_name || '--'}</td>
      <td>${emp.email || '--'}</td>
      <td>${emp.phone || '--'}</td>
      <td>${emp.department || '--'}</td>
      <td>${emp.position || '--'}</td>
      <td>${emp.username || '--'}</td>
      <td><span class="badge ${emp.working_status}">${STATUS_LABELS[emp.working_status] || emp.working_status}</span></td>
      <td><span class="badge ${emp.account_status}">${emp.account_status === 'active' ? 'Hoạt động' : 'Ngưng hoạt động'}</span></td>
      <td>
        <button class="btn" data-action="view" data-id="${emp.id}">Xem chi tiết</button>
        <button class="btn" data-action="edit" data-id="${emp.id}">Chỉnh sửa</button>
      </td>
    </tr>
  `).join('')
}

function renderDetail(detail) {
  const avatar = document.getElementById('detailAvatar')
  avatar.textContent = detail.full_name?.[0] || 'N'

  const rows = [
    ['Họ tên', detail.full_name],
    ['Tuổi', detail.age],
    ['Giới tính', detail.gender],
    ['SĐT', detail.phone],
    ['Email', detail.email],
    ['Địa chỉ', detail.address],
    ['Phòng ban', detail.department],
    ['Chức vụ', detail.position],
    ['Manager', detail.manager],
    ['Ngày vào làm', detail.hire_date],
    ['Loại hợp đồng', detail.employment_type],
    ['Ngày bắt đầu', detail.contract?.start_date],
    ['Ngày kết thúc', detail.contract?.end_date],
    ['Lương cơ bản', detail.contract?.basic_salary],
    ['Phụ cấp', '--']
  ]

  const grid = document.getElementById('employeeDetailGrid')
  grid.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v || '--'}</dd>`).join('')

  document.getElementById('quickEmployeeId').value = detail.id
  document.getElementById('quickFullName').value = detail.full_name || ''
  document.getElementById('quickPhone').value = detail.phone || ''
  document.getElementById('quickAddress').value = detail.address || ''
  document.getElementById('quickDepartment').value = detail.department_id || ''
  document.getElementById('quickPosition').value = detail.position_id || ''
  document.getElementById('quickManager').value = detail.manager_id || ''
  document.getElementById('quickStatus').value = detail.working_status || 'active'

  document.getElementById('contractCode').value = detail.contract?.contract_code || 'Tự động khi lưu'
  document.getElementById('contractHint').textContent = `Đang tạo hợp đồng cho: ${detail.full_name}`
  document.getElementById('contractForm').dataset.employeeId = String(detail.id)
  state.selectedEmployee = detail
}

async function loadEmployees() {
  const params = {
    search: document.getElementById('searchInput').value.trim(),
    department_id: document.getElementById('departmentFilter').value,
    position_id: document.getElementById('positionFilter').value,
    working_status: document.getElementById('statusFilter').value
  }
  const data = await HRApi.getEmployees(params)
  state.employees = data
  renderEmployeeTable()
}

async function loadMeta() {
  state.meta = await HRApi.getMeta()
  fillSelect(document.getElementById('departmentFilter'), state.meta.departments)
  fillSelect(document.getElementById('positionFilter'), state.meta.positions)

  fillSelect(document.getElementById('quickDepartment'), state.meta.departments, 'Chọn phòng ban')
  fillSelect(document.getElementById('quickPosition'), state.meta.positions, 'Chọn chức danh')
  fillSelect(document.getElementById('quickManager'), state.meta.managers, 'Chọn quản lý')

  fillSelect(document.getElementById('newDepartment'), state.meta.departments, 'Chọn phòng ban')
  fillSelect(document.getElementById('newPosition'), state.meta.positions, 'Chọn chức danh')
  fillSelect(document.getElementById('newManager'), state.meta.managers, 'Chọn quản lý')
}

async function handleCreateEmployee(saveAndContinue = false) {
  const payload = {
    full_name: document.getElementById('newFullName').value,
    dob: document.getElementById('newDob').value,
    gender: document.getElementById('newGender').value,
    phone: document.getElementById('newPhone').value,
    address: document.getElementById('newAddress').value,
    department_id: Number(document.getElementById('newDepartment').value) || null,
    position_id: Number(document.getElementById('newPosition').value) || null,
    manager_id: Number(document.getElementById('newManager').value) || null,
    hire_date: document.getElementById('newHireDate').value || null,
    employment_type: document.getElementById('newEmploymentType').value,
    create_account: document.getElementById('createAccount').checked,
    username: document.getElementById('newUsername').value || null,
    email: document.getElementById('newEmail').value || null,
    password: document.getElementById('newPassword').value || null
  }

  const result = await HRApi.createEmployee(payload)
  showToast(result.message)

  if (document.getElementById('createContractNow').checked) {
    const contractPayload = {
      employee_id: result.id,
      basic_salary: Number(document.getElementById('basicSalary').value) || 0,
      start_date: document.getElementById('contractStart').value,
      end_date: document.getElementById('contractEnd').value || null,
      contract_type: document.getElementById('contractType').value || null,
      note: document.getElementById('contractNote').value || null
    }
    await HRApi.createContract(contractPayload)
    showToast('Đã tạo nhân viên và hợp đồng')
  }

  await loadEmployees()
  if (!saveAndContinue) {
    document.getElementById('createEmployeeForm').reset()
  }
}

function bindEvents() {
  document.getElementById('searchInput').addEventListener('input', () => loadEmployees().catch((e) => showToast(e.message)))
  ;['departmentFilter', 'positionFilter', 'statusFilter'].forEach((id) => {
    document.getElementById(id).addEventListener('change', () => loadEmployees().catch((e) => showToast(e.message)))
  })

  document.getElementById('employeeTableBody').addEventListener('click', async (event) => {
    const button = event.target.closest('button[data-action]')
    if (!button) return
    const employeeId = Number(button.dataset.id)
    if (!employeeId) return
    const detail = await HRApi.getEmployeeDetail(employeeId)
    renderDetail(detail)
  })

  document.getElementById('quickEditForm').addEventListener('submit', async (event) => {
    event.preventDefault()
    const employeeId = Number(document.getElementById('quickEmployeeId').value)
    if (!employeeId) return showToast('Vui lòng chọn nhân viên')

    const payload = {
      full_name: document.getElementById('quickFullName').value,
      phone: document.getElementById('quickPhone').value,
      address: document.getElementById('quickAddress').value,
      department_id: Number(document.getElementById('quickDepartment').value) || null,
      position_id: Number(document.getElementById('quickPosition').value) || null,
      manager_id: Number(document.getElementById('quickManager').value) || null,
      working_status: document.getElementById('quickStatus').value
    }

    const result = await HRApi.updateEmployee(employeeId, payload)
    showToast(result.message)
    await loadEmployees()
  })

  document.getElementById('btnDeactivate').addEventListener('click', async () => {
    const employeeId = Number(document.getElementById('quickEmployeeId').value)
    if (!employeeId || !state.selectedEmployee) return showToast('Vui lòng chọn nhân viên')

    const nextIsActive = !state.selectedEmployee.account.is_active
    const result = await HRApi.updateAccountStatus(employeeId, nextIsActive)
    state.selectedEmployee.account.is_active = result.is_active
    showToast(result.message)
    await loadEmployees()
  })

  document.getElementById('createEmployeeForm').addEventListener('submit', async (event) => {
    event.preventDefault()
    await handleCreateEmployee(false)
  })

  document.getElementById('btnSaveAndContinue').addEventListener('click', async () => {
    await handleCreateEmployee(true)
  })

  document.getElementById('contractForm').addEventListener('submit', async (event) => {
    event.preventDefault()
    const employeeId = Number(document.getElementById('contractForm').dataset.employeeId)
    if (!employeeId) return showToast('Chưa chọn nhân viên để tạo hợp đồng')

    const payload = {
      employee_id: employeeId,
      basic_salary: Number(document.getElementById('basicSalary').value) || 0,
      start_date: document.getElementById('contractStart').value,
      end_date: document.getElementById('contractEnd').value || null,
      contract_type: document.getElementById('contractType').value || null,
      note: document.getElementById('contractNote').value || null
    }
    const result = await HRApi.createContract(payload)
    document.getElementById('contractCode').value = result.contract_code
    showToast(result.message)
  })

  document.getElementById('btnCreateEmployee').addEventListener('click', () => {
    document.getElementById('newFullName').focus()
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
  })
}

async function bootstrap() {
  try {
    await loadMeta()
    await loadEmployees()
    bindEvents()
  } catch (error) {
    showToast(error.message)
  }
}

bootstrap()
async function openResignationQueue() {
  const rows = await HRApi.listResignations('pending_hr')
  if (!rows.length) {
    await Swal.fire({ icon: 'info', title: 'Không có hồ sơ offboarding chờ HR xử lý' })
    return
  }
  const html = rows.map((row) => `<div style="text-align:left;padding:10px;border:1px solid #ddd;margin-bottom:10px"><b>${row.employee_name}</b><br>Ngày nghỉ dự kiến: ${row.expected_last_day}<br>Lý do: ${row.reason_text || row.reason_category}<br><button class="btn btn-primary" data-hr-resignation="forward_admin" data-id="${row.id}">Xử lý xong & chuyển Admin</button> <button class="btn btn-ghost" data-hr-resignation="reject" data-id="${row.id}">Từ chối</button></div>`).join('')
  await Swal.fire({ title: 'HR Offboarding Queue', html, width: 900, showConfirmButton: false })
}

document.addEventListener('click', async (event) => {
  const btn = event.target.closest('button[data-hr-resignation]')
  if (!btn) return
  const action = btn.dataset.hrResignation
  const requestId = Number(btn.dataset.id)
  const { value, isConfirmed } = await Swal.fire({
    title: action === 'forward_admin' ? 'Chốt offboarding và chuyển Admin?' : 'Từ chối resignation?',
    html: action === 'forward_admin' ? `
      <textarea id="hr-note" class="swal2-textarea" placeholder="Ghi chú HR"></textarea>
      <textarea id="hr-payroll" class="swal2-textarea" placeholder="Final payroll"></textarea>
      <textarea id="hr-attendance" class="swal2-textarea" placeholder="Final attendance"></textarea>
      <textarea id="hr-leave" class="swal2-textarea" placeholder="Leave balance"></textarea>
      <textarea id="hr-insurance" class="swal2-textarea" placeholder="Insurance"></textarea>
      <textarea id="hr-asset" class="swal2-textarea" placeholder="Asset handover"></textarea>` : '<textarea id="hr-note" class="swal2-textarea" placeholder="Lý do từ chối"></textarea>',
    showCancelButton: true,
    preConfirm: () => ({
      hr_note: document.getElementById('hr-note')?.value || '',
      final_payroll_note: document.getElementById('hr-payroll')?.value || '',
      final_attendance_note: document.getElementById('hr-attendance')?.value || '',
      leave_balance_note: document.getElementById('hr-leave')?.value || '',
      insurance_note: document.getElementById('hr-insurance')?.value || '',
      asset_handover_note: document.getElementById('hr-asset')?.value || ''
    })
  })
  if (!isConfirmed) return
  const payload = { action, ...(value || {}) }
  try {
    const result = await HRApi.processResignation(requestId, payload)
    await Swal.fire({ icon: 'success', title: result.message || 'Đã xử lý offboarding' })
  } catch (err) {
    await Swal.fire({ icon: 'error', title: err.message || 'Không thể xử lý offboarding' })
  }
})

document.getElementById('btnLoadResignationQueue')?.addEventListener('click', () => {
  openResignationQueue().catch((e) => Swal.fire({ icon: 'error', title: e.message }))
})