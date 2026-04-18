function money(v) {
  return new Intl.NumberFormat('vi-VN').format(Number(v || 0))
}

function statusLabel(status) {
  const s = (status || '').toLowerCase()
  if (s === 'paid') return '<span class="status paid">✅ Paid</span>'
  if (s === 'pending') return '<span class="status pending">⏳ Pending</span>'
  return `<span class="status">${status}</span>`
}

async function loadSalary() {
  const month = document.getElementById('month').value
  const year = document.getElementById('year').value
  const stateBox = document.getElementById('salary-state')
  const body = document.getElementById('salary-body')

  stateBox.hidden = true
  body.innerHTML = ''

  try {
    const rows = await ManagerAPI.salary(month, year)
    if (!rows.length) {
      stateBox.hidden = false
      stateBox.textContent = 'Không có dữ liệu lương theo bộ lọc.'
      return
    }

    body.innerHTML = rows
      .map(
        (row) => `
      <tr>
        <td>${row.name}</td>
        <td>${money(row.basic_salary)}</td>
        <td>${money(row.allowance)}</td>
        <td>${money(row.net_salary)}</td>
        <td>${statusLabel(row.status)}</td>
      </tr>
    `
      )
      .join('')
  } catch (err) {
    stateBox.hidden = false
    stateBox.textContent = `Không thể tải dữ liệu: ${err.message}`
  }
}

document.getElementById('salary-view').addEventListener('click', loadSalary)