let contractRows = []

function getFilters() {
  return {
    employee_name: document.getElementById('f-employee-name').value.trim(),
    employee_code: document.getElementById('f-employee-code').value.trim(),
    contract_type: document.getElementById('f-contract-type').value,
    contract_status: document.getElementById('f-contract-status').value,
    end_date_from: document.getElementById('f-end-date-from').value,
    end_date_to: document.getElementById('f-end-date-to').value,
    department: document.getElementById('f-department').value.trim(),
    position: document.getElementById('f-position').value.trim()
  }
}

function renderSummary(summary = {}) {
  document.getElementById('sum-total').textContent = summary.total_contracts || 0
  document.getElementById('sum-expiring').textContent = summary.expiring || 0
  document.getElementById('sum-probation').textContent = summary.probation || 0
  document.getElementById('sum-pending-renewal').textContent = summary.pending_renewal || 0
  document.getElementById('sum-termination').textContent = summary.termination_proposals || 0
}

function fmtDate(value) {
  if (!value) return '--'
  return new Date(value).toLocaleDateString('vi-VN')
}

function renderTable() {
  const tbody = document.getElementById('contractRows')
  tbody.innerHTML = contractRows
    .map((row) => `
      <tr>
        <td>${row.employee_code || '--'}</td>
        <td>${row.employee_name || '--'}</td>
        <td>${row.position || '--'}</td>
        <td>${row.contract_type || '--'}</td>
        <td>${fmtDate(row.start_date)}</td>
        <td>${fmtDate(row.end_date)}</td>
        <td>${row.days_left == null ? '--' : `${row.days_left} ngày`}</td>
        <td>${row.status_label || row.status || '--'}</td>
        <td>${fmtDate(row.latest_renewal_at)}</td>
        <td class="actions">
          <button data-action="view" data-id="${row.id}">Xem</button>
          <button data-action="renewal" data-id="${row.id}">Đề xuất gia hạn</button>
          <button data-action="termination" data-id="${row.id}">Đề xuất chấm dứt</button>
          <button data-action="probation_conversion" data-id="${row.id}">Đề xuất chuyển chính thức</button>
          <button data-action="review" data-id="${row.id}">Xác nhận review</button>
        </td>
      </tr>
    `)
    .join('')

  tbody.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => handleAction(btn.dataset.action, Number(btn.dataset.id)))
  })

}

async function loadContracts() {
  try {  const box = document.getElementById('contract-error')
  box.hidden = true
    const payload = await ManagerAPI.contractsOverview(getFilters())
    contractRows = payload.rows || []
    renderSummary(payload.summary || {})
    renderTable()
  } catch (err) {
    box.hidden = false
    box.textContent = err.message
  }
}

async function showContractDetail(contractId) {
  const detail = await ManagerAPI.contractDetail(contractId)
  const historyHtml = (detail.renewal_history || [])
    .slice(0, 5)
    .map((x) => `<li>${x.proposal_type} - ${x.status} (${fmtDate(x.created_at)})</li>`)
    .join('') || '<li>Chưa có lịch sử đề xuất</li>'

  await Swal.fire({
    title: 'Chi tiết hợp đồng',
    width: 800,
    html: `
      <div style="text-align:left; line-height:1.6">
        <p><b>Nhân viên:</b> ${detail.employee.full_name} (${detail.employee.code})</p>
        <p><b>Chức danh:</b> ${detail.employee.position}</p>
        <p><b>Loại hợp đồng:</b> ${detail.contract_type || '--'}</p>
        <p><b>Lương cơ bản:</b> ${Number(detail.basic_salary || 0).toLocaleString('vi-VN')} VND</p>
        <p><b>Phụ cấp:</b> ${Number(detail.allowance || 0).toLocaleString('vi-VN')} VND</p>
        <p><b>Thời hạn:</b> ${fmtDate(detail.start_date)} → ${fmtDate(detail.end_date)}</p>
        <p><b>Đánh giá hiệu suất gần nhất:</b> ${detail.performance_review || '--'}</p>
        <p><b>Ghi chú quản lý:</b> ${detail.manager_note || '--'}</p>
        <p><b>Lịch sử gia hạn/đề xuất:</b></p><ul>${historyHtml}</ul>
      </div>
    `,
    confirmButtonText: 'Đóng'
  })
}

async function openProposalForm(contractId, proposalType) {
  const result = await Swal.fire({
    title: 'Gửi đề xuất hợp đồng',
    html: `
      <textarea id="swal-reason" class="swal2-textarea" placeholder="Lý do đề xuất"></textarea>
      <input id="swal-date" type="date" class="swal2-input">
      <input id="swal-duration" type="number" min="1" class="swal2-input" placeholder="Thời gian đề xuất (tháng)">
      <textarea id="swal-note" class="swal2-textarea" placeholder="Ghi chú đánh giá chuyên môn"></textarea>
    `,
    focusConfirm: false,
    showCancelButton: true,
    confirmButtonText: 'Gửi đề xuất',
    preConfirm: () => ({
      reason: document.getElementById('swal-reason').value.trim(),
      proposed_date: document.getElementById('swal-date').value || null,
      proposed_duration_months: Number(document.getElementById('swal-duration').value || 0) || null,
      professional_note: document.getElementById('swal-note').value.trim() || null
    })
  })
  if (!result.isConfirmed) return

  if (!result.value.reason) {
    await Swal.fire({ icon: 'warning', title: 'Vui lòng nhập lý do đề xuất' })
    return
  }

  await ManagerAPI.createContractProposal(contractId, {
    proposal_type: proposalType,
    ...result.value
  })
  await Swal.fire({ icon: 'success', title: 'Đã gửi đề xuất đến HR/Admin' })
  await loadContracts()
}

async function confirmReview(contractId) {
  const result = await Swal.fire({
    title: 'Xác nhận đã review chuyên môn?',
    input: 'textarea',
    inputPlaceholder: 'Ghi chú review',
    showCancelButton: true,
    confirmButtonText: 'Xác nhận review'
  })
  if (!result.isConfirmed) return
  await ManagerAPI.confirmContractReview(contractId, result.value || '')
  await Swal.fire({ icon: 'success', title: 'Đã xác nhận review' })
}

async function handleAction(action, contractId) {
  try {
    if (action === 'view') return showContractDetail(contractId)
    if (action === 'review') return confirmReview(contractId)
    return openProposalForm(contractId, action)
  } catch (err) {
    await Swal.fire({ icon: 'error', title: err.message || 'Không thể xử lý yêu cầu' })
  }
}

document.getElementById('btn-search').addEventListener('click', loadContracts)
document.getElementById('btn-reset').addEventListener('click', async () => {
  ;['f-employee-name', 'f-employee-code', 'f-contract-type', 'f-contract-status', 'f-end-date-from', 'f-end-date-to', 'f-department', 'f-position'].forEach((id) => {
    const el = document.getElementById(id)
    el.value = id.includes('type') || id.includes('status') ? 'all' : ''
  })
  await loadContracts()
})

loadContracts()