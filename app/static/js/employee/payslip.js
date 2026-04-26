function money(v) {
  return `${new Intl.NumberFormat('vi-VN').format(Number(v || 0))}đ`
}

async function api(url, options = {}) {
  const res = await fetch(url, options)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Request failed')
  return data
}

async function loadPayroll() {
  const params = new URLSearchParams({
    year: document.getElementById('filter-year').value,
    status: document.getElementById('filter-status').value,
    has_complaint: document.getElementById('filter-complaint').value,
    paid_state: document.getElementById('filter-paid').value
  })
  const data = await api(`/employee/payslip/api/history?${params.toString()}`)

  document.getElementById('summary-title').textContent = data.summary.title
  document.getElementById('summary-net').textContent = `Thực nhận: ${money(data.summary.net_salary)}`
  document.getElementById('summary-status').textContent = data.summary.status
  document.getElementById('summary-payment').textContent = data.summary.payment_date
  document.getElementById('summary-complaint').textContent = data.summary.complaint_status
  document.getElementById('summary-dependents').textContent = data.number_of_dependents

  const rows = data.items.filter((x) => {
    const f = document.getElementById('filter-complaint').value
    if (f === 'true') return x.has_complaint
    if (f === 'false') return !x.has_complaint
    return true
  })

  document.getElementById('salary-body').innerHTML = rows.length ? rows.map((r) => `<tr>
    <td>${String(r.month).padStart(2, '0')}/${r.year}</td>
    <td>${money(r.basic_salary)}</td>
    <td>${money(r.allowance)}</td>
    <td>${money(r.overtime)}</td>
    <td>${money(r.deduction)}</td>
    <td>${money(r.insurance)}</td>
    <td>${money(r.tax)}</td>
    <td><b>${money(r.net_salary)}</b></td>
    <td>${r.status_label}${r.complaint_status_label ? `<br/><small>${r.complaint_status_label}</small>` : ''}</td>
    <td>
      <button onclick="viewDetail(${r.id})">Xem chi tiết</button>
      <button onclick="downloadPayslip(${r.id})">Tải phiếu lương</button>
      <button onclick="sendComplaint(${r.id})">Phản hồi / Khiếu nại</button>
    </td>
  </tr>`).join('') : '<tr><td colspan="10">Không có dữ liệu.</td></tr>'
}

async function viewDetail(id) {
  const d = await api(`/employee/payslip/api/${id}`)
  await Swal.fire({
    title: `Phiếu lương ${String(d.month).padStart(2, '0')}/${d.year}`,
    html: `<p>Lương cơ bản: <b>${money(d.basic_salary)}</b></p>
    <p>Phụ cấp ăn trưa: <b>${money(d.lunch_allowance)}</b></p>
    <p>Phụ cấp trách nhiệm: <b>${money(d.responsibility_allowance)}</b></p>
    <p>Thưởng: <b>${money(d.bonus)}</b></p>
    <p>Overtime: <b>${money(d.overtime)}</b></p>
    <p>Deduction: <b>${money(d.deduction)}</b></p>
    <p>Bảo hiểm (10.5%): <b>${money(d.insurance)}</b></p>
    <p>Thuế TNCN: <b>${money(d.tax)}</b></p>
    <p>Số người phụ thuộc: <b>${d.number_of_dependents}</b></p>
    <p>Giảm trừ gia cảnh: <b>${money(d.family_deduction)}</b></p>
    <p><b>Tổng thực nhận: ${money(d.net_salary)}</b></p>`
  })
}

async function downloadPayslip(id) {
  await Swal.fire({ title: 'Đang tạo PDF...', timer: 900, showConfirmButton: false })
  window.open(`/employee/payslip/api/${id}/pdf`, '_blank')
}

async function sendComplaint(id) {
  const result = await Swal.fire({
    title: 'Phản hồi / Khiếu nại',
    html: `<select id="issue_type" class="swal2-input">
      <option value="attendance_issue">Sai ngày công</option>
      <option value="ot_issue">Sai OT</option>
      <option value="allowance_issue">Sai phụ cấp</option>
      <option value="tax_issue">Sai thuế</option>
      <option value="insurance_issue">Sai bảo hiểm</option>
      <option value="deduction_issue">Sai deduction</option>
      <option value="other">Khác</option></select>
      <textarea id="issue_desc" class="swal2-textarea" placeholder="Nội dung chi tiết" required></textarea>
      <input type="file" id="issue_file" class="swal2-file" accept=".png,.jpg,.jpeg,.pdf"/>`,
    showCancelButton: true,
    preConfirm: () => {
      const desc = document.getElementById('issue_desc').value.trim()
      if (!desc) {
        Swal.showValidationMessage('Vui lòng nhập nội dung chi tiết')
        return false
      }
      const form = new FormData()
      form.append('issue_type', document.getElementById('issue_type').value)
      form.append('description', desc)
      const file = document.getElementById('issue_file').files[0]
      if (file) form.append('attachment', file)
      return form
    }
  })
  if (!result.isConfirmed) return
  await api(`/employee/payslip/api/${id}/complaint`, { method: 'POST', body: result.value })
  await Swal.fire({ icon: 'success', title: 'Đã gửi khiếu nại' })
  await loadComplaints()
  await loadPayroll()
}

