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

  contractsExpiring: () => fetch('/manager/contracts/expiring').then(parseJsonResponse),

  renewContract: (payload) =>
    fetch('/manager/contracts/renew', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(parseJsonResponse),

  salary: (month, year) =>
    fetch(`/manager/salary?month=${month}&year=${year}`).then(parseJsonResponse)
}