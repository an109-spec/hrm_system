let attendanceRows = []
let dashboard = { total: 0, working: 0, on_leave: 0, late: 0, absent: 0 }

function parseMinutesLate(checkIn) {
  if (!checkIn) return 0
  const [hour, minute] = checkIn.split(':').map(Number)
  if (Number.isNaN(hour) || Number.isNaN(minute)) return 0
  const actual = hour * 60 + minute
  const standard = 8 * 60
  return Math.max(0, actual - standard)
}

function formatLateText(row) {
  const lateMinutes = parseMinutesLate(row.check_in)
  if (!lateMinutes) return `Muộn (Vào lúc ${row.check_in || '--:--'})`
  return `Muộn ${lateMinutes}p (Vào lúc ${row.check_in || '--:--'})`
}

function renderQuickList(type) {
  const panel = document.getElementById('quick-action-panel')
  const title = document.getElementById('quick-action-title')
  const list = document.getElementById('quick-action-list')

  if (type === 'LATE') {
    const lateRows = attendanceRows.filter((row) => row.status === 'LATE')
    title.textContent = '[ 🟡 DANH SÁCH ĐI MUỘN HÔM NAY ]'
    if (!lateRows.length) {
      list.innerHTML = '<p>Không có nhân viên đi muộn hôm nay.</p>'
      panel.hidden = false
      return
    }

    list.innerHTML = lateRows
      .map(
        (row) => `
          <div class="quick-item">
            <span><strong>${row.name}</strong>: ${formatLateText(row)}</span>
            <button class="btn-action" data-action="remind" data-id="${row.employee_id}">💬 Nhắc nhở</button>
          </div>
        `
      )
      .join('')
    panel.hidden = false
    return
  }

  if (type === 'ABSENT') {
    const absentRows = attendanceRows.filter((row) => row.status === 'ABSENT')
    title.textContent = '[ 🔴 DANH SÁCH VẮNG MẶT ]'
    if (!absentRows.length) {
      list.innerHTML = '<p>Không có nhân viên vắng mặt hôm nay.</p>'
      panel.hidden = false
      return
    }

    list.innerHTML = absentRows
      .map((row) => {
        const telHref = row.phone ? `tel:${row.phone}` : '#'
        return `
          <div class="quick-item">
            <span><strong>${row.name}</strong>: Chưa Check-in</span>
            <div class="quick-actions-inline">
              <a class="btn-action ${row.phone ? '' : 'disabled'}" href="${telHref}">📞 Gọi điện</a>
              <button class="btn-action" data-action="notify" data-id="${row.employee_id}">🔔 Gửi thông báo</button>
            </div>
          </div>
        `
      })
      .join('')
    panel.hidden = false
    return
  }

  if (type === 'LEAVE') {
    const leaveRows = attendanceRows.filter((row) => row.status === 'LEAVE')
    title.textContent = '[ 🌴 DANH SÁCH ĐANG NGHỈ PHÉP ]'
    list.innerHTML = leaveRows.length
      ? leaveRows.map((row) => `<div class="quick-item"><span><strong>${row.name}</strong>: Đang nghỉ phép</span></div>`).join('')
      : '<p>Không có nhân viên nghỉ phép hôm nay.</p>'
    panel.hidden = false
    return
  }

  const presentRows = attendanceRows.filter((row) => row.status === 'ON_TIME' || row.status === 'PRESENT')
  title.textContent = '[ 🟢 DANH SÁCH ĐANG LÀM VIỆC ]'
  list.innerHTML = presentRows.length
    ? presentRows.map((row) => `<div class="quick-item"><span><strong>${row.name}</strong>: Vào lúc ${row.check_in || '--:--'}</span></div>`).join('')
    : '<p>Không có dữ liệu nhân viên đang làm việc.</p>'
  panel.hidden = false
}

function renderSummary() {
  const body = document.getElementById('status-summary-body')
  const total = dashboard.total || attendanceRows.length || 1
  const presentCount = Math.max(0, (dashboard.working || 0) - (dashboard.late || 0))
  const lateCount = dashboard.late || 0
  const absentCount = dashboard.absent || 0
  const leaveCount = dashboard.on_leave || 0

  const items = [
    {
      key: 'PRESENT',
      label: '🟢 Đang làm việc',
      count: presentCount,
      ratio: `${Math.round((presentCount / total) * 100)}%`,
      actionLabel: '👁️ Xem danh sách',
      actionType: 'view'
    },
    {
      key: 'LATE',
      label: '🟡 Đi muộn / Về sớm',
      count: lateCount,
      ratio: `${Math.round((lateCount / total) * 100)}%`,
      actionLabel: '⚠️ Xử lý ngay',
      actionType: 'handle'
    },
    {
      key: 'ABSENT',
      label: '🔴 Vắng mặt (Không lý do)',
      count: absentCount,
      ratio: `${Math.round((absentCount / total) * 100)}%`,
      actionLabel: '🔔 Nhắc nhở',
      actionType: 'handle'
    },
    {
      key: 'LEAVE',
      label: '🌴 Đang nghỉ phép',
      count: leaveCount,
      ratio: '--',
      actionLabel: '📋 Xem đơn',
      actionType: 'view'
    }
  ]

  body.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>${item.label}</td>
          <td>${item.count}</td>
          <td>${item.ratio}</td>
          <td><button class="btn-action" data-type="${item.key}" data-action-type="${item.actionType}">${item.actionLabel}</button></td>
        </tr>
      `
    )
    .join('')
}

async function notifyEmployee(employeeId) {
  await ManagerAPI.reminder([employeeId], 'Quản lý nhắc nhở: bạn đang có bất thường chấm công hôm nay, vui lòng phản hồi sớm.')
  alert('Đã gửi thông báo nhắc nhở')
}

async function bootstrap() {
  const errorNode = document.getElementById('dept-emp-error')
  try {
    const [attendanceData, dashboardData] = await Promise.all([
      ManagerAPI.attendanceToday(),
      ManagerAPI.dashboard()
    ])
    attendanceRows = attendanceData || []
    dashboard = dashboardData || dashboard
    renderSummary()
  } catch (err) {
    errorNode.hidden = false
    errorNode.textContent = `Lỗi tải dữ liệu: ${err.message}`
  }
}

document.addEventListener('click', async (event) => {
  const actionButton = event.target.closest('button[data-type]')
  if (actionButton) {
    const type = actionButton.dataset.type
    renderQuickList(type)
    return
  }

  const notifyButton = event.target.closest('button[data-action="notify"], button[data-action="remind"]')
  if (notifyButton) {
    const employeeId = Number(notifyButton.dataset.id)
    if (employeeId) {
      await notifyEmployee(employeeId)
    }
  }
})

bootstrap()