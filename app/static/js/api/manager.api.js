const API = {
  dashboard: () => fetch('/manager/dashboard').then(r => r.json()),
  attendance: () => fetch('/manager/attendance/today').then(r => r.json()),
  leaves: (status) => fetch(`/manager/leave?status=${status || ''}`).then(r => r.json()),

  approve: (id, note) =>
    fetch(`/manager/leave/${id}/approve`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({note})
    }),

  reject: (id, note) =>
    fetch(`/manager/leave/${id}/reject`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({note})
    }),

  reminder: (ids) =>
    fetch(`/manager/reminder`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({employee_ids: ids})
    }),

  contracts: () => fetch('/manager/contracts/expiring').then(r => r.json()),

  renew: (data) =>
    fetch('/manager/contracts/renew', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    }),

  salary: (m,y) => fetch(`/manager/salary?month=${m}&year=${y}`).then(r => r.json())
}