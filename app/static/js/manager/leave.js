let leaveRows = []
let selected = null

const LEAVE_STATUS = {
  pending: '🟡 Chờ Manager duyệt',
  pending_hr: '🔵 Chờ HR duyệt',
  pending_admin: '🟣 Chờ Admin duyệt',
  approved: '🟢 Đã duyệt',
  rejected: '❌ Từ chối',
  supplement_requested: '🟠 Yêu cầu bổ sung',
  cancelled: '⚪ Hủy đơn',
  complaint: '🔴 Khiếu nại'
}

function collectFilters() {
  return {
    employee_name: document.getElementById('employee_name').value.trim(),
    employee_code: document.getElementById('employee_code').value.trim(),
    department: document.getElementById('department').value.trim(),
    leave_type: document.getElementById('leave_type').value.trim(),
    status: document.getElementById('status').value,
    from_date: document.getElementById('from_date').value,
    to_date: document.getElementById('to_date').value,
    is_paid: document.getElementById('is_paid').value,
    emergency_only: document.getElementById('emergency_only').checked,
    has_attachment: document.getElementById('has_attachment').checked
  }
}

function renderLeaveRows() {
  const body = document.getElementById('leave-body')
  body.innerHTML = leaveRows
    .map((row) => `
      <tr>
        <td>#${row.id}</td>
        <td>${row.name}${row.is_emergency ? ' <span class="badge emergency">Khẩn</span>' : ''}</td>
        <td>${row.employee_code}</td>
        <td>${row.department}</td>
        <td>${row.position}</td>
        <td>${row.type}${row.is_paid ? ' (Có lương)' : ' (Không lương)'}</td>
        <td>${row.from}</td>
        <td>${row.to}</td>
        <td>${row.days}</td>
        <td>${row.reason || '--'}</td>
        <td>${row.attachment ? `<a href="${row.attachment}" target="_blank">Xem</a>` : '--'}</td>
        <td>${LEAVE_STATUS[row.status] || row.status}</td>
        <td>${row.created_at || '--'}</td>
        <td><button data-id="${row.id}" class="view-btn">👁️ Xem</button></td>
      </tr>
          `)
    .join('')

  body.querySelectorAll('.view-btn').forEach((btn) => {
    btn.addEventListener('click', () => openModal(Number(btn.dataset.id)))
  })
}
function renderSummary(summary) {
  document.getElementById('sum-pending').textContent = summary.pending || 0
  document.getElementById('sum-today').textContent = summary.today || 0
  document.getElementById('sum-emergency').textContent = summary.emergency || 0
  document.getElementById('sum-approved').textContent = summary.approved || 0
  document.getElementById('sum-rejected').textContent = summary.rejected || 0
  document.getElementById('sum-supplement').textContent = summary.supplement_requested || 0
}
async function loadLeaves() {
  try {
    const filters = collectFilters()
    const [rows, summary] = await Promise.all([
      ManagerAPI.leaves(filters),
      ManagerAPI.leaveSummary(filters)
    ])
    leaveRows = rows
    renderLeaveRows()
    renderSummary(summary)
  } catch (err) {
    await Swal.fire({ icon: 'error', title: err.message || 'Không tải được danh sách đơn nghỉ' })
  }
}
async function openModal(id) {
  try {
    selected = await ManagerAPI.leaveDetail(id)
    const overlap = selected.overlapping || []
    const overlapHtml = overlap.length
      ? `<ul>${overlap.map((x) => `<li>${x.employee_name} (${x.from} → ${x.to}) - ${x.status}</li>`).join('')}</ul>`
      : '<p>Không có nhân sự nghỉ trùng thời điểm.</p>'
    const complaints = (selected.complaints || []).length
      ? `<ul>${selected.complaints.map((x) => `<li>${x.title} - ${x.status}</li>`).join('')}</ul>`
      : '<p>Chưa có khiếu nại.</p>'

    document.getElementById('leave-detail').innerHTML = `
      <p><strong>Nhân viên:</strong> ${selected.employee.name} (#${selected.employee.employee_code}) - ${selected.employee.department} / ${selected.employee.position}</p>
      <p><strong>Loại nghỉ:</strong> ${selected.leave.type} (${selected.leave.is_paid ? 'Có lương' : 'Không lương'})</p>
      <p><strong>Thời gian:</strong> ${selected.leave.from} → ${selected.leave.to} (${selected.leave.days} ngày)</p>
      <p><strong>Lý do:</strong> ${selected.leave.reason || 'Không có'}</p>
      <p><strong>Quota còn lại:</strong> ${selected.quota.remaining_days} / ${selected.quota.total_days}</p>
      <p><strong>Backup công việc:</strong> ${selected.replacement_employee}</p>
      <p><strong>File minh chứng:</strong> ${selected.leave.document_url ? `<a href="${selected.leave.document_url}" target="_blank">Mở file</a>` : 'Không có'}</p>
      <h4>Nhân sự nghỉ cùng thời điểm</h4>${overlapHtml}
      <h4>Khiếu nại / phản hồi</h4>${complaints}
    `
    document.getElementById('leave-modal').hidden = false
  } catch (err) {
    await Swal.fire({ icon: 'error', title: err.message || 'Không tải được chi tiết đơn nghỉ' })
  }
}

