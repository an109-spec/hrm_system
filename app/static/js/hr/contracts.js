const ContractApi = {
  async request(url, options = {}) {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.error || 'Có lỗi xảy ra trong quá trình xử lý hợp đồng')
    }
    return data
  },
  getMeta() {
    return this.request('/hr/api/meta')
  },
  getEmployees() {
    return this.request('/hr/api/employees')
  },
  getContracts(params) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/hr/api/contracts?${query}`)
  },
  getContractDetail(contractId) {
    return this.request(`/hr/api/contracts/${contractId}`)
  },
  createContract(payload) {
    return this.request('/hr/api/contracts', { method: 'POST', body: JSON.stringify(payload) })
  },
  updateContract(contractId, payload) {
    return this.request(`/hr/api/contracts/${contractId}`, { method: 'PUT', body: JSON.stringify(payload) })
  },
  extendContract(contractId, payload) {
    return this.request(`/hr/api/contracts/${contractId}/extend`, { method: 'POST', body: JSON.stringify(payload) })
  },
  terminateContract(contractId, payload) {
    return this.request(`/hr/api/contracts/${contractId}/terminate`, { method: 'POST', body: JSON.stringify(payload) })
  },
  getReminders() {
    return this.request('/hr/api/contracts/reminders')
  }
}

const state = {
  contracts: [],
  reminders: [],
  employees: [],
  editingContractId: null
}

const CURRENCY_FORMATTER = new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 })

function formatDate(value) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('vi-VN')
}

function formatMoney(value) {
  return CURRENCY_FORMATTER.format(Number(value || 0))
}

function showToast(message) {
  const toast = document.getElementById('hrToast')
  toast.textContent = message
  toast.hidden = false
  clearTimeout(showToast.timer)
  showToast.timer = setTimeout(() => {
    toast.hidden = true
  }, 2800)
}

function fillFilterOptions() {
  const statusFilter = document.getElementById('statusFilter')
  const typeFilter = document.getElementById('typeFilter')

  statusFilter.innerHTML = [
    { value: 'all', label: 'Tất cả' },
    { value: 'expiring', label: 'Sắp hết hạn' },
    { value: 'active', label: 'Đang hiệu lực' },
    { value: 'expired', label: 'Đã hết hạn' }
  ].map((item) => `<option value="${item.value}">${item.label}</option>`).join('')

  typeFilter.innerHTML = [
    { value: 'all', label: 'Tất cả' },
    { value: 'trial', label: 'Thử việc' },
    { value: 'official', label: 'Chính thức' },
    { value: 'internship', label: 'Thực tập' },
    { value: 'seasonal', label: 'Thời vụ' }
  ].map((item) => `<option value="${item.value}">${item.label}</option>`).join('')
}

function renderSummary(summary) {
  const target = document.getElementById('summaryStrip')
  target.innerHTML = `
    <div class="summary-box"><strong>${summary.total || 0}</strong><span>Tổng hợp đồng</span></div>
    <div class="summary-box"><strong>${summary.active || 0}</strong><span>Đang hiệu lực</span></div>
    <div class="summary-box"><strong>${summary.expiring || 0}</strong><span>Sắp hết hạn</span></div>
    <div class="summary-box"><strong>${summary.expired || 0}</strong><span>Đã hết hạn</span></div>
  `
}

function renderContracts() {
  const body = document.getElementById('contractTableBody')
  body.innerHTML = state.contracts.map((contract) => `
    <tr>
      <td>${contract.employee_code}</td>
      <td>${contract.employee_name}</td>
      <td>${contract.contract_type_label}</td>
      <td>${formatDate(contract.start_date)}</td>
      <td>${formatDate(contract.end_date)}</td>
      <td><span class="badge ${contract.contract_status}">${contract.contract_status_label}</span></td>
      <td>${formatMoney(contract.basic_salary)}</td>
      <td>${formatMoney(contract.allowance)}</td>
      <td>
        <div class="action-group">
          <button class="btn" data-action="view" data-id="${contract.id}">Xem chi tiết</button>
          <button class="btn" data-action="edit" data-id="${contract.id}">Chỉnh sửa</button>
          <button class="btn" data-action="extend" data-id="${contract.id}">Gia hạn</button>
          <button class="btn" data-action="terminate" data-id="${contract.id}">Kết thúc</button>
        </div>
      </td>
    </tr>
  `).join('')
}

function renderReminders(summary, reminders) {
  const stats = document.getElementById('reminderStats')
  stats.innerHTML = `
    <div class="reminder-stat critical"><strong>${summary.critical || 0}</strong>Critical</div>
    <div class="reminder-stat warning"><strong>${summary.warning || 0}</strong>Warning</div>
    <div class="reminder-stat info"><strong>${summary.info || 0}</strong>Info</div>
  `

  const list = document.getElementById('reminderList')
  list.innerHTML = reminders.map((item) => `
    <li class="reminder-item ${item.level}">
      <p><strong>${item.employee_name}</strong> (${item.employee_code})</p>
      <p>${item.message}</p>
      <p class="meta">Mức: ${item.level.toUpperCase()}${item.days_left != null ? ` • Còn ${item.days_left} ngày` : ''}</p>
    </li>
  `).join('')

  if (!reminders.length) {
    list.innerHTML = '<li class="reminder-item info"><p>Không có nhắc lịch nào trong thời điểm hiện tại.</p></li>'
  }
}

function renderEmployeeSelect(employees) {
  const select = document.getElementById('employeeSelect')
  select.innerHTML = '<option value="">Chọn nhân viên</option>' + employees.map((employee) => (
    `<option value="${employee.id}">${employee.employee_code} - ${employee.full_name}</option>`
  )).join('')
}

function collectFilters() {
  return {
    search: document.getElementById('searchInput').value.trim(),
    contract_status: document.getElementById('statusFilter').value,
    contract_type: document.getElementById('typeFilter').value
  }
}

function collectFormPayload() {
  return {
    employee_id: Number(document.getElementById('employeeSelect').value),
    contract_type: document.getElementById('contractType').value,
    basic_salary: Number(document.getElementById('basicSalary').value || 0),
    start_date: document.getElementById('startDate').value,
    end_date: document.getElementById('endDate').value || null,
    note: document.getElementById('note').value || null
  }
}

function resetForm() {
  state.editingContractId = null
  document.getElementById('formTitle').textContent = 'Tạo hợp đồng mới'
  document.getElementById('btnSubmitForm').textContent = 'Lưu hợp đồng'
  document.getElementById('contractId').value = ''
  document.getElementById('contractForm').reset()
}

async function loadContracts() {
  const response = await ContractApi.getContracts(collectFilters())
  state.contracts = response.items || []
  renderSummary(response.summary || {})
  renderContracts()
}

async function loadReminders() {
  const response = await ContractApi.getReminders()
  state.reminders = response.items || []
  renderReminders(response.summary || {}, state.reminders)
}

async function enterEditMode(contractId) {
  const detail = await ContractApi.getContractDetail(contractId)
  state.editingContractId = detail.id

  document.getElementById('formTitle').textContent = `Chỉnh sửa hợp đồng ${detail.contract_code}`
  document.getElementById('btnSubmitForm').textContent = 'Cập nhật hợp đồng'

  document.getElementById('contractId').value = detail.id
  document.getElementById('employeeSelect').value = detail.employee_id
  document.getElementById('employeeSelect').disabled = true
  document.getElementById('contractType').value = detail.contract_type || 'official'
  document.getElementById('basicSalary').value = detail.basic_salary || 0
  document.getElementById('startDate').value = detail.start_date || ''
  document.getElementById('endDate').value = detail.end_date || ''
  document.getElementById('note').value = detail.note || ''

  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
}

async function handleTableAction(action, contractId) {
  if (action === 'view') {
    const detail = await ContractApi.getContractDetail(contractId)
    showToast(`${detail.contract_code} • ${detail.employee_name} • ${detail.contract_status_label}`)
    return
  }

  if (action === 'edit') {
    await enterEditMode(contractId)
    return
  }

  if (action === 'extend') {
    const endDate = window.prompt('Nhập ngày gia hạn mới (YYYY-MM-DD):')
    if (!endDate) return
    const result = await ContractApi.extendContract(contractId, { end_date: endDate })
    showToast(result.message)
    await Promise.all([loadContracts(), loadReminders()])
    return
  }

  if (action === 'terminate') {
    const confirmed = window.confirm('Bạn chắc chắn muốn kết thúc hợp đồng này?')
    if (!confirmed) return
    const endDate = window.prompt('Ngày kết thúc (YYYY-MM-DD). Bỏ trống để dùng ngày hôm nay:')
    const result = await ContractApi.terminateContract(contractId, { end_date: endDate || null })
    showToast(result.message)
    await Promise.all([loadContracts(), loadReminders()])
  }
}

function bindEvents() {
  document.getElementById('searchInput').addEventListener('input', () => {
    loadContracts().catch((error) => showToast(error.message))
  })

  document.getElementById('statusFilter').addEventListener('change', () => {
    loadContracts().catch((error) => showToast(error.message))
  })

  document.getElementById('typeFilter').addEventListener('change', () => {
    loadContracts().catch((error) => showToast(error.message))
  })

  document.getElementById('contractTableBody').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]')
    if (!button) return
    const action = button.dataset.action
    const contractId = Number(button.dataset.id)
    handleTableAction(action, contractId).catch((error) => showToast(error.message))
  })

  document.getElementById('contractForm').addEventListener('submit', async (event) => {
    event.preventDefault()
    const payload = collectFormPayload()

    try {
      if (!payload.employee_id && !state.editingContractId) {
        showToast('Vui lòng chọn nhân viên để tạo hợp đồng')
        return
      }

      if (state.editingContractId) {
        const result = await ContractApi.updateContract(state.editingContractId, {
          contract_type: payload.contract_type,
          basic_salary: payload.basic_salary,
          start_date: payload.start_date,
          end_date: payload.end_date,
          note: payload.note
        })
        showToast(result.message)
      } else {
        const result = await ContractApi.createContract(payload)
        showToast(`${result.message} (${result.contract_code})`)
      }

      document.getElementById('employeeSelect').disabled = false
      resetForm()
      await Promise.all([loadContracts(), loadReminders()])
    } catch (error) {
      showToast(error.message)
    }
  })

  document.getElementById('btnSwitchCreate').addEventListener('click', () => {
    document.getElementById('employeeSelect').disabled = false
    resetForm()
  })

  document.getElementById('btnCreateContract').addEventListener('click', () => {
    document.getElementById('employeeSelect').disabled = false
    resetForm()
    document.getElementById('employeeSelect').focus()
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
  })

  document.getElementById('btnRefreshReminder').addEventListener('click', () => {
    loadReminders().catch((error) => showToast(error.message))
  })
}

async function bootstrap() {
  try {
    fillFilterOptions()
    const [employees] = await Promise.all([ContractApi.getEmployees()])
    state.employees = employees || []
    renderEmployeeSelect(state.employees)
    await Promise.all([loadContracts(), loadReminders()])
    bindEvents()
  } catch (error) {
    showToast(error.message)
  }
}

bootstrap()