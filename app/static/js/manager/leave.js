let leaveRows = []
let selected = null

function statusText(status) {
  if (status === 'pending') return '🟡 Chờ duyệt'
  if (status === 'approved') return '🟢 Đã duyệt'
  if (status === 'rejected') return '❌ Từ chối'
  return status
}

function renderLeaveRows() {
  const body = document.getElementById('leave-body')
  body.innerHTML = leaveRows
    .map(
      (row, idx) => `
      <tr>
        <td>${idx + 1}</td>
        <td>${row.name}</td>
        <td>${row.type}</td>
        <td>${row.from} → ${row.to} (${row.days} ngày)</td>
        <td>${row.created_at || '--'}</td>
        <td>${statusText(row.status)}</td>
        <td><button data-id="${row.id}" class="view-btn">👁️ Xem</button></td>
      </tr>
    `
    )
    .join('')

  body.querySelectorAll('.view-btn').forEach((btn) => {
    btn.addEventListener('click', () => openModal(Number(btn.dataset.id)))
  })
}

async function loadLeaves() {
  const status = document.getElementById('statusFilter').value
  leaveRows = await ManagerAPI.leaves(status)
  renderLeaveRows()
}

function openModal(id) {
  selected = leaveRows.find((row) => row.id === id)
  if (!selected) return
  document.getElementById('leave-detail').innerHTML = `
    <p><strong>Nhân viên:</strong> ${selected.name}</p>
    <p><strong>Loại nghỉ:</strong> ${selected.type}</p>
    <p><strong>Thời gian:</strong> ${selected.from} → ${selected.to} (${selected.days} ngày)</p>
    <p><strong>Lý do:</strong> ${selected.reason || 'Không có'}</p>
  `
  document.getElementById('leave-modal').hidden = false
}

function closeModal() {
  document.getElementById('leave-modal').hidden = true
  selected = null
  document.getElementById('leave-note').value = ''
}

async function submitDecision(type) {
  if (!selected) return
  const note = document.getElementById('leave-note').value
  if (type === 'approve') {
    await ManagerAPI.approveLeave(selected.id, note)
  } else {
    await ManagerAPI.rejectLeave(selected.id, note)
  }
  closeModal()
  await loadLeaves()
}

document.getElementById('statusFilter').addEventListener('change', loadLeaves)
document.getElementById('close-modal').addEventListener('click', closeModal)
document.getElementById('approve-btn').addEventListener('click', () => submitDecision('approve'))
document.getElementById('reject-btn').addEventListener('click', () => submitDecision('reject'))

loadLeaves()