function closeModal() {
  document.getElementById('leave-modal').hidden = true
  selected = null
}
async function submitApprove() {
  if (!selected) return
  const confirm = await Swal.fire({ icon: 'question', title: 'Duyệt và chuyển HR?', input: 'text', inputLabel: 'Ghi chú cho HR (tuỳ chọn)', showCancelButton: true })
  if (!confirm.isConfirmed) return
  await ManagerAPI.approveLeave(selected.id, confirm.value || '')
  await Swal.fire({ icon: 'success', title: 'Đã chuyển đơn sang HR duyệt' })
  closeModal()
  await loadLeaves()
}

async function submitReject() {
  if (!selected) return
  const result = await Swal.fire({ title: 'Nhập lý do từ chối', input: 'text', inputPlaceholder: 'Ví dụ: thiếu người thay thế', showCancelButton: true })
  if (!result.isConfirmed) return
  if (!(result.value || '').trim()) {
    await Swal.fire({ icon: 'warning', title: 'Bắt buộc nhập lý do từ chối' })
    return
  }
  await ManagerAPI.rejectLeave(selected.id, result.value)
  await Swal.fire({ icon: 'success', title: 'Đã từ chối đơn nghỉ' })
  closeModal()
  await loadLeaves()
}

async function submitSupplement() {
  if (!selected) return
  const result = await Swal.fire({ title: 'Yêu cầu bổ sung hồ sơ', input: 'text', inputPlaceholder: 'Thiếu giấy tờ gì?', showCancelButton: true })
  if (!result.isConfirmed) return
  if (!(result.value || '').trim()) {
    await Swal.fire({ icon: 'warning', title: 'Bắt buộc nhập nội dung cần bổ sung' })
    return
  }
  await ManagerAPI.supplementLeave(selected.id, result.value)
  await Swal.fire({ icon: 'success', title: 'Đã yêu cầu bổ sung hồ sơ' })
  await ManagerAPI.supplementLeave(selected.id, result.value)
  await Swal.fire({ icon: 'success', title: 'Đã yêu cầu bổ sung hồ sơ' })
  closeModal()
  await loadLeaves()
}

document.getElementById('search-btn').addEventListener('click', loadLeaves)
document.getElementById('close-modal').addEventListener('click', closeModal)
document.getElementById('approve-btn').addEventListener('click', submitApprove)
document.getElementById('reject-btn').addEventListener('click', submitReject)
document.getElementById('supplement-btn').addEventListener('click', submitSupplement)

loadLeaves()