function money(v) {
  return `${new Intl.NumberFormat('vi-VN').format(Number(v || 0))}đ`
}

async function loadSelfPayroll() {
  const year = document.getElementById('self-year').value
  const rows = await ManagerAPI.selfPayrollHistory(year)
  const body = document.getElementById('self-body')
  body.innerHTML = rows.map((r) => `<tr>
    <td>${String(r.month).padStart(2, '0')}/${r.year}</td>
    <td>${money(r.basic_salary)}</td><td>${money(r.allowance)}</td><td>${money(r.overtime)}</td><td>${money(r.deduction)}</td>
    <td>${money(r.insurance)}</td><td>${money(r.tax)}</td><td>${money(r.net_salary)}</td><td>${r.status_label}</td>
    <td>
      <button onclick="viewDetail(${r.id})">Xem chi tiết</button>
      <button onclick="downloadPdf(${r.id})">Tải phiếu lương</button>
      <button onclick="sendComplaint(${r.id})">Phản hồi/Khiếu nại</button>
    </td>
  </tr>`).join('')

  if (rows.length) {
    const latest = rows[0]
    document.getElementById('self-month').textContent = `${String(latest.month).padStart(2, '0')}/${latest.year}`
    document.getElementById('self-net').textContent = money(latest.net_salary)
    document.getElementById('self-status').textContent = latest.status_label
    document.getElementById('self-payday').textContent = latest.payment_date || '--'
    document.getElementById('self-complaint').textContent = latest.status === 'complaint' ? 'Có khiếu nại' : 'Không'
  }
  await loadDependents()
}

async function viewDetail(id) {
  const d = await ManagerAPI.selfPayrollDetail(id)
  await Swal.fire({
    title: `Phiếu lương ${String(d.month).padStart(2, '0')}/${d.year}`,
    html: `<p>Lương cơ bản: <b>${money(d.basic_salary)}</b></p>
<p>Phụ cấp ăn trưa: <b>${money(d.lunch_allowance)}</b></p>
<p>Phụ cấp trách nhiệm: <b>${money(d.responsibility_allowance)}</b></p>
<p>Thưởng: <b>${money(d.bonus)}</b></p>
<p>Overtime: <b>${money(d.overtime)}</b></p>
<p>Deduction: <b>${money(d.deduction)}</b></p>
<p>Bảo hiểm: <b>${money(d.insurance)}</b></p>
<p>Thuế TNCN: <b>${money(d.tax)}</b></p>
<p>Số người phụ thuộc: <b>${d.number_of_dependents}</b></p>
<p>Giảm trừ gia cảnh: <b>${money(d.family_deduction)}</b></p>
<p><b>Tổng thực nhận: ${money(d.net_salary)}</b></p>`
  })
}

async function downloadPdf(id) {
  await Swal.fire({ title: 'Đang tạo phiếu lương PDF...', timer: 900, showConfirmButton: false })
  window.open(ManagerAPI.selfPayrollPdfUrl(id), '_blank')
}

async function sendComplaint(id) {
  const result = await Swal.fire({
    title: 'Phản hồi / Khiếu nại lương',
    html: `<select id="issue_type" class="swal2-input">
      <option value="attendance_issue">Sai ngày công</option><option value="ot_issue">Sai OT</option><option value="allowance_issue">Sai phụ cấp</option>
      <option value="tax_issue">Sai thuế</option><option value="insurance_issue">Sai bảo hiểm</option><option value="other">Khác</option></select>
      <textarea id="issue_desc" class="swal2-textarea" placeholder="Nội dung chi tiết"></textarea>
      <input type="file" id="issue_file" class="swal2-file" accept=".png,.jpg,.jpeg,.pdf"/>`,
    showCancelButton: true,
    preConfirm: () => {
      const formData = new FormData()
      formData.append('issue_type', document.getElementById('issue_type').value)
      formData.append('description', document.getElementById('issue_desc').value)
      const file = document.getElementById('issue_file').files[0]
      if (file) formData.append('attachment', file)
      return formData
    }
  })
  if (!result.isConfirmed) return
  await ManagerAPI.selfPayrollComplaint(id, result.value)
  await Swal.fire({ icon: 'success', title: 'Đã gửi complaint cho HR' })
}

async function loadDependents() {
  const data = await ManagerAPI.selfDependents()
  document.getElementById('dependent-summary').innerHTML = `Số dependent hợp lệ: <b>${data.number_of_dependents || 0}</b><br/>` +
    (data.items || []).map((x) => `${x.full_name} - ${x.relationship} ${x.is_valid ? '✅' : '❌'} <button onclick="removeDependent(${x.id})">Xóa</button>`).join('<br/>')
}

async function openDependentForm() {
  const result = await Swal.fire({
    title: 'Thêm/Cập nhật dependent',
    html: '<input id="dep_name" class="swal2-input" placeholder="Họ tên"/><input id="dep_dob" class="swal2-input" type="date"/><select id="dep_rel" class="swal2-input"><option value="con">Con</option><option value="vo_chong">Vợ/Chồng</option><option value="bo">Bố</option><option value="me">Mẹ</option><option value="khac">Khác</option></select><input id="dep_tax" class="swal2-input" placeholder="MST cá nhân"/>',
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
  await ManagerAPI.createSelfDependent(result.value)
  await Swal.fire({ icon: 'success', title: 'Đã cập nhật dependent' })
  await loadDependents()
}

async function removeDependent(id) {
  const ok = await Swal.fire({ title: 'Xóa dependent?', showCancelButton: true })
  if (!ok.isConfirmed) return
  await ManagerAPI.deleteSelfDependent(id)
  await Swal.fire({ icon: 'success', title: 'Đã xóa dependent' })
  await loadDependents()
}

document.getElementById('load-self').addEventListener('click', loadSelfPayroll)
loadSelfPayroll()