async function loadComplaints() {
  const data = await api('/employee/payslip/api/complaints')
  document.getElementById('complaint-list').innerHTML = (data.items || []).map((x) => `<article class="complaint-item">
    <div><b>${x.title}</b><p>${x.status_label} · ${x.created_at || ''}</p></div>
    <div>${x.closed ? 'Đã đóng' : `<button onclick="closeComplaint(${x.id})">Đóng khiếu nại</button>`}</div>
  </article>`).join('') || '<p>Chưa có khiếu nại.</p>'
}

async function closeComplaint(id) {
  const ok = await Swal.fire({ icon: 'question', title: 'Đóng khiếu nại?', showCancelButton: true, confirmButtonText: 'Đóng' })
  if (!ok.isConfirmed) return
  await api(`/employee/payslip/api/complaints/${id}/close`, { method: 'POST' })
  await Swal.fire({ icon: 'success', title: 'Đã đóng khiếu nại' })
  await loadComplaints()
  await loadPayroll()
}

function relationLabel(v) {
  return { con: 'Con', vo_chong: 'Vợ/chồng', bo: 'Cha', me: 'Mẹ', khac: 'Khác' }[v] || v
}

async function loadDependents() {
  const data = await api('/employee/profile/dependents')
  document.getElementById('summary-dependents').textContent = data.number_of_dependents || 0
  document.getElementById('dependent-list').innerHTML = (data.items || []).map((d) => `<article class="dependent-item">
  <div><b>${d.full_name}</b><p>${relationLabel(d.relationship)} · ${d.dob} · MST: ${d.tax_code || '---'} · ${d.is_valid ? 'Hợp lệ' : 'Chưa hợp lệ'}</p></div>
  <div><button onclick="editDependent(${d.id})">Sửa</button><button onclick="deleteDependent(${d.id})">Xóa</button></div></article>`).join('') || '<p>Chưa có người phụ thuộc.</p>'
}

async function addDependent() {
  const result = await Swal.fire({
    title: 'Thêm người phụ thuộc',
    html: '<input id="dep_name" class="swal2-input" placeholder="Họ tên"/><input id="dep_dob" class="swal2-input" type="date"/><select id="dep_rel" class="swal2-input"><option value="con">Con</option><option value="vo_chong">Vợ/Chồng</option><option value="bo">Cha</option><option value="me">Mẹ</option><option value="khac">Khác</option></select><input id="dep_tax" class="swal2-input" placeholder="MST cá nhân"/>',
    showCancelButton: true,
    preConfirm: () => ({
      full_name: document.getElementById('dep_name').value,
      dob: document.getElementById('dep_dob').value,
      relationship: document.getElementById('dep_rel').value,
      tax_code: document.getElementById('dep_tax').value,
      is_valid: true
    })
  })
  if (!result.isConfirmed) return
  await api('/employee/profile/dependents', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(result.value) })
  await Swal.fire({ icon: 'success', title: 'Đã thêm dependent' })
  await loadDependents()
}

async function editDependent(id) {
  const list = await api('/employee/profile/dependents')
  const d = (list.items || []).find((x) => x.id === id)
  if (!d) return
  const result = await Swal.fire({
    title: 'Cập nhật người phụ thuộc',
    html: `<input id="dep_name" class="swal2-input" value="${d.full_name}"/><input id="dep_dob" class="swal2-input" type="date" value="${d.dob}"/><select id="dep_rel" class="swal2-input"><option value="con">Con</option><option value="vo_chong">Vợ/Chồng</option><option value="bo">Cha</option><option value="me">Mẹ</option><option value="khac">Khác</option></select><input id="dep_tax" class="swal2-input" value="${d.tax_code || ''}"/><label><input type="checkbox" id="dep_valid" ${d.is_valid ? 'checked' : ''}/> Hợp lệ</label>`,
    showCancelButton: true,
    didOpen: () => { document.getElementById('dep_rel').value = d.relationship },
    preConfirm: () => ({
      full_name: document.getElementById('dep_name').value,
      dob: document.getElementById('dep_dob').value,
      relationship: document.getElementById('dep_rel').value,
      tax_code: document.getElementById('dep_tax').value,
      is_valid: document.getElementById('dep_valid').checked
    })
  })
  if (!result.isConfirmed) return
  await api(`/employee/profile/dependents/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(result.value) })
  await Swal.fire({ icon: 'success', title: 'Đã cập nhật dependent' })
  await loadDependents()
}

async function deleteDependent(id) {
  const ok = await Swal.fire({ title: 'Xóa dependent?', showCancelButton: true, confirmButtonText: 'Xóa' })
  if (!ok.isConfirmed) return
  await api(`/employee/profile/dependents/${id}`, { method: 'DELETE' })
  await Swal.fire({ icon: 'success', title: 'Đã xóa dependent' })
  await loadDependents()
}

function initTabs() {
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach((x) => x.classList.remove('active'))
      document.querySelectorAll('.tab-content').forEach((x) => x.classList.add('hidden'))
      btn.classList.add('active')
      document.getElementById(`tab-${btn.dataset.tab}`).classList.remove('hidden')
    })
  })
}

document.getElementById('btn-filter').addEventListener('click', loadPayroll)
document.getElementById('add-dependent').addEventListener('click', addDependent)

initTabs()
loadPayroll().catch((e) => Swal.fire({ icon: 'error', title: e.message }))
loadComplaints().catch((e) => Swal.fire({ icon: 'error', title: e.message }))
loadDependents().catch((e) => Swal.fire({ icon: 'error', title: e.message }))

window.viewDetail = viewDetail
window.downloadPayslip = downloadPayslip
window.sendComplaint = sendComplaint
window.closeComplaint = closeComplaint
window.editDependent = editDependent
window.deleteDependent = deleteDependent