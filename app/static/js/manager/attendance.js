let allRows = []
let activeFilter = 'ALL'
const SHARED_SIM_TIME_KEY = 'hrm_simulated_now'
const managerAttendanceState = {
  hasAttendance: false,
  hasCheckedOut: false
}
let managerQRScanner = null
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

function toLocalISO(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${String(date.getMilliseconds()).padStart(3, '0')}`
}

function getNow() {
  return readSharedSimTime(new Date())
}

function renderManagerClock() {
  const el = document.getElementById('manager-clock')
  if (!el) return
  const now = getNow()
  el.textContent = `${now.toLocaleTimeString('vi-VN')} - ${now.toLocaleDateString('vi-VN')}`
}

function updateManagerAttendanceButton() {
  const btn = document.getElementById('manager-attendance-btn')
  if (!btn) return
  if (!managerAttendanceState.hasAttendance) {
    btn.textContent = '🔳 QUÉT QR CHECK-IN'
    return
  }
  if (!managerAttendanceState.hasCheckedOut) {
    btn.textContent = '🔳 QUÉT QR CHECK-OUT'
    return
  }
  btn.textContent = '✅ ĐÃ HOÀN THÀNH CHẤM CÔNG'
  btn.disabled = true
}

async function refreshManagerAttendanceState() {
  const now = getNow()
  const month = now.getMonth() + 1
  const year = now.getFullYear()
  const result = await ManagerAPI.attendanceMonth(month, year)
  const todayKey = now.toISOString().slice(0, 10)
  const todayRow = (result || []).find((row) => row.date === todayKey)
  managerAttendanceState.hasAttendance = Boolean(todayRow && todayRow.check_in)
  managerAttendanceState.hasCheckedOut = Boolean(todayRow && todayRow.check_out)
  updateManagerAttendanceButton()
}

async function submitManagerAttendance(qrText, options = {}) {
  const now = getNow()
  const payload = {
    qr_text: qrText,
    simulated_now: toLocalISO(now),
    ...options
  }
  const response = await fetch('/employee/attendance/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.message || 'Không thể chấm công.')
  }
  if (data.action === 'confirm_overtime') {
    const confirmOT = window.confirm(data.message || 'Bạn có muốn đăng ký tăng ca không?')
    if (confirmOT) {
      return submitManagerAttendance(qrText, { overtime_confirmed: true })
    }
    return submitManagerAttendance(qrText, { overtime_rejected: true })
  }
  return data
}

function initManagerAttendanceAction() {
  const btn = document.getElementById('manager-attendance-btn')
  const closeBtn = document.getElementById('manager-close-qr')
  if (!btn || !window.HRMQRScanner) return

  managerQRScanner = window.HRMQRScanner.createQRScanner({
    modalId: 'manager-qr-modal',
    readerId: 'manager-qr-reader',
    onDecoded: async (decodedText) => {
      const data = await submitManagerAttendance(decodedText || 'manager-self-attendance')
      window.alert(data.message || 'Chấm công thành công.')
      await refreshManagerAttendanceState()
      await loadAttendance()
    },
    onError: (err) => {
      window.alert(err?.message || 'Lỗi quét QR.')
    }
  })

  btn.addEventListener('click', async () => {
    if (btn.disabled) return
    try {
      await managerQRScanner.open()
    } catch (err) {
      window.alert(err?.message || 'Không thể mở camera.')
    }
  })

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      if (managerQRScanner) managerQRScanner.close()
    })
  }
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
    alert('Không có nhân viên vắng để nhắc nhở.')
    return
  }

  await ManagerAPI.reminder(
    ids,
    'Chào bạn, bạn chưa thực hiện chấm công check-in hôm nay. Vui lòng kiểm tra lại thiết bị hoặc báo quản lý nếu có sai sót.'
  )
  alert('Đã gửi nhắc nhở')
})

loadAttendance()
renderManagerClock()
setInterval(renderManagerClock, 1000)
initManagerAttendanceAction()
refreshManagerAttendanceState().catch(() => {})