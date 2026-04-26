async function parseJsonResponse(response) {
  let payload = null
  try {
    payload = await response.json()
  } catch (e) {
    payload = null
  }

  if (!response.ok) {
    const message = payload?.error || payload?.message || 'Request failed'
    throw new Error(message)
  }
  return payload
}

window.ManagerAPI = {
  dashboard: () => fetch('/manager/dashboard').then(parseJsonResponse),
  attendanceToday: () => fetch('/manager/attendance/today').then(parseJsonResponse),
  attendanceMonth: (month, year) =>
    fetch(`/manager/attendance/month?month=${month}&year=${year}`).then(parseJsonResponse),

  leaves: (status = 'pending') =>
    fetch(`/manager/leave?status=${encodeURIComponent(status)}`).then(parseJsonResponse),

  approveLeave: (id, note) =>
    fetch(`/manager/leave/${id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: note || '' })
    }).then(parseJsonResponse),

  rejectLeave: (id, note) =>
    fetch(`/manager/leave/${id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: note || '' })
    }).then(parseJsonResponse),

  reminder: (employeeIds, message) =>
    fetch('/manager/reminder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ employee_ids: employeeIds, message })
    }).then(parseJsonResponse),

  overtimeRequests: () => fetch('/manager/overtime').then(parseJsonResponse),
  reviewOvertime: (id, action, note = '') =>
    fetch(`/manager/overtime/${id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, note })
    }).then(parseJsonResponse),

  contractsExpiring: () => fetch('/manager/contracts/expiring').then(parseJsonResponse),

  renewContract: (payload) =>
    fetch('/manager/contracts/renew', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(parseJsonResponse),

  salary: (month, year) =>
fetch(`/manager/salary?month=${month}&year=${year}`).then(parseJsonResponse),

  departmentPayroll: (params) =>
    fetch(`/manager/payroll/department?${new URLSearchParams(params).toString()}`).then(parseJsonResponse),
  departmentPayrollDetail: (salaryId) =>
    fetch(`/manager/payroll/department/${salaryId}`).then(parseJsonResponse),
  confirmDepartmentPayroll: (salaryId, note = '') =>
    fetch(`/manager/payroll/department/${salaryId}/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note })
    }).then(parseJsonResponse),
  feedbackDepartmentPayroll: (salaryId, payload) =>
    fetch(`/manager/payroll/department/${salaryId}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(parseJsonResponse),
  payrollComplaints: () => fetch('/manager/payroll/complaints').then(parseJsonResponse),
  approvePayrollComplaint: (complaintId) =>
    fetch(`/manager/payroll/complaints/${complaintId}/approve`, { method: 'POST' }).then(parseJsonResponse),
  rejectPayrollComplaint: (complaintId) =>
    fetch(`/manager/payroll/complaints/${complaintId}/reject`, { method: 'POST' }).then(parseJsonResponse),

  selfPayrollHistory: (year) => fetch(`/manager/self-payroll/history?year=${year}`).then(parseJsonResponse),
  selfPayrollDetail: (salaryId) => fetch(`/manager/self-payroll/${salaryId}`).then(parseJsonResponse),
  selfPayrollPdfUrl: (salaryId) => `/manager/self-payroll/${salaryId}/pdf`,
  selfPayrollComplaint: (salaryId, formData) =>
    fetch(`/manager/self-payroll/${salaryId}/complaint`, { method: 'POST', body: formData }).then(parseJsonResponse),
  selfDependents: () => fetch('/manager/self/dependents').then(parseJsonResponse),
  createSelfDependent: (payload) =>
    fetch('/manager/self/dependents', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }).then(parseJsonResponse),
  updateSelfDependent: (id, payload) =>
    fetch(`/manager/self/dependents/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }).then(parseJsonResponse),
  deleteSelfDependent: (id) =>
    fetch(`/manager/self/dependents/${id}`, { method: 'DELETE' }).then(parseJsonResponse)
}