let allRows = []
let activeFilter = 'ALL'
const SHARED_SIM_TIME_KEY = 'hrm_simulated_now'
function formatStatus(status) {
  const map = {
    ON_TIME: '🟢 Đúng giờ',
    PRESENT: '🟢 Đúng giờ',
    LATE: '🟡 Đi muộn',
    ABSENT: '🔴 Vắng mặt',
    LEAVE: '🌴 Nghỉ phép'
  }
  return map[status] || status
}

function getReminderTargets() {
  return allRows.filter((r) => r.status === 'ABSENT').map((r) => r.employee_id)
}
function renderRows() {
  const body = document.getElementById('attendance-body')
  const rows = activeFilter === 'ALL' ? allRows : allRows.filter((r) => r.status === activeFilter)
  body.innerHTML = rows
    .map((row, idx) => `
      <tr>
              <td>${idx + 1}</td>
        <td>${row.name}</td>
        <td>${row.position || '--'}</td>
        <td>${row.check_in || '--:--'}</td>
        <td>${row.check_out || '--:--'}</td>
        <td><span class="status ${row.status}">${formatStatus(row.status)}</span></td>
      </tr>
          `)
    .join('')
}
function updateAlertBox() {
  const alertBox = document.getElementById('attendance-alert')
  const now = new Date()
  const hour = now.getHours()
  const minute = now.getMinutes()
  const absentRows = allRows.filter((row) => row.status === 'ABSENT')

  if ((hour > 9 || (hour === 9 && minute > 0)) && absentRows.length) {
    alertBox.hidden = false
    alertBox.innerHTML = `⚠️ Cảnh báo: có ${absentRows.length} nhân viên chưa check-in sau 09:00.`
  } else {
    alertBox.hidden = true
  }
}
function readSharedSimTime(fallback) {
  try {
    const raw = localStorage.getItem(SHARED_SIM_TIME_KEY)
    if (!raw) return fallback
    const parsed = new Date(raw)
    return Number.isNaN(parsed.getTime()) ? fallback : parsed
  } catch (_) {
    return fallback
  }
}
function getNow() {
  return readSharedSimTime(new Date())
}

async function loadOvertimeRequests() {
  const list = document.getElementById('ot-requests')
  if (!list) return
  const rows = await ManagerAPI.overtimeRequests()
  list.innerHTML = rows.map((r) => `<li>
    <strong>${r.employee_name}</strong> - ${r.overtime_date} (${r.overtime_hours}h)<br>
    Lý do: ${r.reason || '--'}
    <div>
      <button data-ot-action="approve" data-id="${r.id}">Duyệt</button>
      <button data-ot-action="reject" data-id="${r.id}">Từ chối</button>
    </div>
  </li>`).join('') || '<li>Không có yêu cầu OT chờ duyệt.</li>'
}



async function loadAttendance() {
  const sendBtn = document.getElementById('send-reminder')
  sendBtn.disabled = true
  try {
    allRows = await ManagerAPI.attendanceToday()
    renderRows()
    updateAlertBox()
    sendBtn.disabled = getReminderTargets().length === 0
  } catch (err) {
    document.getElementById('attendance-alert').hidden = false
    document.getElementById('attendance-alert').textContent = `Lỗi tải dữ liệu: ${err.message}`
  }
}

document.querySelectorAll('.filters button').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filters button').forEach((node) => node.classList.remove('active'))
    btn.classList.add('active')
    activeFilter = btn.dataset.filter
    renderRows()
  })
  })

document.getElementById('send-reminder').addEventListener('click', async () => {
  const ids = getReminderTargets()
  if (!ids.length) {
    await Swal.fire({ icon: 'info', title: 'Không có nhân viên vắng để nhắc nhở.' })
    return
  }

  await ManagerAPI.reminder(
    ids,
    'Chào bạn, bạn chưa thực hiện chấm công check-in hôm nay. Vui lòng kiểm tra lại thiết bị hoặc báo quản lý nếu có sai sót.'
  )
  await Swal.fire({ icon: 'success', title: 'Đã gửi nhắc nhở' })
})

loadAttendance()
loadOvertimeRequests()
renderManagerClock()
setInterval(renderManagerClock, 1000)

document.addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-ot-action]')
  if (!btn) return
  const action = btn.dataset.otAction
  const id = btn.dataset.id
  let note = ''
  if (action === 'reject') {
    const result = await Swal.fire({ title: 'Lý do từ chối', input: 'text', showCancelButton: true })
    if (!result.isConfirmed) return
    note = result.value || ''
  } else {
    const confirm = await Swal.fire({ icon: 'question', title: 'Duyệt yêu cầu OT này?', showCancelButton: true })
    if (!confirm.isConfirmed) return
  }
  try {
    await ManagerAPI.reviewOvertime(id, action, note)
    await Swal.fire({ icon: 'success', title: 'Xử lý yêu cầu OT thành công' })
    await loadOvertimeRequests()
  } catch (err) {
    await Swal.fire({ icon: 'error', title: err.message })
  }
})